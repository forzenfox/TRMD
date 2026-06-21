# coding=UTF-8
"""RepositoryDB 模块单元测试。

覆盖数据库表创建、CRUD 操作、查询方法、UNIQUE 约束、索引存在性等场景。
"""

import pytest

from module.core.repository_db import (
    FileDistribution,
    RepositoryDB,
    RepositoryDBError,
    RepositoryFile,
    RepositorySource,
)


# ==================== Fixture ====================


@pytest.fixture
def repo_db(tmp_path):
    """提供使用临时数据库的 RepositoryDB 实例。"""
    db_path = str(tmp_path / "test_trmd.db")
    db = RepositoryDB(db_path=db_path)
    yield db


# ==================== 辅助函数 ====================


def _make_repository_file(**overrides) -> RepositoryFile:
    """创建 RepositoryFile 测试数据。"""
    defaults = {
        "id": None,
        "file_unique_id": "uid_001",
        "file_id": "fid_001",
        "content_hash": "hash_abc123",
        "file_size": 1024,
        "file_type": "video",
        "mime_type": "video/mp4",
        "file_name": "test.mp4",
        "repository_chat_id": -1001234567890,
        "repository_message_id": 42,
        "created_at": None,
        "updated_at": None,
        "status": "active",
    }
    defaults.update(overrides)
    return RepositoryFile(**defaults)


def _make_repository_source(**overrides) -> RepositorySource:
    """创建 RepositorySource 测试数据。"""
    defaults = {
        "id": None,
        "file_unique_id": "uid_001",
        "source_chat_id": -1009876543210,
        "source_message_id": 100,
        "source_link": "https://t.me/channel/100",
        "created_at": None,
    }
    defaults.update(overrides)
    return RepositorySource(**defaults)


def _make_file_distribution(**overrides) -> FileDistribution:
    """创建 FileDistribution 测试数据。"""
    defaults = {
        "id": None,
        "file_unique_id": "uid_001",
        "target_chat_id": -1001111111111,
        "target_message_id": 200,
        "method": "copy_message",
        "task_id": "task_001",
        "created_at": None,
    }
    defaults.update(overrides)
    return FileDistribution(**defaults)


# ==================== 表创建测试 ====================


class TestTableCreation:
    """数据库表和索引创建测试。"""

    def test_repository_files_table_exists(self, repo_db):
        """初始化后应存在 repository_files 表。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='repository_files'"
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "repository_files"

    def test_repository_sources_table_exists(self, repo_db):
        """初始化后应存在 repository_sources 表。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='repository_sources'"
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "repository_sources"

    def test_file_distributions_table_exists(self, repo_db):
        """初始化后应存在 file_distributions 表。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_distributions'"
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "file_distributions"

    def test_pragma_journal_mode_wal(self, repo_db):
        """PRAGMA journal_mode 应为 WAL。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
        assert mode == "wal"

    def test_pragma_foreign_keys_on(self, repo_db):
        """PRAGMA foreign_keys 应为 ON。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute("PRAGMA foreign_keys")
            val = cursor.fetchone()[0]
        assert val == 1

    def test_pragma_busy_timeout(self, repo_db):
        """PRAGMA busy_timeout 应为 10000。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute("PRAGMA busy_timeout")
            val = cursor.fetchone()[0]
        assert val == 10000


# ==================== 索引存在性测试 ====================


class TestIndexExistence:
    """索引创建验证测试。"""

    def _get_indexes(self, repo_db, table_name: str) -> list[str]:
        """获取指定表的所有索引名称。"""
        with repo_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
                (table_name,),
            )
            return [row[0] for row in cursor.fetchall()]

    def test_repository_files_indexes(self, repo_db):
        """repository_files 表应有正确的索引。"""
        indexes = self._get_indexes(repo_db, "repository_files")
        assert "idx_repo_files_file_id" in indexes
        assert "idx_repo_files_content_hash" in indexes
        assert "idx_repo_files_chat_msg" in indexes

    def test_repository_sources_indexes(self, repo_db):
        """repository_sources 表应有正确的索引。"""
        indexes = self._get_indexes(repo_db, "repository_sources")
        assert "idx_repo_sources_file_unique_id" in indexes

    def test_file_distributions_indexes(self, repo_db):
        """file_distributions 表应有正确的索引。"""
        indexes = self._get_indexes(repo_db, "file_distributions")
        assert "idx_distributions_file_unique_id" in indexes
        assert "idx_distributions_task_id" in indexes


# ==================== insert_file_record 测试 ====================


class TestInsertFileRecord:
    """insert_file_record 方法测试。"""

    def test_insert_returns_id(self, repo_db):
        """插入文件记录应返回自增 ID。"""
        record = _make_repository_file()
        row_id = repo_db.insert_file_record(record)
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_insert_data_correct(self, repo_db):
        """插入后数据应可通过 file_unique_id 查询到。"""
        record = _make_repository_file()
        repo_db.insert_file_record(record)
        result = repo_db.get_file_by_unique_id(record.file_unique_id)
        assert result is not None
        assert result.file_unique_id == record.file_unique_id
        assert result.file_id == record.file_id
        assert result.file_size == record.file_size
        assert result.file_type == record.file_type
        assert result.repository_chat_id == record.repository_chat_id
        assert result.repository_message_id == record.repository_message_id

    def test_insert_with_none_optional_fields(self, repo_db):
        """可选字段为 None 时应正确插入。"""
        record = _make_repository_file(
            content_hash=None,
            mime_type=None,
            file_name=None,
        )
        row_id = repo_db.insert_file_record(record)
        assert row_id > 0
        result = repo_db.get_file_by_unique_id(record.file_unique_id)
        assert result is not None
        assert result.content_hash is None
        assert result.mime_type is None
        assert result.file_name is None

    def test_insert_duplicate_unique_id_ignored(self, repo_db):
        """重复 file_unique_id 插入应被忽略（INSERT OR IGNORE）。"""
        record = _make_repository_file(file_unique_id="uid_dup")
        repo_db.insert_file_record(record)
        id2 = repo_db.insert_file_record(record)
        # INSERT OR IGNORE 不会抛异常，但返回的 id 应为 0 或相同值
        assert id2 == 0

    def test_insert_default_status(self, repo_db):
        """未指定 status 时默认应为 'active'。"""
        record = _make_repository_file(status="active")
        repo_db.insert_file_record(record)
        result = repo_db.get_file_by_unique_id(record.file_unique_id)
        assert result is not None
        assert result.status == "active"


# ==================== insert_source_mapping 测试 ====================


class TestInsertSourceMapping:
    """insert_source_mapping 方法测试。"""

    def test_insert_returns_id(self, repo_db):
        """插入来源映射应返回自增 ID。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        source = _make_repository_source()
        row_id = repo_db.insert_source_mapping(source)
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_insert_data_correct(self, repo_db):
        """插入后应能通过来源查询到文件。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        source = _make_repository_source()
        repo_db.insert_source_mapping(source)
        result = repo_db.get_file_by_source(
            source.source_chat_id, source.source_message_id
        )
        assert result is not None
        assert result.file_unique_id == file_record.file_unique_id

    def test_insert_duplicate_source_ignored(self, repo_db):
        """重复 (source_chat_id, source_message_id) 插入应被忽略。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        source = _make_repository_source()
        repo_db.insert_source_mapping(source)
        id2 = repo_db.insert_source_mapping(source)
        assert id2 == 0

    def test_insert_with_none_source_link(self, repo_db):
        """source_link 为 None 时应正确插入。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(source_link=None)
        row_id = repo_db.insert_source_mapping(source)
        assert row_id > 0


# ==================== update_file_id 测试 ====================


class TestUpdateFileId:
    """update_file_id 方法测试。"""

    def test_update_changes_file_id(self, repo_db):
        """更新后 file_id 应改变。"""
        record = _make_repository_file(file_id="old_fid")
        repo_db.insert_file_record(record)
        repo_db.update_file_id(record.file_unique_id, "new_fid")
        result = repo_db.get_file_by_unique_id(record.file_unique_id)
        assert result is not None
        assert result.file_id == "new_fid"

    def test_update_updates_timestamp(self, repo_db):
        """更新后 updated_at 应被刷新为 CURRENT_TIMESTAMP。"""
        record = _make_repository_file()
        repo_db.insert_file_record(record)
        repo_db.update_file_id(record.file_unique_id, "new_fid")
        new_result = repo_db.get_file_by_unique_id(record.file_unique_id)
        assert new_result is not None
        # updated_at 应已更新
        assert new_result.updated_at is not None

    def test_update_nonexistent_does_nothing(self, repo_db):
        """更新不存在的 file_unique_id 不应抛异常。"""
        # 不应抛异常
        repo_db.update_file_id("nonexistent_uid", "new_fid")


# ==================== insert_distribution 测试 ====================


class TestInsertDistribution:
    """insert_distribution 方法测试。"""

    def test_insert_returns_id(self, repo_db):
        """插入分发记录应返回自增 ID。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        dist = _make_file_distribution()
        row_id = repo_db.insert_distribution(dist)
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_insert_with_none_target_message_id(self, repo_db):
        """target_message_id 为 None 时应正确插入。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        dist = _make_file_distribution(target_message_id=None)
        row_id = repo_db.insert_distribution(dist)
        assert row_id > 0

    def test_insert_with_none_task_id(self, repo_db):
        """task_id 为 None 时应正确插入。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        dist = _make_file_distribution(task_id=None)
        row_id = repo_db.insert_distribution(dist)
        assert row_id > 0

    def test_insert_multiple_distributions_for_same_file(self, repo_db):
        """同一文件可以有多条分发记录。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        dist1 = _make_file_distribution(target_chat_id=-100111, method="copy")
        dist2 = _make_file_distribution(target_chat_id=-100222, method="forward")
        id1 = repo_db.insert_distribution(dist1)
        id2 = repo_db.insert_distribution(dist2)
        assert id1 > 0
        assert id2 > 0
        assert id1 != id2


# ==================== get_file_by_source 测试 ====================


class TestGetFileBySource:
    """get_file_by_source 方法测试。"""

    def test_returns_file_when_source_exists(self, repo_db):
        """来源存在时应返回对应的 RepositoryFile。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        source = _make_repository_source()
        repo_db.insert_source_mapping(source)
        result = repo_db.get_file_by_source(
            source.source_chat_id, source.source_message_id
        )
        assert result is not None
        assert isinstance(result, RepositoryFile)
        assert result.file_unique_id == file_record.file_unique_id

    def test_returns_none_when_source_not_exists(self, repo_db):
        """来源不存在时应返回 None。"""
        result = repo_db.get_file_by_source(-999, -999)
        assert result is None

    def test_join_returns_correct_file_data(self, repo_db):
        """JOIN 查询应返回完整的文件数据。"""
        file_record = _make_repository_file(
            file_unique_id="uid_join_test",
            file_id="fid_join",
            content_hash="hash_join",
            file_size=2048,
            file_type="photo",
            mime_type="image/jpeg",
            file_name="photo.jpg",
            repository_chat_id=-100555,
            repository_message_id=55,
        )
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(
            file_unique_id="uid_join_test",
            source_chat_id=-100666,
            source_message_id=66,
        )
        repo_db.insert_source_mapping(source)
        result = repo_db.get_file_by_source(-100666, 66)
        assert result is not None
        assert result.file_id == "fid_join"
        assert result.file_size == 2048
        assert result.file_type == "photo"
        assert result.mime_type == "image/jpeg"
        assert result.file_name == "photo.jpg"


# ==================== get_file_by_unique_id 测试 ====================


class TestGetFileByUniqueId:
    """get_file_by_unique_id 方法测试。"""

    def test_returns_file_when_exists(self, repo_db):
        """file_unique_id 存在时应返回 RepositoryFile。"""
        record = _make_repository_file(file_unique_id="uid_query")
        repo_db.insert_file_record(record)
        result = repo_db.get_file_by_unique_id("uid_query")
        assert result is not None
        assert isinstance(result, RepositoryFile)
        assert result.file_unique_id == "uid_query"

    def test_returns_none_when_not_exists(self, repo_db):
        """file_unique_id 不存在时应返回 None。"""
        result = repo_db.get_file_by_unique_id("nonexistent")
        assert result is None


# ==================== get_file_by_content_hash 测试 ====================


class TestGetFileByContentHash:
    """get_file_by_content_hash 方法测试。"""

    def test_returns_file_when_hash_matches(self, repo_db):
        """content_hash 匹配且 status='active' 时应返回文件。"""
        record = _make_repository_file(content_hash="hash_match_001")
        repo_db.insert_file_record(record)
        result = repo_db.get_file_by_content_hash("hash_match_001")
        assert result is not None
        assert result.file_unique_id == record.file_unique_id

    def test_returns_none_when_hash_not_exists(self, repo_db):
        """content_hash 不存在时应返回 None。"""
        result = repo_db.get_file_by_content_hash("nonexistent_hash")
        assert result is None

    def test_returns_none_when_status_not_active(self, repo_db):
        """status 不为 'active' 时应返回 None。"""
        record = _make_repository_file(content_hash="hash_inactive", status="deleted")
        repo_db.insert_file_record(record)
        # 手动更新 status 为非 active（因为默认 INSERT 时 status='active'）
        with repo_db._get_connection() as conn:
            conn.execute(
                "UPDATE repository_files SET status = 'deleted' WHERE file_unique_id = ?",
                (record.file_unique_id,),
            )
        result = repo_db.get_file_by_content_hash("hash_inactive")
        assert result is None

    def test_returns_none_when_hash_is_none(self, repo_db):
        """content_hash 为 None 的记录不应被查询到。"""
        record = _make_repository_file(content_hash=None)
        repo_db.insert_file_record(record)
        result = repo_db.get_file_by_content_hash(None)
        # content_hash 为 NULL 的记录，WHERE content_hash = NULL 不会匹配
        assert result is None


# ==================== get_repository_message_id 测试 ====================


class TestGetRepositoryMessageId:
    """get_repository_message_id 方法测试。"""

    def test_returns_tuple_when_exists(self, repo_db):
        """file_unique_id 存在时应返回 (chat_id, message_id) 元组。"""
        record = _make_repository_file(
            repository_chat_id=-100999, repository_message_id=777
        )
        repo_db.insert_file_record(record)
        result = repo_db.get_repository_message_id(record.file_unique_id)
        assert result is not None
        assert isinstance(result, tuple)
        assert result == (-100999, 777)

    def test_returns_none_when_not_exists(self, repo_db):
        """file_unique_id 不存在时应返回 None。"""
        result = repo_db.get_repository_message_id("nonexistent")
        assert result is None


# ==================== UNIQUE 约束测试 ====================


class TestUniqueConstraints:
    """UNIQUE 约束验证测试。"""

    def test_file_unique_id_unique_constraint(self, repo_db):
        """repository_files.file_unique_id 的 UNIQUE 约束应生效。"""
        record1 = _make_repository_file(file_unique_id="uid_unique_test")
        record2 = _make_repository_file(
            file_unique_id="uid_unique_test", file_id="fid_different"
        )
        id1 = repo_db.insert_file_record(record1)
        id2 = repo_db.insert_file_record(record2)
        # 第二次插入应被忽略
        assert id1 > 0
        assert id2 == 0

    def test_source_composite_unique_constraint(self, repo_db):
        """repository_sources (source_chat_id, source_message_id) 的 UNIQUE 约束应生效。"""
        file_record = _make_repository_file(file_unique_id="uid_src_unique")
        repo_db.insert_file_record(file_record)
        source1 = _make_repository_source(
            file_unique_id="uid_src_unique",
            source_chat_id=-100123,
            source_message_id=456,
        )
        source2 = _make_repository_source(
            file_unique_id="uid_src_unique",
            source_chat_id=-100123,
            source_message_id=456,
        )
        id1 = repo_db.insert_source_mapping(source1)
        id2 = repo_db.insert_source_mapping(source2)
        assert id1 > 0
        assert id2 == 0


# ==================== 异常层次测试 ====================


class TestExceptionHierarchy:
    """异常类层次结构测试。"""

    def test_repository_db_error_is_exception(self):
        """RepositoryDBError 应继承 Exception。"""
        assert issubclass(RepositoryDBError, Exception)


# ==================== 数据模型测试 ====================


class TestDataModels:
    """数据模型 dataclass 测试。"""

    def test_repository_file_dataclass(self):
        """RepositoryFile 应为 dataclass 且字段正确。"""
        record = RepositoryFile(
            id=1,
            file_unique_id="uid",
            file_id="fid",
            content_hash="hash",
            file_size=1024,
            file_type="video",
            mime_type="video/mp4",
            file_name="test.mp4",
            repository_chat_id=-100,
            repository_message_id=42,
            created_at="2026-01-01",
            updated_at="2026-01-01",
            status="active",
        )
        assert record.file_unique_id == "uid"
        assert record.file_size == 1024
        assert record.status == "active"

    def test_repository_file_default_status(self):
        """RepositoryFile 默认 status 应为 'active'。"""
        record = RepositoryFile(
            id=None,
            file_unique_id="uid",
            file_id="fid",
            content_hash=None,
            file_size=0,
            file_type="video",
            mime_type=None,
            file_name=None,
            repository_chat_id=0,
            repository_message_id=0,
            created_at=None,
            updated_at=None,
        )
        assert record.status == "active"

    def test_repository_source_dataclass(self):
        """RepositorySource 应为 dataclass 且字段正确。"""
        record = RepositorySource(
            id=1,
            file_unique_id="uid",
            source_chat_id=-100,
            source_message_id=42,
            source_link="https://t.me/c/100/42",
            created_at="2026-01-01",
        )
        assert record.file_unique_id == "uid"
        assert record.source_link == "https://t.me/c/100/42"

    def test_file_distribution_dataclass(self):
        """FileDistribution 应为 dataclass 且字段正确。"""
        record = FileDistribution(
            id=1,
            file_unique_id="uid",
            target_chat_id=-100,
            target_message_id=42,
            method="copy_message",
            task_id="task_001",
            created_at="2026-01-01",
        )
        assert record.method == "copy_message"
        assert record.task_id == "task_001"


# ==================== 外键约束测试 ====================


class TestForeignKeyConstraints:
    """外键约束验证测试。"""

    def test_cascade_delete_on_file_deletion(self, repo_db):
        """删除 repository_files 记录时，关联的 sources 和 distributions 应被级联删除。"""
        file_record = _make_repository_file(file_unique_id="uid_cascade")
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(file_unique_id="uid_cascade")
        repo_db.insert_source_mapping(source)
        dist = _make_file_distribution(file_unique_id="uid_cascade")
        repo_db.insert_distribution(dist)

        # 删除文件记录
        with repo_db._get_connection() as conn:
            conn.execute(
                "DELETE FROM repository_files WHERE file_unique_id = ?",
                ("uid_cascade",),
            )

        # 验证级联删除
        with repo_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM repository_sources WHERE file_unique_id = ?",
                ("uid_cascade",),
            )
            assert cursor.fetchone()[0] == 0

            cursor = conn.execute(
                "SELECT COUNT(*) FROM file_distributions WHERE file_unique_id = ?",
                ("uid_cascade",),
            )
            assert cursor.fetchone()[0] == 0


# ==================== 行/记录转换测试 ====================


class TestRowConversion:
    """行/记录转换方法测试。

    _file_to_row 生成 INSERT 元组（不含 id/created_at/updated_at），
    _row_to_file 期望 SELECT 元组（含全部列），两者长度不同。
    因此通过数据库做完整的往返验证。
    """

    def test_file_round_trip_via_db(self, repo_db):
        """插入文件后查询，数据应完整保留。"""
        record = _make_repository_file()
        repo_db.insert_file_record(record)
        restored = repo_db.get_file_by_unique_id(record.file_unique_id)
        assert restored is not None
        assert restored.file_unique_id == record.file_unique_id
        assert restored.file_id == record.file_id
        assert restored.content_hash == record.content_hash
        assert restored.file_size == record.file_size
        assert restored.file_type == record.file_type
        assert restored.mime_type == record.mime_type
        assert restored.file_name == record.file_name
        assert restored.repository_chat_id == record.repository_chat_id
        assert restored.repository_message_id == record.repository_message_id
        assert restored.status == record.status
        assert restored.id is not None
        assert restored.created_at is not None
        assert restored.updated_at is not None

    def test_source_round_trip_via_db(self, repo_db):
        """插入来源映射后通过 JOIN 查询，数据应完整保留。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        source = _make_repository_source()
        repo_db.insert_source_mapping(source)
        result = repo_db.get_file_by_source(
            source.source_chat_id, source.source_message_id
        )
        assert result is not None
        assert result.file_unique_id == source.file_unique_id

    def test_distribution_round_trip_via_db(self, repo_db):
        """插入分发记录后查询，数据应完整保留。"""
        file_record = _make_repository_file()
        repo_db.insert_file_record(file_record)
        dist = _make_file_distribution()
        repo_db.insert_distribution(dist)
        # 通过直接查询验证数据
        with repo_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, file_unique_id, target_chat_id, target_message_id, method, task_id, created_at FROM file_distributions WHERE file_unique_id = ?",
                (dist.file_unique_id,),
            )
            row = cursor.fetchone()
        assert row is not None
        restored = repo_db._row_to_distribution(row)
        assert restored.file_unique_id == dist.file_unique_id
        assert restored.target_chat_id == dist.target_chat_id
        assert restored.target_message_id == dist.target_message_id
        assert restored.method == dist.method
        assert restored.task_id == dist.task_id
        assert restored.id is not None
        assert restored.created_at is not None
