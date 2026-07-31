# coding=UTF-8
"""Repository 相关 SQLModel 表模型单元测试。

覆盖 RepositoryFileRecord、RepositorySourceRecord、FileDistributionRecord 的
CRUD 操作、UNIQUE 约束、外键关联、索引字段、跨表 JOIN 查询等场景。
使用内存数据库（sqlite+aiosqlite:///:memory:）进行测试。
"""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from module.core import db
from module.core.repository.models import (
    FileDistributionRecord,
    RepositoryFileRecord,
    RepositorySourceRecord,
)


# ==================== Fixture ====================


@pytest_asyncio.fixture
async def repo_db():
    """提供使用内存数据库的异步会话。"""
    await db.init_db(":memory:")
    yield
    await db.close_db()


def _make_file_record(**overrides) -> RepositoryFileRecord:
    """创建 RepositoryFileRecord 测试数据。"""
    defaults = {
        "file_unique_id": "uid_001",
        "file_id": "fid_001",
        "content_hash": "hash_abc123",
        "file_size": 1024,
        "file_type": "video",
        "mime_type": "video/mp4",
        "file_name": "test.mp4",
        "repository_chat_id": -1001234567890,
        "repository_message_id": 42,
        "created_at": datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
        "status": "active",
    }
    defaults.update(overrides)
    return RepositoryFileRecord(**defaults)


def _make_source_record(**overrides) -> RepositorySourceRecord:
    """创建 RepositorySourceRecord 测试数据。"""
    defaults = {
        "file_unique_id": "uid_001",
        "source_chat_id": -1009876543210,
        "source_message_id": 100,
        "created_at": datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return RepositorySourceRecord(**defaults)


def _make_distribution_record(**overrides) -> FileDistributionRecord:
    """创建 FileDistributionRecord 测试数据。"""
    defaults = {
        "file_unique_id": "uid_001",
        "target_chat_id": -1001111111111,
        "target_message_id": 200,
        "method": "forward",
        "task_id": "task_001",
        "created_at": datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return FileDistributionRecord(**defaults)


# ==================== RepositoryFileRecord CRUD ====================


class TestRepositoryFileRecordCRUD:
    """RepositoryFileRecord CRUD 操作测试。"""

    async def test_create_file(self, repo_db):
        """创建仓库文件记录。"""
        record = _make_file_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.id is not None
            assert record.file_unique_id == "uid_001"
            assert record.file_id == "fid_001"
            assert record.content_hash == "hash_abc123"
            assert record.file_size == 1024
            assert record.file_type == "video"

    async def test_read_file(self, repo_db):
        """按 file_unique_id 读取仓库文件记录。"""
        record = _make_file_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(
                    RepositoryFileRecord.file_unique_id == "uid_001"
                )
            )
            found = result.scalars().first()
            assert found is not None
            assert found.file_name == "test.mp4"

    async def test_update_file(self, repo_db):
        """更新仓库文件记录。"""
        record = _make_file_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            record_id = record.id

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(RepositoryFileRecord.id == record_id)
            )
            found = result.scalars().first()
            found.status = "deleted"
            found.updated_at = datetime(2026, 7, 18, 13, 0, 0, tzinfo=timezone.utc)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(RepositoryFileRecord.id == record_id)
            )
            found = result.scalars().first()
            assert found.status == "deleted"
            assert found.updated_at == datetime(2026, 7, 18, 13, 0, 0)

    async def test_delete_file(self, repo_db):
        """删除仓库文件记录。"""
        record = _make_file_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            record_id = record.id

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(RepositoryFileRecord.id == record_id)
            )
            found = result.scalars().first()
            await session.delete(found)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(RepositoryFileRecord.id == record_id)
            )
            assert result.scalars().first() is None


# ==================== RepositoryFileRecord 约束 ====================


class TestRepositoryFileRecordConstraints:
    """RepositoryFileRecord 约束测试。"""

    async def test_file_unique_id_unique_constraint(self, repo_db):
        """file_unique_id UNIQUE 约束：重复插入应失败。"""
        record1 = _make_file_record(file_unique_id="uid_dup")
        record2 = _make_file_record(file_unique_id="uid_dup", file_id="fid_other")

        async with db.get_session() as session:
            session.add(record1)
            await session.commit()

        async with db.get_session() as session:
            session.add(record2)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_file_unique_id_index_query(self, repo_db):
        """file_unique_id 索引查询。"""
        async with db.get_session() as session:
            session.add(_make_file_record(file_unique_id="uid_001"))
            session.add(_make_file_record(file_unique_id="uid_002", file_id="fid_002"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(
                    RepositoryFileRecord.file_unique_id == "uid_002"
                )
            )
            found = result.scalars().first()
            assert found is not None
            assert found.file_id == "fid_002"

    async def test_content_hash_index_query(self, repo_db):
        """content_hash 索引查询（用于去重）。"""
        async with db.get_session() as session:
            session.add(_make_file_record(content_hash="hash_same"))
            session.add(
                _make_file_record(
                    file_unique_id="uid_002",
                    file_id="fid_002",
                    content_hash="hash_same",
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(
                    RepositoryFileRecord.content_hash == "hash_same"
                )
            )
            found = result.scalars().all()
            assert len(found) == 2

    async def test_file_id_index_query(self, repo_db):
        """file_id 索引查询。"""
        async with db.get_session() as session:
            session.add(_make_file_record(file_id="fid_search"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord).where(
                    RepositoryFileRecord.file_id == "fid_search"
                )
            )
            found = result.scalars().first()
            assert found is not None


# ==================== RepositoryFileRecord 默认值 ====================


class TestRepositoryFileRecordDefaults:
    """RepositoryFileRecord 默认值测试。"""

    async def test_default_values(self, repo_db):
        """验证字段的默认值。"""
        record = RepositoryFileRecord(
            file_unique_id="uid_min",
            file_id="fid_min",
            file_size=2048,
            file_type="photo",
            repository_chat_id=-1001234567890,
            repository_message_id=99,
        )
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.content_hash is None
            assert record.mime_type is None
            assert record.file_name is None
            assert record.created_at is None
            assert record.updated_at is None
            assert record.status == "active"


# ==================== RepositorySourceRecord CRUD ====================


class TestRepositorySourceRecordCRUD:
    """RepositorySourceRecord CRUD 操作测试。"""

    async def test_create_source(self, repo_db):
        """创建来源映射记录。"""
        record = _make_source_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.id is not None
            assert record.file_unique_id == "uid_001"
            assert record.source_chat_id == -1009876543210
            assert record.source_message_id == 100

    async def test_source_unique_constraint(self, repo_db):
        """(source_chat_id, source_message_id) UNIQUE 约束。"""
        record1 = _make_source_record()
        record2 = _make_source_record(file_unique_id="uid_002")

        async with db.get_session() as session:
            session.add(record1)
            await session.commit()

        async with db.get_session() as session:
            session.add(record2)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_source_different_chat_same_message(self, repo_db):
        """不同 chat_id + 相同 message_id 不违反 UNIQUE 约束。"""
        record1 = _make_source_record(source_chat_id=-1001111111111)
        record2 = _make_source_record(
            file_unique_id="uid_002",
            source_chat_id=-1002222222222,
        )

        async with db.get_session() as session:
            session.add(record1)
            session.add(record2)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(func.count()).select_from(RepositorySourceRecord)
            )
            assert result.scalar() == 2

    async def test_source_different_message_same_chat(self, repo_db):
        """相同 chat_id + 不同 message_id 不违反 UNIQUE 约束。"""
        record1 = _make_source_record(source_message_id=100)
        record2 = _make_source_record(
            file_unique_id="uid_002",
            source_message_id=200,
        )

        async with db.get_session() as session:
            session.add(record1)
            session.add(record2)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(func.count()).select_from(RepositorySourceRecord)
            )
            assert result.scalar() == 2

    async def test_source_index_query(self, repo_db):
        """file_unique_id 索引查询来源映射。"""
        async with db.get_session() as session:
            session.add(_make_source_record(file_unique_id="uid_search"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositorySourceRecord).where(
                    RepositorySourceRecord.file_unique_id == "uid_search"
                )
            )
            found = result.scalars().first()
            assert found is not None


# ==================== FileDistributionRecord CRUD ====================


class TestFileDistributionRecordCRUD:
    """FileDistributionRecord CRUD 操作测试。"""

    async def test_create_distribution(self, repo_db):
        """创建分发记录。"""
        record = _make_distribution_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.id is not None
            assert record.file_unique_id == "uid_001"
            assert record.target_chat_id == -1001111111111
            assert record.method == "forward"
            assert record.task_id == "task_001"

    async def test_distribution_optional_fields(self, repo_db):
        """可选字段为 None 时应正常存储。"""
        record = FileDistributionRecord(
            file_unique_id="uid_min",
            target_chat_id=-1001111111111,
            method="copy",
        )
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.target_message_id is None
            assert record.task_id is None
            assert record.created_at is None

    async def test_distribution_task_id_index(self, repo_db):
        """task_id 索引查询分发记录。"""
        async with db.get_session() as session:
            session.add(
                _make_distribution_record(
                    task_id="task_search", file_unique_id="uid_001"
                )
            )
            session.add(
                _make_distribution_record(
                    task_id="task_search",
                    file_unique_id="uid_002",
                    target_chat_id=-1002222222222,
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(FileDistributionRecord).where(
                    FileDistributionRecord.task_id == "task_search"
                )
            )
            found = result.scalars().all()
            assert len(found) == 2

    async def test_distribution_file_unique_id_index(self, repo_db):
        """file_unique_id 索引查询分发记录。"""
        async with db.get_session() as session:
            session.add(_make_distribution_record(file_unique_id="uid_dist"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(FileDistributionRecord).where(
                    FileDistributionRecord.file_unique_id == "uid_dist"
                )
            )
            found = result.scalars().first()
            assert found is not None

    async def test_multiple_methods(self, repo_db):
        """同一文件可分发到不同目标且使用不同方法。"""
        async with db.get_session() as session:
            session.add(
                _make_distribution_record(
                    target_chat_id=-1001111111111,
                    method="forward",
                    target_message_id=200,
                )
            )
            session.add(
                _make_distribution_record(
                    file_unique_id="uid_002",
                    target_chat_id=-1002222222222,
                    method="copy",
                    target_message_id=300,
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(select(FileDistributionRecord))
            dists = result.scalars().all()
            methods = {d.method for d in dists}
            assert methods == {"forward", "copy"}


# ==================== 跨表 JOIN 查询 ====================


class TestRepositoryCrossTableQuery:
    """Repository 相关表的跨表 JOIN 查询测试。"""

    async def test_file_with_sources_join(self, repo_db):
        """文件与来源映射 JOIN 查询。"""
        async with db.get_session() as session:
            session.add(_make_file_record())
            session.add(_make_source_record())
            session.add(
                _make_source_record(
                    file_unique_id="uid_001",
                    source_chat_id=-1002222222222,
                    source_message_id=200,
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(
                    RepositoryFileRecord.file_unique_id,
                    func.count(RepositorySourceRecord.id).label("source_count"),
                )
                .join(
                    RepositorySourceRecord,
                    RepositoryFileRecord.file_unique_id
                    == RepositorySourceRecord.file_unique_id,
                )
                .group_by(RepositoryFileRecord.file_unique_id)
            )
            row = result.first()
            assert row is not None
            assert row.file_unique_id == "uid_001"
            assert row.source_count == 2

    async def test_file_with_distributions_join(self, repo_db):
        """文件与分发记录 JOIN 查询。"""
        async with db.get_session() as session:
            session.add(_make_file_record())
            session.add(_make_distribution_record())
            session.add(
                _make_distribution_record(
                    file_unique_id="uid_001",
                    target_chat_id=-1002222222222,
                    method="copy",
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(
                    RepositoryFileRecord.file_unique_id,
                    func.count(FileDistributionRecord.id).label("dist_count"),
                )
                .join(
                    FileDistributionRecord,
                    RepositoryFileRecord.file_unique_id
                    == FileDistributionRecord.file_unique_id,
                )
                .group_by(RepositoryFileRecord.file_unique_id)
            )
            row = result.first()
            assert row is not None
            assert row.dist_count == 2

    async def test_find_files_by_source_chat(self, repo_db):
        """通过来源 chat_id 查找文件（跨表查询场景）。"""
        async with db.get_session() as session:
            session.add(_make_file_record())
            session.add(_make_source_record())
            session.add(
                _make_source_record(
                    file_unique_id="uid_001",
                    source_chat_id=-1002222222222,
                    source_message_id=200,
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(RepositoryFileRecord)
                .join(
                    RepositorySourceRecord,
                    RepositoryFileRecord.file_unique_id
                    == RepositorySourceRecord.file_unique_id,
                )
                .where(RepositorySourceRecord.source_chat_id == -1009876543210)
            )
            files = result.scalars().all()
            assert len(files) == 1
            assert files[0].file_unique_id == "uid_001"


# ==================== RepositoryFileRecord 边界情况 ====================


class TestRepositoryFileRecordEdgeCases:
    """RepositoryFileRecord 边界情况测试。"""

    async def test_large_file_size(self, repo_db):
        """大文件（>2GB）应正常存储。"""
        large_size = 5 * 1024 * 1024 * 1024  # 5GB
        record = _make_file_record(file_size=large_size)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.file_size == large_size

    async def test_negative_chat_id(self, repo_db):
        """Telegram 频道 chat_id 为负数。"""
        record = _make_file_record(repository_chat_id=-1001234567890)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.repository_chat_id == -1001234567890

    async def test_null_content_hash(self, repo_db):
        """content_hash 为 None（文件未计算哈希时）。"""
        record = _make_file_record(content_hash=None)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.content_hash is None
