# coding=UTF-8
"""
RepositoryDB 模块 - Telegram_Restricted_Media_Downloader 仓库数据库管理

职责：
- 管理仓库文件记录（repository_files）
- 管理文件来源映射（repository_sources）
- 管理文件分发记录（file_distributions）
- 提供文件去重、来源追踪、分发记录的查询接口
"""

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass
class RepositoryFile:
    """仓库文件记录。"""

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
    created_at: str | None
    updated_at: str | None
    status: str = "active"


@dataclass
class RepositorySource:
    """文件来源映射记录。"""

    id: int | None
    file_unique_id: str
    source_chat_id: int
    source_message_id: int
    source_link: str | None
    created_at: str | None


@dataclass
class FileDistribution:
    """文件分发记录。"""

    id: int | None
    file_unique_id: str
    target_chat_id: int
    target_message_id: int | None
    method: str
    task_id: str | None
    created_at: str | None


# ==================== 异常类型 ====================


class RepositoryDBError(Exception):
    """仓库数据库操作异常的基类。"""


# ==================== RepositoryDB ====================


class RepositoryDB:
    """
    仓库数据库管理器。

    管理三张表：repository_files、repository_sources、file_distributions，
    提供文件去重、来源追踪、分发记录的 CRUD 和查询接口。
    """

    def __init__(self, db_path: str) -> None:
        """
        初始化仓库数据库管理器。

        Args:
            db_path: SQLite 数据库文件路径。
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构和索引。"""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS repository_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_unique_id TEXT UNIQUE NOT NULL,
                    file_id TEXT NOT NULL,
                    content_hash TEXT,
                    file_size INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    mime_type TEXT,
                    file_name TEXT,
                    repository_chat_id INTEGER NOT NULL,
                    repository_message_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                );

                CREATE INDEX IF NOT EXISTS idx_repo_files_file_id
                    ON repository_files(file_id);

                CREATE INDEX IF NOT EXISTS idx_repo_files_content_hash
                    ON repository_files(content_hash);

                CREATE INDEX IF NOT EXISTS idx_repo_files_chat_msg
                    ON repository_files(repository_chat_id, repository_message_id);

                CREATE TABLE IF NOT EXISTS repository_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_unique_id TEXT NOT NULL,
                    source_chat_id INTEGER NOT NULL,
                    source_message_id INTEGER NOT NULL,
                    source_link TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_chat_id, source_message_id),
                    FOREIGN KEY (file_unique_id) REFERENCES repository_files(file_unique_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_repo_sources_file_unique_id
                    ON repository_sources(file_unique_id);

                CREATE TABLE IF NOT EXISTS file_distributions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_unique_id TEXT NOT NULL,
                    target_chat_id INTEGER NOT NULL,
                    target_message_id INTEGER,
                    method TEXT NOT NULL,
                    task_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_unique_id) REFERENCES repository_files(file_unique_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_distributions_file_unique_id
                    ON file_distributions(file_unique_id);

                CREATE INDEX IF NOT EXISTS idx_distributions_task_id
                    ON file_distributions(task_id);
            """)

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器，自动提交/回滚/关闭。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ==================== 行/记录转换方法 ====================

    def _file_to_row(self, record: RepositoryFile) -> tuple:
        """将 RepositoryFile 转换为 SQLite 行元组（不含 id）。"""
        return (
            record.file_unique_id,
            record.file_id,
            record.content_hash,
            record.file_size,
            record.file_type,
            record.mime_type,
            record.file_name,
            record.repository_chat_id,
            record.repository_message_id,
            record.status,
        )

    def _row_to_file(self, row: tuple) -> RepositoryFile:
        """将 SQLite 行元组转换为 RepositoryFile。"""
        return RepositoryFile(
            id=row[0],
            file_unique_id=row[1],
            file_id=row[2],
            content_hash=row[3],
            file_size=row[4],
            file_type=row[5],
            mime_type=row[6],
            file_name=row[7],
            repository_chat_id=row[8],
            repository_message_id=row[9],
            created_at=row[10],
            updated_at=row[11],
            status=row[12],
        )

    def _source_to_row(self, record: RepositorySource) -> tuple:
        """将 RepositorySource 转换为 SQLite 行元组（不含 id）。"""
        return (
            record.file_unique_id,
            record.source_chat_id,
            record.source_message_id,
            record.source_link,
        )

    def _row_to_source(self, row: tuple) -> RepositorySource:
        """将 SQLite 行元组转换为 RepositorySource。"""
        return RepositorySource(
            id=row[0],
            file_unique_id=row[1],
            source_chat_id=row[2],
            source_message_id=row[3],
            source_link=row[4],
            created_at=row[5],
        )

    def _distribution_to_row(self, record: FileDistribution) -> tuple:
        """将 FileDistribution 转换为 SQLite 行元组（不含 id）。"""
        return (
            record.file_unique_id,
            record.target_chat_id,
            record.target_message_id,
            record.method,
            record.task_id,
        )

    def _row_to_distribution(self, row: tuple) -> FileDistribution:
        """将 SQLite 行元组转换为 FileDistribution。"""
        return FileDistribution(
            id=row[0],
            file_unique_id=row[1],
            target_chat_id=row[2],
            target_message_id=row[3],
            method=row[4],
            task_id=row[5],
            created_at=row[6],
        )

    # ==================== CRUD 方法 ====================

    def insert_file_record(self, record: RepositoryFile) -> int:
        """
        插入文件记录。

        使用 INSERT OR IGNORE 处理 file_unique_id 的 UNIQUE 约束。

        Args:
            record: RepositoryFile 实例（id 字段忽略）。

        Returns:
            插入行的 id；若因 UNIQUE 约束被忽略则返回 0。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO repository_files
                   (file_unique_id, file_id, content_hash, file_size,
                    file_type, mime_type, file_name,
                    repository_chat_id, repository_message_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._file_to_row(record),
            )
            return cursor.lastrowid

    def insert_source_mapping(self, record: RepositorySource) -> int:
        """
        插入来源映射记录。

        使用 INSERT OR IGNORE 处理 (source_chat_id, source_message_id) 的 UNIQUE 约束。

        Args:
            record: RepositorySource 实例（id 字段忽略）。

        Returns:
            插入行的 id；若因 UNIQUE 约束被忽略则返回 0。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO repository_sources
                   (file_unique_id, source_chat_id, source_message_id, source_link)
                   VALUES (?, ?, ?, ?)""",
                self._source_to_row(record),
            )
            return cursor.lastrowid

    def update_file_id(self, file_unique_id: str, new_file_id: str) -> None:
        """
        更新文件的 file_id。

        同时更新 updated_at 为 CURRENT_TIMESTAMP。

        Args:
            file_unique_id: 文件唯一标识。
            new_file_id: 新的 file_id。
        """
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE repository_files
                   SET file_id = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE file_unique_id = ?""",
                (new_file_id, file_unique_id),
            )

    def insert_distribution(self, record: FileDistribution) -> int:
        """
        插入分发记录。

        Args:
            record: FileDistribution 实例（id 字段忽略）。

        Returns:
            插入行的 id。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO file_distributions
                   (file_unique_id, target_chat_id, target_message_id, method, task_id)
                   VALUES (?, ?, ?, ?, ?)""",
                self._distribution_to_row(record),
            )
            return cursor.lastrowid

    # ==================== 查询方法 ====================

    def get_file_by_source(
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
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT f.id, f.file_unique_id, f.file_id, f.content_hash,
                          f.file_size, f.file_type, f.mime_type, f.file_name,
                          f.repository_chat_id, f.repository_message_id,
                          f.created_at, f.updated_at, f.status
                   FROM repository_sources s
                   JOIN repository_files f ON s.file_unique_id = f.file_unique_id
                   WHERE s.source_chat_id = ? AND s.source_message_id = ?""",
                (source_chat_id, source_message_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_file(row)

    def get_file_by_unique_id(self, file_unique_id: str) -> RepositoryFile | None:
        """
        根据 file_unique_id 查找文件。

        Args:
            file_unique_id: 文件唯一标识。

        Returns:
            RepositoryFile 实例，未找到时返回 None。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, file_unique_id, file_id, content_hash,
                          file_size, file_type, mime_type, file_name,
                          repository_chat_id, repository_message_id,
                          created_at, updated_at, status
                   FROM repository_files
                   WHERE file_unique_id = ?""",
                (file_unique_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_file(row)

    def get_file_by_content_hash(self, content_hash: str) -> RepositoryFile | None:
        """
        根据 content_hash 查找活跃文件。

        仅返回 status='active' 的记录。

        Args:
            content_hash: 文件内容哈希值。

        Returns:
            RepositoryFile 实例，未找到时返回 None。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, file_unique_id, file_id, content_hash,
                          file_size, file_type, mime_type, file_name,
                          repository_chat_id, repository_message_id,
                          created_at, updated_at, status
                   FROM repository_files
                   WHERE content_hash = ? AND status = 'active'""",
                (content_hash,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_file(row)

    def get_repository_message_id(self, file_unique_id: str) -> tuple[int, int] | None:
        """
        获取文件的仓库消息定位信息。

        用于 copy_message 分发时获取源消息位置。

        Args:
            file_unique_id: 文件唯一标识。

        Returns:
            (repository_chat_id, repository_message_id) 元组，未找到时返回 None。
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT repository_chat_id, repository_message_id
                   FROM repository_files
                   WHERE file_unique_id = ?""",
                (file_unique_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return (row[0], row[1])
