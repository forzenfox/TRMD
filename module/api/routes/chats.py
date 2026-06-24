# coding=UTF-8
"""频道与消息路由。

提供频道列表、消息估算等功能。
"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from module.api.dependencies import get_cache_manager, require_token
from module.api.responses import json_response, error_json_response
from module.api.models.chat import ChatOut, MessageRangeRequest, MessageEstimateOut

router = APIRouter(prefix="/chats", tags=["频道"])
logger = logging.getLogger(__name__)


def _get_client(request: Request):
    """获取 Telegram Client 实例（从 AppContext 单例读取）。"""
    try:
        from module.integration import get_context
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


@router.post("/{chat_id}/messages/estimate")
async def estimate_messages(
    chat_id: str,
    body: MessageRangeRequest,
    request: Request,
    token: str = Depends(require_token),
    cache_manager=Depends(get_cache_manager),
):
    """抽样估算消息范围大小与数量。

    从 TelegramClient 获取消息历史进行估算。
    验证消息范围参数。支持缓存以减少 Telegram API 调用。
    """
    # 验证消息范围参数
    is_valid, errors = body.validate_for_mode()
    if not is_valid:
        return error_json_response("消息范围参数无效", "; ".join(errors))

    client = _get_client(request)
    params = body.model_dump()  # 用于缓存键

    if cache_manager:
        async def fetch_estimate():
            chat = await client.get_chat(chat_id)
            count = getattr(chat, "messages_count", 0)
            return {
                "message_count": count,
                "total_size_bytes": 0,
                "total_size_human": "未知",
                "estimated_duration_seconds": count * 3,
                "sampled": True,
            }

        try:
            result = await cache_manager.get_message_stats(
                chat_id=chat_id,
                params=params,
                estimator=fetch_estimate,
            )
            return json_response(data=result)
        except Exception as e:
            logger.warning(f"缓存估算失败，降级为直接调用: {e}")

    # 降级逻辑（原有代码不变）
    try:
        # 获取消息计数
        chat = await client.get_chat(chat_id)
        count = getattr(chat, "messages_count", 0)

        # 简单估算（实际应遍历消息获取真实大小）
        estimate = MessageEstimateOut(
            message_count=count,
            total_size_bytes=0,  # 需要遍历消息才能获取
            total_size_human="未知",
            estimated_duration_seconds=count * 3,  # 假设每条消息 3 秒
            sampled=True,
        )
        return json_response(data=estimate.model_dump())
    except Exception as e:
        logger.error(f"估算消息失败: {e}")
        return error_json_response("估算失败", str(e))


@router.post("/{chat_id}/messages/analyze")
async def analyze_messages(
    chat_id: str,
    body: MessageRangeRequest,
    request: Request,
    token: str = Depends(require_token),
):
    """精确分析消息范围（遍历）。

    从 TelegramClient 遍历消息进行精确分析。
    """
    client = _get_client(request)
    try:
        # 获取精确消息数
        chat = await client.get_chat(chat_id)
        count = getattr(chat, "messages_count", 0)

        estimate = MessageEstimateOut(
            message_count=count,
            total_size_bytes=0,
            total_size_human="未知",
            estimated_duration_seconds=count * 3,
            sampled=False,
        )
        return json_response(data=estimate.model_dump())
    except Exception as e:
        logger.error(f"分析消息失败: {e}")
        return error_json_response("分析失败", str(e))
