# coding=UTF-8
"""Repository 路由模块。

提供仓库模式API端点，包括文件管理、来源映射、分发记录、同步触发等。
设计依据: module-design-web-api.md §2.3 路由组织(第165行)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path

from module.api.dependencies import require_token
from module.api.responses import json_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repository", tags=["仓库"])


@router.get("/files")
async def list_repository_files(
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    chat_id: Optional[int] = Query(None, description="频道ID过滤"),
    _: str = Depends(require_token),
):
    """获取仓库文件列表(分页)。

    :param offset: 偏移量
    :param limit: 每页数量
    :param chat_id: 频道ID过滤（可选）
    :param _: Token认证依赖
    :return: 文件列表及总数
    """
    try:
        from module.integration import get_context

        ctx = get_context()
        if not ctx or not hasattr(ctx, "repository_db"):
            return json_response(
                data={"items": [], "total": 0, "offset": offset, "limit": limit},
                message="RepositoryDB未初始化",
            )

        db = ctx.repository_db
        files = db.list_files(chat_id=chat_id, offset=offset, limit=limit)
        total = db.count_files(chat_id=chat_id)

        return json_response(
            data={"items": files, "total": total, "offset": offset, "limit": limit}
        )
    except Exception as e:
        logger.error("获取仓库文件列表失败: %s", e)
        return json_response(code=500, message=f"获取文件列表失败: {str(e)}")


@router.get("/files/{file_unique_id}")
async def get_file_detail(
    file_unique_id: str = Path(..., description="文件唯一标识"),
    _: str = Depends(require_token),
):
    """获取单个文件详情。

    :param file_unique_id: 文件唯一标识
    :param _: Token认证依赖
    :return: 文件详情
    """
    try:
        from module.integration import get_context

        ctx = get_context()
        if not ctx or not hasattr(ctx, "repository_db"):
            return json_response(code=500, message="RepositoryDB未初始化")

        db = ctx.repository_db
        file = db.get_file_by_unique_id(file_unique_id)

        if not file:
            return json_response(code=404, message=f"文件不存在: {file_unique_id}")

        return json_response(data=file)
    except Exception as e:
        logger.error("获取文件详情失败: %s", e)
        return json_response(code=500, message=f"获取文件详情失败: {str(e)}")


@router.get("/sources")
async def list_repository_sources(
    file_unique_id: Optional[str] = Query(None, description="文件唯一标识过滤"),
    _: str = Depends(require_token),
):
    """获取来源映射列表。

    :param file_unique_id: 文件唯一标识过滤（可选）
    :param _: Token认证依赖
    :return: 来源映射列表
    """
    try:
        from module.integration import get_context

        ctx = get_context()
        if not ctx or not hasattr(ctx, "repository_db"):
            return json_response(data={"items": []}, message="RepositoryDB未初始化")

        db = ctx.repository_db
        sources = db.list_sources(file_unique_id=file_unique_id)

        return json_response(data={"items": sources})
    except Exception as e:
        logger.error("获取来源映射列表失败: %s", e)
        return json_response(code=500, message=f"获取来源映射失败: {str(e)}")


@router.get("/distributions")
async def list_file_distributions(
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    chat_id: Optional[int] = Query(None, description="频道ID过滤"),
    _: str = Depends(require_token),
):
    """获取分发记录列表(分页)。

    :param offset: 偏移量
    :param limit: 每页数量
    :param chat_id: 频道ID过滤（可选）
    :param _: Token认证依赖
    :return: 分发记录列表及总数
    """
    try:
        from module.integration import get_context

        ctx = get_context()
        if not ctx or not hasattr(ctx, "repository_db"):
            return json_response(
                data={"items": [], "total": 0, "offset": offset, "limit": limit},
                message="RepositoryDB未初始化",
            )

        db = ctx.repository_db
        distributions = db.list_distributions(
            chat_id=chat_id, offset=offset, limit=limit
        )
        total = db.count_distributions(chat_id=chat_id)

        return json_response(
            data={
                "items": distributions,
                "total": total,
                "offset": offset,
                "limit": limit,
            }
        )
    except Exception as e:
        logger.error("获取分发记录列表失败: %s", e)
        return json_response(code=500, message=f"获取分发记录失败: {str(e)}")


@router.post("/sync")
async def trigger_repository_sync(
    _: str = Depends(require_token),
):
    """触发仓库增量同步。

    :param _: Token认证依赖
    :return: 同步触发结果
    """
    try:
        from module.integration import get_context

        ctx = get_context()
        if not ctx or not hasattr(ctx, "repository_sync"):
            return json_response(code=500, message="RepositorySync未初始化")

        sync = ctx.repository_sync

        # 检查是否已在同步中
        if hasattr(sync, "_syncing") and sync._syncing:
            return json_response(code=409, message="同步任务正在进行中")

        # 触发异步同步任务
        import asyncio

        asyncio.create_task(sync.incremental_sync())

        return json_response(message="同步任务已触发")
    except Exception as e:
        logger.error("触发仓库同步失败: %s", e)
        return json_response(code=500, message=f"触发同步失败: {str(e)}")


@router.get("/status")
async def get_repository_status(
    _: str = Depends(require_token),
):
    """获取仓库同步状态。

    :param _: Token认证依赖
    :return: 同步状态信息
    """
    try:
        from module.integration import get_context

        ctx = get_context()
        if not ctx or not hasattr(ctx, "repository_sync"):
            return json_response(code=500, message="RepositorySync未初始化")

        sync = ctx.repository_sync
        db = ctx.repository_db if hasattr(ctx, "repository_db") else None

        status_info = {
            "syncing": getattr(sync, "_syncing", False),
            "last_sync_time": getattr(sync, "_last_sync_time", None),
            "files_count": db.count_files() if db else 0,
            "sources_count": db.count_sources() if db else 0,
            "distributions_count": db.count_distributions() if db else 0,
        }

        return json_response(data=status_info)
    except Exception as e:
        logger.error("获取仓库状态失败: %s", e)
        return json_response(code=500, message=f"获取状态失败: {str(e)}")
