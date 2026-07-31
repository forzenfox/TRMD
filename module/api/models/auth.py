# coding=UTF-8
"""认证相关 Pydantic 数据模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TokenInfo(BaseModel):
    """Token 状态信息。"""

    valid: bool
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    usage_count: int = 0
