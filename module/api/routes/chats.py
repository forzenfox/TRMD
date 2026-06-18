# coding=UTF-8
"""频道与消息路由。

提供频道列表、消息估算等功能。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request

from module.api.dependencies import require_token
from module.api.responses import json_response, error_json_response
from module.api.models.chat import ChatOut, MessageRangeRequest, MessageEstimateOut

router = APIRouter(prefix="/chats", tags=["频道"])


@router.get("")
async def list_chats(
    request: Request,
    token: str = Depends(require_token),
):
    """获取已加入频道列表。

    当前版本返回模拟数据，实际实现需接入 TelegramClient。
    """
    # 模拟频道数据，实际应从 TelegramClient 获取
    chats = [
        ChatOut(id="chat_1", title="示例频道 1", type="channel", username="example1"),
        ChatOut(id="chat_2", title="示例频道 2", type="group", username=None),
    ]
    return json_response(data=[c.model_dump() for c in chats])


@router.post("/{chat_id}/messages/estimate")
async def estimate_messages(
    chat_id: str,
    body: MessageRangeRequest,
    request: Request,
    token: str = Depends(require_token),
):
    """抽样估算消息范围大小与数量。

    当前版本返回模拟数据。
    """
    # 模拟估算数据
    estimate = MessageEstimateOut(
        message_count=850,
        total_size_bytes=7730941132,
        total_size_human="7.2 GB",
        estimated_duration_seconds=2700,
        sampled=True,
    )
    return json_response(data=estimate.model_dump())


@router.post("/{chat_id}/messages/analyze")
async def analyze_messages(
    chat_id: str,
    body: MessageRangeRequest,
    request: Request,
    token: str = Depends(require_token),
):
    """精确分析消息范围（遍历）。

    当前版本返回模拟数据。
    """
    # 模拟精确分析数据
    estimate = MessageEstimateOut(
        message_count=1000,
        total_size_bytes=8589934592,
        total_size_human="8.0 GB",
        estimated_duration_seconds=3600,
        sampled=False,
    )
    return json_response(data=estimate.model_dump())
