# coding=UTF-8
"""仓库相关 SQLModel 表模型。

对应 repository_files、repository_sources、file_distributions 三张表。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class RepositoryFileRecord(SQLModel, table=True):
    """仓库文件记录模型（对应 repository_files）。"""

    __tablename__ = "repository_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_unique_id: str = Field(unique=True, nullable=False, index=True)
    file_id: str = Field(nullable=False, index=True)
    content_hash: Optional[str] = Field(default=None, index=True)
    file_size: int = Field(nullable=False)
    file_type: str = Field(nullable=False)
    mime_type: Optional[str] = None
    file_name: Optional[str] = None
    repository_chat_id: int = Field(nullable=False)
    repository_message_id: int = Field(nullable=False)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: str = Field(default="active")


class RepositorySourceRecord(SQLModel, table=True):
    """文件来源映射记录模型（对应 repository_sources）。"""

    __tablename__ = "repository_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_unique_id: str = Field(index=True)
    source_chat_id: int = Field(nullable=False)
    source_message_id: int = Field(nullable=False)
    created_at: Optional[datetime] = None

    # UNIQUE(source_chat_id, source_message_id) 约束
    __table_args__ = (
        UniqueConstraint(
            "source_chat_id", "source_message_id", name="uq_repo_sources_chat_msg"
        ),
    )


class FileDistributionRecord(SQLModel, table=True):
    """文件分发记录模型（对应 file_distributions）。"""

    __tablename__ = "file_distributions"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_unique_id: str = Field(index=True)
    target_chat_id: int = Field(nullable=False)
    target_message_id: Optional[int] = None
    method: str = Field(nullable=False)
    task_id: Optional[str] = Field(default=None, index=True)
    created_at: Optional[datetime] = None
