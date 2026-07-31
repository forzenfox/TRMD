# coding=UTF-8
"""
RepositoryDB 模块 - Telegram_Restricted_Media_Downloader 仓库数据库管理

职责：
- 管理仓库文件记录（repository_files）
- 管理文件来源映射（repository_sources）
- 管理文件分发记录（file_distributions）
- 提供文件去重、来源追踪、分发记录的查询接口

基于 SQLModel + SQLAlchemy 异步引擎实现，数据库引擎与建表由
`module.core.db` 统一管理（init_db / get_session / close_db）。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from module.core.db import get_session
from module.core.repository.models import (
    FileDistributionRecord,
    RepositoryFileRecord,
    RepositorySourceRecord,
)

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass
class RepositoryFile:
    """仓库文件记录（业务逻辑层使用）。"""

    id: int | None
    file_unique_id: str
    file_id: str
    content_hash: str | None
    file_size: int
    file_type: str
    mime_type: str | None
    file_name: str | None
    repository_chat_id: int
    repository_message_id: int
    created_at: datetime | None
    updated_at: datetime | None
    status: str = "active"


@dataclass
class RepositorySource:
    """文件来源映射记录（业务逻辑层使用）。"""

    id: int | None
    file_unique_id: str
    source_chat_id: int
    source_message_id: int
    created_at: datetime | None


@dataclass
class FileDistribution:
    """文件分发记录（业务逻辑层使用）。"""

    id: int | None
    file_unique_id: str
    target_chat_id: int
    target_message_id: int | None
    method: str
    task_id: str | None
    created_at: datetime | None


# ==================== 异常类型 ====================


class RepositoryDBError(Exception):
    """仓库数据库操作异常的基类。"""


# ==================== RepositoryDB ====================


class RepositoryDB:
    """
    仓库数据库管理器（异步实现）。

    管理三张表：repository_files、repository_sources、file_distributions，
    提供文件去重、来源追踪、分发记录的 CRUD 和查询接口。

    数据库引擎与表结构由 `module.core.db.init_db` 统一初始化，
    本类不再持有 db_path，所有操作通过 `get_session` 获取异步会话执行。
    """

    def __init__(self) -> None:
        """
        初始化仓库数据库管理器。

        注意：调用方需先通过 `module.core.db.init_db(db_path)` 完成引擎与
        建表初始化后，再使用本类实例进行数据库操作。
        """
        # 引擎与表结构由 module.core.db 统一管理，此处无需持有 db_path
        logger.debug("RepositoryDB 实例已创建（异步模式）")

    # ==================== 辅助方法 ====================

    @staticmethod
    def _now() -> datetime:
        """生成当前 UTC datetime 对象。

        用于替代原生 SQL 层的 DEFAULT CURRENT_TIMESTAMP 语义。
        SQLAlchemy 会自动将 datetime 序列化为 ISO 8601 字符串存储。
        """
        return datetime.now(timezone.utc)

    # ----- dataclass <-> SQLModel Record 映射 -----

    def _file_to_record(self, record: RepositoryFile) -> RepositoryFileRecord:
        """将 RepositoryFile dataclass 转换为 RepositoryFileRecord。

        时间戳字段（created_at/updated_at）原样映射；若业务层未提供
        （通常为 None），由调用方在插入前填充当前时间。
        """
        return RepositoryFileRecord(
            file_unique_id=record.file_unique_id,
            file_id=record.file_id,
            content_hash=record.content_hash,
            file_size=record.file_size,
            file_type=record.file_type,
            mime_type=record.mime_type,
            file_name=record.file_name,
            repository_chat_id=record.repository_chat_id,
            repository_message_id=record.repository_message_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            status=record.status,
        )

    def _record_to_file(self, record: RepositoryFileRecord) -> RepositoryFile:
        """将 RepositoryFileRecord 转换为 RepositoryFile dataclass。"""
        return RepositoryFile(
            id=record.id,
            file_unique_id=record.file_unique_id,
            file_id=record.file_id,
            content_hash=record.content_hash,
            file_size=record.file_size,
            file_type=record.file_type,
            mime_type=record.mime_type,
            file_name=record.file_name,
            repository_chat_id=record.repository_chat_id,
            repository_message_id=record.repository_message_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            status=record.status,
        )

    def _source_to_record(self, record: RepositorySource) -> RepositorySourceRecord:
        """将 RepositorySource dataclass 转换为 RepositorySourceRecord。"""
        return RepositorySourceRecord(
            file_unique_id=record.file_unique_id,
            source_chat_id=record.source_chat_id,
            source_message_id=record.source_message_id,
            created_at=record.created_at,
        )

    def _record_to_source(self, record: RepositorySourceRecord) -> RepositorySource:
        """将 RepositorySourceRecord 转换为 RepositorySource dataclass。"""
        return RepositorySource(
            id=record.id,
            file_unique_id=record.file_unique_id,
            source_chat_id=record.source_chat_id,
            source_message_id=record.source_message_id,
            created_at=record.created_at,
        )

    def _distribution_to_record(
        self, record: FileDistribution
    ) -> FileDistributionRecord:
        """将 FileDistribution dataclass 转换为 FileDistributionRecord。"""
        return FileDistributionRecord(
            file_unique_id=record.file_unique_id,
            target_chat_id=record.target_chat_id,
            target_message_id=record.target_message_id,
            method=record.method,
            task_id=record.task_id,
            created_at=record.created_at,
        )

    def _record_to_distribution(
        self, record: FileDistributionRecord
    ) -> FileDistribution:
        """将 FileDistributionRecord 转换为 FileDistribution dataclass。"""
        return FileDistribution(
            id=record.id,
            file_unique_id=record.file_unique_id,
            target_chat_id=record.target_chat_id,
            target_message_id=record.target_message_id,
            method=record.method,
            task_id=record.task_id,
            created_at=record.created_at,
        )

    # ==================== CRUD 方法 ====================

    async def insert_file_record(self, record: RepositoryFile) -> int:
        """
        插入文件记录。

        使用 try/except IntegrityError 处理 file_unique_id 的 UNIQUE 约束，
        等价于原生 SQL 的 INSERT OR IGNORE 语义。

        Args:
            record: RepositoryFile 实例（id 字段忽略）。

        Returns:
            插入行的 id；若因 UNIQUE 约束被忽略则返回 0。
        """
        now = self._now()
        db_record = self._file_to_record(record)
        # 业务层传入时 created_at/updated_at 通常为 None，此处填充当前时间
        db_record.created_at = record.created_at or now
        db_record.updated_at = record.updated_at or now

        logger.debug(
            f"insert_file_record: file_unique_id={db_record.file_unique_id}, "
            f"file_id={db_record.file_id}"
        )

        async with get_session() as session:
            try:
                session.add(db_record)
                await session.flush()  # 触发 UNIQUE 约束检查
                await session.commit()
                result_id = db_record.id or 0
                logger.debug(f"insert_file_record OK: id={result_id}")
                return result_id
            except IntegrityError as e:
                # INSERT OR IGNORE 语义：UNIQUE 约束冲突时回滚并返回 0
                await session.rollback()
                logger.debug(f"insert_file_record INTEGRITY_ERROR: {e}")
                return 0

    async def insert_source_mapping(self, record: RepositorySource) -> int:
        """
        插入来源映射记录。

        使用 try/except IntegrityError 处理 (source_chat_id, source_message_id)
        的复合 UNIQUE 约束，等价于原生 SQL 的 INSERT OR IGNORE 语义。

        Args:
            record: RepositorySource 实例（id 字段忽略）。

        Returns:
            插入行的 id；若因 UNIQUE 约束被忽略则返回 0。
        """
        now = self._now()
        db_record = self._source_to_record(record)
        db_record.created_at = record.created_at or now

        logger.debug(
            f"insert_source_mapping: file_unique_id={db_record.file_unique_id}, "
            f"source={db_record.source_chat_id}/{db_record.source_message_id}"
        )

        async with get_session() as session:
            try:
                session.add(db_record)
                await session.flush()  # 触发复合 UNIQUE 约束检查
                await session.commit()
                result_id = db_record.id or 0
                logger.debug(f"insert_source_mapping OK: id={result_id}")
                return result_id
            except IntegrityError as e:
                # INSERT OR IGNORE 语义：复合 UNIQUE 约束冲突时回滚并返回 0
                await session.rollback()
                logger.debug(f"insert_source_mapping INTEGRITY_ERROR: {e}")
                return 0

    async def update_file_id(self, file_unique_id: str, new_file_id: str) -> None:
        """
        更新文件的 file_id。

        同时更新 updated_at 为当前 UTC 时间戳。

        Args:
            file_unique_id: 文件唯一标识。
            new_file_id: 新的 file_id。
        """
        now = self._now()
        async with get_session() as session:
            stmt = select(RepositoryFileRecord).where(
                RepositoryFileRecord.file_unique_id == file_unique_id
            )
            result = await session.execute(stmt)
            db_record = result.scalars().first()
            if db_record is None:
                # 不存在则什么都不做（与原实现一致，不抛异常）
                return
            db_record.file_id = new_file_id
            db_record.updated_at = now
            await session.commit()

    async def insert_distribution(self, record: FileDistribution) -> int:
        """
        插入分发记录。

        Args:
            record: FileDistribution 实例（id 字段忽略）。

        Returns:
            插入行的 id。
        """
        now = self._now()
        db_record = self._distribution_to_record(record)
        db_record.created_at = record.created_at or now

        async with get_session() as session:
            session.add(db_record)
            await session.commit()
            return db_record.id or 0

    # ==================== 查询方法 ====================

    async def get_file_by_source(
        self, source_chat_id: int, source_message_id: int
    ) -> RepositoryFile | None:
        """
        根据来源聊天 ID 和消息 ID 查找文件。

        通过 JOIN repository_sources 和 repository_files 实现。

        Args:
            source_chat_id: 来源聊天 ID。
            source_message_id: 来源消息 ID。

        Returns:
            RepositoryFile 实例，未找到时返回 None。
        """
        async with get_session() as session:
            stmt = (
                select(RepositoryFileRecord)
                .join(
                    RepositorySourceRecord,
                    RepositorySourceRecord.file_unique_id
                    == RepositoryFileRecord.file_unique_id,
                )
                .where(
                    RepositorySourceRecord.source_chat_id == source_chat_id,
                    RepositorySourceRecord.source_message_id == source_message_id,
                )
            )
            result = await session.execute(stmt)
            db_record = result.scalars().first()
            if db_record is None:
                return None
            return self._record_to_file(db_record)

    async def get_file_by_unique_id(self, file_unique_id: str) -> RepositoryFile | None:
        """
        根据 file_unique_id 查找文件。

        Args:
            file_unique_id: 文件唯一标识。

        Returns:
            RepositoryFile 实例，未找到时返回 None。
        """
        async with get_session() as session:
            stmt = select(RepositoryFileRecord).where(
                RepositoryFileRecord.file_unique_id == file_unique_id
            )
            result = await session.execute(stmt)
            db_record = result.scalars().first()
            if db_record is None:
                return None
            return self._record_to_file(db_record)

    async def get_file_by_content_hash(
        self, content_hash: str | None
    ) -> RepositoryFile | None:
        """
        根据 content_hash 查找活跃文件。

        仅返回 status='active' 的记录。

        注意：content_hash 为 None 时直接返回 None，与原生 SQLite
        `WHERE content_hash = NULL`（不匹配任何行）的语义保持一致。

        Args:
            content_hash: 文件内容哈希值。

        Returns:
            RepositoryFile 实例，未找到时返回 None。
        """
        # content_hash 为 None 时，原 SQLite `= NULL` 不匹配任何行
        if content_hash is None:
            return None
        async with get_session() as session:
            stmt = select(RepositoryFileRecord).where(
                RepositoryFileRecord.content_hash == content_hash,
                RepositoryFileRecord.status == "active",
            )
            result = await session.execute(stmt)
            db_record = result.scalars().first()
            if db_record is None:
                return None
            return self._record_to_file(db_record)

    async def get_repository_message_id(
        self, file_unique_id: str
    ) -> tuple[int, int] | None:
        """
        获取文件的仓库消息定位信息。

        用于 copy_message 分发时获取源消息位置。

        Args:
            file_unique_id: 文件唯一标识。

        Returns:
            (repository_chat_id, repository_message_id) 元组，未找到时返回 None。
        """
        async with get_session() as session:
            stmt = select(RepositoryFileRecord).where(
                RepositoryFileRecord.file_unique_id == file_unique_id
            )
            result = await session.execute(stmt)
            db_record = result.scalars().first()
            if db_record is None:
                return None
            return (db_record.repository_chat_id, db_record.repository_message_id)
