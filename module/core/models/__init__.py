# coding=UTF-8
"""SQLModel 数据库模型包。

所有数据库表模型定义在此包中，通过 SQLModel 自动管理 schema。
模型类名加 `Record` 后缀，避免与业务逻辑层的 dataclass 冲突。
"""

from module.core.models.task import TaskItemRecord, TaskRecord
from module.core.models.repository import (
    FileDistributionRecord,
    RepositoryFileRecord,
    RepositorySourceRecord,
)
from module.core.models.cache import CacheEntryRecord, CacheParamRecord
from module.core.models.token import TokenRecordDB

__all__ = [
    "TaskRecord",
    "TaskItemRecord",
    "RepositoryFileRecord",
    "RepositorySourceRecord",
    "FileDistributionRecord",
    "CacheEntryRecord",
    "CacheParamRecord",
    "TokenRecordDB",
]
