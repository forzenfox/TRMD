# coding=UTF-8
"""缓存相关 SQLModel 表模型。

对应 cache_entries、cache_params 两张表。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel


class CacheEntryRecord(SQLModel, table=True):
    """缓存条目模型（对应 cache_entries）。"""

    __tablename__ = "cache_entries"

    cache_key: str = Field(primary_key=True)
    cache_type: str = Field(nullable=False)
    chat_id: Optional[int] = Field(default=None, index=True)
    payload: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    expires_at: datetime = Field(nullable=False)
    created_at: datetime = Field(nullable=False)
    updated_at: datetime = Field(nullable=False)
    version: int = Field(default=1)


class CacheParamRecord(SQLModel, table=True):
    """缓存参数模型（对应 cache_params）。"""

    __tablename__ = "cache_params"

    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(unique=True, nullable=False)
    param_hash: str = Field(index=True, nullable=False)
    param_json: str = Field(nullable=False)
