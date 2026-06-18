# coding=UTF-8
"""频道与消息相关 Pydantic 数据模型。"""

from typing import Optional

from pydantic import BaseModel


class ChatOut(BaseModel):
    """频道响应数据。"""

    id: str
    title: str
    type: str
    username: Optional[str] = None


class MessageRangeRequest(BaseModel):
    """消息范围分析请求体。"""

    range_mode: str
    min_id: Optional[int] = None
    max_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    message_list: Optional[list[str]] = None
    download_type: Optional[list[str]] = None


class MessageEstimateOut(BaseModel):
    """消息估算响应数据。"""

    message_count: int
    total_size_bytes: int
    total_size_human: str
    estimated_duration_seconds: int
    sampled: bool
