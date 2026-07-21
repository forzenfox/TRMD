# coding=UTF-8
"""任务相关 SQLModel 表模型。

对应 tm_tasks、tm_task_items 两张表（tm_task_events 已移除，详见数据模型设计文档 §6.10）。
业务逻辑层使用 Task/TaskItem dataclass，数据库层使用本模块的 Record 模型。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class TaskRecord(SQLModel, table=True):
    """任务主表模型（对应 tm_tasks）。"""

    __tablename__ = "tm_tasks"

    id: str = Field(primary_key=True)
    task_type: str = Field(nullable=False)
    status: str = Field(nullable=False, index=True)
    chat_id: int = Field(nullable=False, index=True)
    chat_username: Optional[str] = None
    chat_type: Optional[str] = None
    params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(nullable=False, index=True)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_size_bytes: int = Field(default=0)
    error_message: Optional[str] = None
    retry_count: int = Field(default=0)
    max_retry_count: int = Field(default=5)
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))


class TaskItemRecord(SQLModel, table=True):
    """子任务表模型（对应 tm_task_items）。"""

    __tablename__ = "tm_task_items"

    id: str = Field(primary_key=True)
    task_id: str = Field(foreign_key="tm_tasks.id", index=True)
    status: str = Field(default="pending", index=True)
    source_message_id: Optional[int] = None
    source_file_path: Optional[str] = None
    target_chat_id: Optional[int] = None
    file_path: Optional[str] = None
    file_size: int = Field(default=0)
    file_sha256: Optional[str] = Field(default=None, index=True)
    telegram_file_id: Optional[str] = None
    file_unique_id: Optional[str] = Field(default=None, index=True)
    uploaded_message_id: Optional[int] = None
    retry_count: int = Field(default=0)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(nullable=False)
    updated_at: datetime = Field(nullable=False)
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # 相册模式分组字段：同一 media_group_id 的消息属于同一相册
    media_group_id: Optional[str] = Field(default=None, index=True)
