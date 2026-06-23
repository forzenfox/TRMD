# coding=UTF-8
"""任务管理路由。

提供任务 CRUD、开始/取消/重试等操作。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request, Query

from module.api.dependencies import require_token, get_task_manager
from module.api.responses import json_response, error_json_response
from module.api.models.task import TaskCreate, TaskOut
from module.api.exceptions import (
    TaskNotFoundError,
    TaskSizeExceeded,
    TaskSizeWarning,
    InsufficientDiskSpace,
    TaskConflictError,
)
from module.core.task_manager import (
    TaskManager,
    Task,
    TaskType,
    TaskStatus,
    InvalidStateTransition,
)

router = APIRouter(prefix="/tasks", tags=["任务"])


def _task_to_out(task: Task) -> TaskOut:
    """将 Task 转换为 TaskOut 响应模型。"""
    return TaskOut(
        id=task.task_id,
        task_type=task.task_type.value,
        status=task.status.value,
        progress=task.progress,
        created_at=task.created_at,
        updated_at=task.started_at or task.completed_at or task.created_at,
        message=task.error_reason,
        success_count=task.success_count,
        failed_count=task.failed_count,
        total_count=len(task.items),
    )


@router.get("")
async def list_tasks(
    request: Request,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
    status_filter: Optional[str] = Query(None, alias="status"),
    task_type: Optional[str] = Query(None, alias="task_type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取任务列表，支持分页和过滤。"""
    # 按状态过滤
    if status_filter:
        try:
            status_enum = TaskStatus(status_filter)
        except ValueError:
            return error_json_response(
                code=400, message=f"无效的状态: {status_filter}", status_code=400
            )
        tasks = await task_manager.list_tasks(status=status_enum)
    else:
        tasks = await task_manager.list_tasks()

    # 按类型过滤
    if task_type:
        try:
            type_enum = TaskType(task_type)
        except ValueError:
            return error_json_response(
                code=400, message=f"无效的类型: {task_type}", status_code=400
            )
        tasks = [t for t in tasks if t.task_type == type_enum]

    total = len(tasks)
    paginated_tasks = tasks[offset : offset + limit]

    data = {
        "items": [_task_to_out(t).model_dump() for t in paginated_tasks],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    return json_response(data=data)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    request: Request,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
):
    """获取任务详情。"""
    task = await task_manager.get_task(task_id)
    if not task:
        raise TaskNotFoundError(task_id)
    return json_response(data=_task_to_out(task).model_dump())


@router.post("")
async def create_task(
    request: Request,
    body: TaskCreate,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
):
    """创建任务。"""
    # 检查磁盘空间
    if not task_manager.check_disk_space():
        raise InsufficientDiskSpace()

    # 检查任务大小（如果 params 中有估算大小）
    estimated_size = body.params.get("estimated_size", 0)
    size_result = task_manager.check_size_threshold(estimated_size)
    if size_result == "exceeded":
        raise TaskSizeExceeded()
    if size_result == "warning":
        size_human = body.params.get("size_human", "")
        raise TaskSizeWarning(size_human)

    # 映射任务类型
    type_map = {
        "download": TaskType.DOWNLOAD,
        "forward": TaskType.FORWARD,
        "upload": TaskType.UPLOAD,
    }
    task_type = type_map.get(body.task_type)
    if task_type is None:
        return error_json_response(
            code=400, message=f"无效的任务类型: {body.task_type}", status_code=400
        )

    # 提取参数
    params = body.params
    chat_id = params.get("chat_id", 0)
    # 将 chat_id 转为 int（可能是 URL 字符串）
    if isinstance(chat_id, str):
        try:
            chat_id = int(chat_id.split("/")[-1])
        except (ValueError, IndexError):
            chat_id = 0

    target_chat_id = params.get("forward_target")
    if isinstance(target_chat_id, str):
        try:
            target_chat_id = int(target_chat_id.split("/")[-1])
        except (ValueError, IndexError):
            target_chat_id = None

    # 范围模式处理
    range_mode = params.get("range_mode")
    message_range = None
    if range_mode == "id_range":
        min_id = params.get("min_id")
        max_id = params.get("max_id")
        if min_id is not None and max_id is not None:
            message_range = (min_id, max_id)

    file_paths = params.get("file_paths", [])
    delete_after = params.get("delete_after_upload", True)

    # 创建任务
    task = await task_manager.create_task(
        task_type=task_type,
        chat_id=chat_id,
        target_chat_id=target_chat_id,
        message_range=message_range,
        file_paths=file_paths,
        estimated_size=estimated_size,
        delete_after_upload=delete_after,
    )

    return json_response(data=_task_to_out(task).model_dump(), status_code=201)


@router.post("/{task_id}/start")
async def start_task(
    task_id: str,
    request: Request,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
):
    """开始/排队任务。"""
    try:
        started = await task_manager.start_task(task_id)
        task = await task_manager.get_task(task_id)
        return json_response(
            data=_task_to_out(task).model_dump(),
            message="任务已开始" if started else "任务已加入队列",
        )
    except TaskNotFoundError:
        raise TaskNotFoundError(task_id)
    except InvalidStateTransition:
        raise TaskConflictError("任务状态不允许启动")


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    request: Request,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
):
    """取消任务。"""
    try:
        await task_manager.cancel_task(task_id)
        task = await task_manager.get_task(task_id)
        return json_response(data=_task_to_out(task).model_dump(), message="任务已取消")
    except TaskNotFoundError:
        raise TaskNotFoundError(task_id)
    except InvalidStateTransition:
        raise TaskConflictError("任务状态不允许取消")


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    request: Request,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
):
    """重试任务。"""
    try:
        await task_manager.retry_task(task_id)
        task = await task_manager.get_task(task_id)
        return json_response(data=_task_to_out(task).model_dump(), message="任务已重试")
    except TaskNotFoundError:
        raise TaskNotFoundError(task_id)
    except InvalidStateTransition:
        raise TaskConflictError("任务状态不允许重试")


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    request: Request,
    token: str = Depends(require_token),
    task_manager: TaskManager = Depends(get_task_manager),
):
    """删除已完成或失败的任务记录。"""
    task = await task_manager.get_task(task_id)
    if not task:
        raise TaskNotFoundError(task_id)

    if task.status not in (
        TaskStatus.PENDING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ):
        raise TaskConflictError("只能删除等待中、已完成、失败或已取消的任务")

    # 从内存中删除
    task_manager._tasks.pop(task_id, None)
    return json_response(data=None, message="任务记录已删除")
