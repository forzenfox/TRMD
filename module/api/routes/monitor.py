# coding=UTF-8
"""监控与资源状态路由。

提供监控统计和资源状态查询功能。
"""

import logging
from fastapi import APIRouter, Depends, Request

from module.api.dependencies import require_token, get_monitor
from module.api.responses import json_response, error_json_response

router = APIRouter(prefix="/monitor", tags=["监控"])
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_monitor_stats(
    request: Request,
    token: str = Depends(require_token),
):
    """获取监控统计（系统资源 + 任务统计）。

    返回 CPU、内存、磁盘使用率和任务状态统计。
    """
    monitor = get_monitor(request)
    if monitor is None:
        return error_json_response("监控服务不可用")

    task_manager = getattr(request.app.state, "task_manager", None)

    try:
        stats = monitor.get_monitor_stats(task_manager=task_manager)
        return json_response(data=stats)
    except Exception as e:
        logger.error(f"获取监控统计失败: {e}")
        return error_json_response("获取监控统计失败", str(e))


@router.get("/resource/status")
async def get_resource_status(
    request: Request,
    token: str = Depends(require_token),
):
    """获取资源状态。

    返回磁盘空间、内存限制、并发数、任务大小限制等。
    """
    monitor = get_monitor(request)
    if monitor is None:
        return error_json_response("监控服务不可用")

    task_manager = getattr(request.app.state, "task_manager", None)
    file_manager = getattr(request.app.state, "file_manager", None)
    config_manager = getattr(request.app.state, "config_manager", None)

    try:
        status = monitor.get_resource_status(
            task_manager=task_manager,
            file_manager=file_manager,
            config_manager=config_manager,
        )
        return json_response(data=status)
    except Exception as e:
        logger.error(f"获取资源状态失败: {e}")
        return error_json_response("获取资源状态失败", str(e))
