# coding=UTF-8
"""频道与消息路由。

提供频道列表、消息估算等功能。
"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from module.api.dependencies import (
    get_cache_manager,
    require_token,
    get_identifier_service,
)
from module.api.responses import json_response, error_json_response
from module.api.models.chat import (
    ChatResolveOut,
    MessageRangeRequest,
    MessageEstimateRequest,
    MessageAnalyzeRequest,
)
from module.core.identifier_service import IdentifierService

router = APIRouter(prefix="/chats", tags=["频道"])
logger = logging.getLogger(__name__)


def _get_client(request: Request):
    """获取 Telegram Client 实例（从 AppContext 单例读取）。"""
    try:
        from module.core.integration import get_context

        ctx = get_context()
        return ctx.client if ctx else None
    except Exception:
        return None


def _dialog_to_dict(dialog):
    """将 Dialog 对象转换为字典"""
    chat_type = "unknown"
    if dialog.chat.type.value == "channel":
        chat_type = "channel"
    elif dialog.chat.type.value == "supergroup":
        chat_type = "supergroup"
    elif dialog.chat.type.value == "group":
        chat_type = "group"
    elif dialog.chat.type.value == "private":
        chat_type = "private"

    return {
        "id": str(dialog.chat.id),
        "title": dialog.chat.title or f"chat_{dialog.chat.id}",
        "type": chat_type,
        "username": getattr(dialog.chat, "username", None),
    }


@router.get("")
async def list_chats(
    request: Request,
    token: str = Depends(require_token),
    cache_manager=Depends(get_cache_manager),
    limit: int = 50,
    refresh: bool = Query(False),
):
    """获取已加入频道列表。

    从 TelegramClient 获取对话列表并转换为频道格式。
    支持缓存以减少 Telegram API 调用。
    """
    client = _get_client(request)

    if cache_manager:

        async def fetch_dialogs():
            dialogs = await client.get_dialogs(limit=limit)
            return [_dialog_to_dict(d) for d in dialogs]

        try:
            chats = await cache_manager.get_chat_list(
                fetcher=fetch_dialogs,
                force_refresh=refresh,
            )
            return json_response(data=chats)
        except Exception as e:
            logger.warning(f"缓存获取失败，降级为直接调用: {e}")

    # 降级逻辑
    try:
        dialogs = await client.get_dialogs(limit=limit)
        chats = [_dialog_to_dict(d) for d in dialogs]
        return json_response(data=chats)
    except Exception as e:
        logger.error(f"获取频道列表失败: {e}")
        return json_response(data=[])


@router.get("/resolve")
async def resolve_chat(
    request: Request,
    identifier: str = Query(..., min_length=1, description="要解析的标识符"),
    token: str = Depends(require_token),
    identifier_service=Depends(get_identifier_service),
):
    """解析任意支持的对话标识符，返回标准化对话信息。

    支持格式：
    - 纯数字 chat_id
    - @username
    - 裸 username
    - https://t.me/username 或 t.me/username
    """
    resolved = await identifier_service.resolve(identifier)
    return json_response(
        data=ChatResolveOut(
            chat_id=resolved.chat_id,
            chat_type=resolved.chat_type,
            chat_name=resolved.chat_name,
            username=resolved.username,
            message_count=resolved.message_count,
            media_count=resolved.media_count,
            has_access=resolved.has_access,
            is_private=resolved.is_private,
        ).model_dump(mode="json")
    )


@router.post("/messages/estimate")
async def estimate_messages(
    body: MessageEstimateRequest,
    request: Request,
    token: str = Depends(require_token),
    cache_manager=Depends(get_cache_manager),
    identifier_service: IdentifierService = Depends(get_identifier_service),
):
    """抽样估算消息范围大小与数量。

    根据 range_mode 差异化估算：
    - id_range: 小范围精确，大范围头尾抽样
    - multiple_ids: 精确遍历
    - date_range: 小范围精确，大范围头尾抽样
    - all: 头尾各10条抽样估算
    - recent: 最近 N 条抽样估算

    支持缓存以减少 Telegram API 调用。
    """
    # 解析 chat_id（支持 URL/@username/数字ID）
    resolved = await identifier_service.resolve(str(body.chat_id))
    chat_id = resolved.chat_id

    # 转换为 MessageRangeRequest 用于验证
    range_req = MessageRangeRequest(
        range_mode=body.range_mode,
        min_id=body.min_id,
        max_id=body.max_id,
        start_date=body.start_date,
        end_date=body.end_date,
        message_list=body.message_list,
        download_type=body.type_filters,
        recent_count=body.recent_count,
    )
    is_valid, errors = range_req.validate_for_mode()
    if not is_valid:
        return error_json_response(
            code=400, message=f"消息范围参数无效: {'; '.join(errors)}"
        )

    client = _get_client(request)
    if client is None:
        return error_json_response(code=400, message="Telegram Client 未连接")

    params = body.model_dump(exclude={"chat_id"})

    if cache_manager:

        async def fetch_estimate():
            from module.api.estimate import estimate_message_stats

            return await estimate_message_stats(
                client=client,
                chat_id=chat_id,
                range_mode=body.range_mode,
                params=params,
                precise=False,
            )

        try:
            result = await cache_manager.get_message_stats(
                chat_id=chat_id,
                params=params,
                estimator=fetch_estimate,
            )
            return json_response(data=result)
        except Exception as e:
            logger.warning(f"缓存估算失败，降级为直接调用: {e}")

    # 降级逻辑
    try:
        from module.api.estimate import estimate_message_stats

        result = await estimate_message_stats(
            client=client,
            chat_id=chat_id,
            range_mode=body.range_mode,
            params=params,
            precise=False,
        )
        return json_response(data=result)
    except Exception as e:
        logger.error(f"估算消息失败: {e}")
        return error_json_response(code=400, message=f"估算失败: {e}")


@router.post("/messages/analyze")
async def analyze_messages(
    body: MessageAnalyzeRequest,
    request: Request,
    token: str = Depends(require_token),
    identifier_service: IdentifierService = Depends(get_identifier_service),
):
    """精确分析消息范围（遍历）。

    小范围（≤500条）精确遍历获取真实文件大小，
    大范围降级为抽样估算并标记 sampled=True。
    """
    # 解析 chat_id（支持 URL/@username/数字ID）
    resolved = await identifier_service.resolve(str(body.chat_id))
    chat_id = resolved.chat_id

    client = _get_client(request)
    if client is None:
        return error_json_response(code=400, message="Telegram Client 未连接")

    try:
        from module.api.estimate import estimate_message_stats

        params = body.model_dump(exclude={"chat_id"})
        result = await estimate_message_stats(
            client=client,
            chat_id=chat_id,
            range_mode=body.range_mode,
            params=params,
            precise=True,
        )
        return json_response(data=result)
    except Exception as e:
        logger.error(f"分析消息失败: {e}")
        return error_json_response(code=400, message=f"分析失败: {e}")
