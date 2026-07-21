# coding=UTF-8
"""Token 相关 SQLModel 表模型。

对应 tokens 表。时间字段统一使用 datetime（带 UTC 时区），
SQLAlchemy 自动序列化为 ISO 8601 字符串存储。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TokenRecordDB(SQLModel, table=True):
    """Token 记录模型（对应 tokens 表）。

    时间戳字段使用 datetime 类型，由 SQLAlchemy 序列化为 ISO 8601 字符串存储。
    revoked 字段使用 int 类型（0/1），对应 SQLite 的 INTEGER。
    """

    __tablename__ = "tokens"

    token: str = Field(primary_key=True)
    user_id: int = Field(default=0, nullable=False)
    created_at: datetime = Field(nullable=False, index=True)
    expires_at: datetime = Field(nullable=False, index=True)
    last_used_at: Optional[datetime] = None
    revoked: int = Field(default=0, nullable=False)
    usage_count: int = Field(default=0, nullable=False)
