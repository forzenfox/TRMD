# coding=UTF-8
"""Task 相关 SQLModel 表模型单元测试。

覆盖 TaskRecord、TaskItemRecord 的 CRUD 操作、
外键约束、JSON 字段、索引字段、默认值等场景。
使用内存数据库（sqlite+aiosqlite:///:memory:）进行测试。
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from module.core import db
from module.core.task.models import TaskItemRecord, TaskRecord


# ==================== Fixture ====================


@pytest_asyncio.fixture
async def task_db():
    """提供使用内存数据库的异步会话。

    每个测试函数获取独立的内存引擎，测试结束后关闭重置。
    """
    await db.init_db(":memory:")
    yield
    await db.close_db()


def _make_task_record(**overrides) -> TaskRecord:
    """创建 TaskRecord 测试数据。"""
    defaults = {
        "id": "task_001",
        "task_type": "download",
        "status": "pending",
        "chat_id": -1001234567890,
        "chat_username": "test_channel",
        "chat_type": "channel",
        "params": {"source_identifier": "@channel", "range_mode": "id_range"},
        "created_at": datetime(2026, 7, 18, 4, 0, 0, tzinfo=timezone.utc),
        "total_size_bytes": 0,
    }
    defaults.update(overrides)
    return TaskRecord(**defaults)


def _make_task_item_record(**overrides) -> TaskItemRecord:
    """创建 TaskItemRecord 测试数据。"""
    defaults = {
        "id": "item_001",
        "task_id": "task_001",
        "status": "pending",
        "source_message_id": 96414,
        "source_file_path": None,
        "target_chat_id": None,
        "file_path": "/downloads/test.mp4",
        "file_size": 1024000,
        "created_at": datetime(2026, 7, 18, 4, 0, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 7, 18, 4, 0, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return TaskItemRecord(**defaults)


# ==================== TaskRecord CRUD ====================


class TestTaskRecordCRUD:
    """TaskRecord CRUD 操作测试。"""

    async def test_create_task(self, task_db):
        """创建任务记录并验证所有字段。"""
        record = _make_task_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.id == "task_001"
            assert record.task_type == "download"
            assert record.status == "pending"
            assert record.params == {
                "source_identifier": "@channel",
                "range_mode": "id_range",
            }
            assert record.created_at == datetime(2026, 7, 18, 4, 0, 0)

    async def test_read_task(self, task_db):
        """按主键读取任务记录。"""
        record = _make_task_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            found = result.scalars().first()
            assert found is not None
            assert found.task_type == "download"

    async def test_update_task(self, task_db):
        """更新任务状态和计数器。"""
        record = _make_task_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            found = result.scalars().first()
            found.status = "completed"
            found.completed_at = datetime(2026, 7, 18, 4, 5, 0, tzinfo=timezone.utc)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            found = result.scalars().first()
            assert found.status == "completed"
            assert found.completed_at == datetime(2026, 7, 18, 4, 5, 0)

    async def test_delete_task(self, task_db):
        """删除任务记录。"""
        record = _make_task_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            found = result.scalars().first()
            await session.delete(found)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            found = result.scalars().first()
            assert found is None

    async def test_count_tasks(self, task_db):
        """统计任务数量。"""
        async with db.get_session() as session:
            for i in range(5):
                session.add(_make_task_record(id=f"task_{i:03d}"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(select(func.count()).select_from(TaskRecord))
            assert result.scalar() == 5


# ==================== TaskRecord JSON 字段 ====================


class TestTaskRecordJSON:
    """TaskRecord JSON 字段（params、extra）测试。"""

    async def test_params_json_dict(self, task_db):
        """params 字段存储和读取 JSON dict。"""
        params = {
            "source_identifier": "@channel",
            "range_mode": "id_range",
            "min_id": 100,
            "max_id": 200,
            "media_types": ["video", "photo"],
        }
        record = _make_task_record(params=params)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.params["media_types"] == ["video", "photo"]
            assert record.params["min_id"] == 100

    async def test_extra_json_dict(self, task_db):
        """extra 字段存储和读取 JSON dict。"""
        extra = {"retry_history": [1, 2, 3], "note": "test"}
        record = _make_task_record(extra=extra)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.extra["retry_history"] == [1, 2, 3]
            assert record.extra["note"] == "test"

    async def test_params_empty_dict(self, task_db):
        """params 为空 dict 应正常存储。"""
        record = _make_task_record(params={})
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.params == {}

    async def test_extra_default_empty_dict(self, task_db):
        """extra 默认值应为空 dict。"""
        record = _make_task_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.extra == {}


# ==================== TaskRecord 索引查询 ====================


class TestTaskRecordIndex:
    """TaskRecord 索引字段查询测试。"""

    async def test_query_by_status_index(self, task_db):
        """按 status 索引查询任务。"""
        async with db.get_session() as session:
            session.add(_make_task_record(id="task_001", status="pending"))
            session.add(_make_task_record(id="task_002", status="completed"))
            session.add(_make_task_record(id="task_003", status="pending"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.status == "pending")
            )
            pending = result.scalars().all()
            assert len(pending) == 2
            assert {t.id for t in pending} == {"task_001", "task_003"}

    async def test_query_by_created_at_index(self, task_db):
        """按 created_at 索引查询任务。"""
        async with db.get_session() as session:
            session.add(
                _make_task_record(
                    id="task_001",
                    created_at=datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc),
                )
            )
            session.add(
                _make_task_record(
                    id="task_002",
                    created_at=datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(
                    TaskRecord.created_at
                    >= datetime(2026, 7, 18, 11, 0, 0, tzinfo=timezone.utc)
                )
            )
            found = result.scalars().all()
            assert len(found) == 1
            assert found[0].id == "task_002"


# ==================== TaskRecord 默认值 ====================


class TestTaskRecordDefaults:
    """TaskRecord 默认值测试。"""

    async def test_default_values(self, task_db):
        """验证数值字段的默认值。"""
        record = TaskRecord(
            id="task_defaults",
            task_type="forward",
            status="pending",
            chat_id=-1001234567890,
            created_at=datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
        )
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.total_size_bytes == 0
            assert record.retry_count == 0
            assert record.max_retry_count == 5
            assert record.started_at is None
            assert record.completed_at is None
            assert record.error_message is None
            assert record.params == {}
            assert record.extra == {}


# ==================== TaskItemRecord CRUD ====================


class TestTaskItemRecordCRUD:
    """TaskItemRecord CRUD 操作测试。"""

    async def test_create_task_item(self, task_db):
        """创建子任务记录。"""
        # 先创建父任务
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        item = _make_task_item_record()
        async with db.get_session() as session:
            session.add(item)
            await session.commit()
            await session.refresh(item)

            assert item.id == "item_001"
            assert item.task_id == "task_001"
            assert item.status == "pending"
            assert item.file_size == 1024000

    async def test_task_item_foreign_key(self, task_db):
        """task_id 外键应关联到 tm_tasks 表。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        item = _make_task_item_record()
        async with db.get_session() as session:
            session.add(item)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(TaskItemRecord.id == "item_001")
            )
            found = result.scalars().first()
            assert found is not None
            assert found.task_id == "task_001"

    async def test_task_item_foreign_key_constraint(self, task_db):
        """task_id 外键约束：引用不存在的任务应失败。"""
        item = _make_task_item_record(task_id="nonexistent_task")
        async with db.get_session() as session:
            session.add(item)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_delete_task_fails_with_items_fk_restrict(self, task_db):
        """foreign_keys=ON 时，删除有子任务的父记录应被 RESTRICT 阻止。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            session.add(_make_task_item_record())
            await session.commit()

        # 尝试删除父任务：外键 RESTRICT 应阻止删除
        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            task = result.scalars().first()
            await session.delete(task)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_delete_items_then_task(self, task_db):
        """先删除子任务再删除父任务应成功。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            session.add(_make_task_item_record())
            await session.commit()

        # 先删除子任务
        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(TaskItemRecord.id == "item_001")
            )
            item = result.scalars().first()
            await session.delete(item)
            await session.commit()

        # 再删除父任务
        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            task = result.scalars().first()
            await session.delete(task)
            await session.commit()

        # 验证均被删除
        async with db.get_session() as session:
            assert (
                await session.execute(select(func.count()).select_from(TaskRecord))
            ).scalar() == 0
            assert (
                await session.execute(select(func.count()).select_from(TaskItemRecord))
            ).scalar() == 0

    async def test_query_items_by_task_id_index(self, task_db):
        """按 task_id 索引查询子任务。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            session.add(_make_task_item_record(id="item_001"))
            session.add(_make_task_item_record(id="item_002", source_message_id=96415))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(TaskItemRecord.task_id == "task_001")
            )
            items = result.scalars().all()
            assert len(items) == 2

    async def test_query_items_by_status_index(self, task_db):
        """按 status 索引查询子任务。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            session.add(_make_task_item_record(id="item_001", status="pending"))
            session.add(_make_task_item_record(id="item_002", status="completed"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(TaskItemRecord.status == "completed")
            )
            items = result.scalars().all()
            assert len(items) == 1
            assert items[0].id == "item_002"


# ==================== TaskItemRecord 字段 ====================


class TestTaskItemRecordFields:
    """TaskItemRecord 字段测试。"""

    async def _ensure_parent_task(self):
        """确保父任务记录存在。"""
        async with db.get_session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == "task_001")
            )
            if result.scalars().first() is None:
                session.add(_make_task_record())
                await session.commit()

    async def test_file_sha256_index(self, task_db):
        """file_sha256 索引查询。"""
        await self._ensure_parent_task()

        async with db.get_session() as session:
            session.add(
                _make_task_item_record(id="item_001", file_sha256="abc123def456")
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(
                    TaskItemRecord.file_sha256 == "abc123def456"
                )
            )
            found = result.scalars().first()
            assert found is not None

    async def test_file_unique_id_index(self, task_db):
        """file_unique_id 索引查询。"""
        await self._ensure_parent_task()

        async with db.get_session() as session:
            session.add(
                _make_task_item_record(id="item_001", file_unique_id="uniq_001")
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(
                    TaskItemRecord.file_unique_id == "uniq_001"
                )
            )
            found = result.scalars().first()
            assert found is not None

    async def test_media_group_id_field(self, task_db):
        """media_group_id 预留字段应可正常读写。"""
        await self._ensure_parent_task()

        async with db.get_session() as session:
            item = _make_task_item_record(id="item_001", media_group_id="mg_12345")
            session.add(item)
            await session.commit()
            await session.refresh(item)
            assert item.media_group_id == "mg_12345"

    async def test_media_group_id_null_by_default(self, task_db):
        """media_group_id 默认为 None。"""
        await self._ensure_parent_task()

        async with db.get_session() as session:
            item = _make_task_item_record(id="item_001")
            session.add(item)
            await session.commit()
            await session.refresh(item)
            assert item.media_group_id is None

    async def test_extra_json_field(self, task_db):
        """extra JSON 字段存储。"""
        await self._ensure_parent_task()

        async with db.get_session() as session:
            item = _make_task_item_record(
                id="item_001", extra={"download_speed": 1024.5}
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            assert item.extra["download_speed"] == 1024.5

    async def test_task_item_all_optional_fields(self, task_db):
        """所有可选字段为 None 时应正常存储。"""
        await self._ensure_parent_task()

        async with db.get_session() as session:
            item = TaskItemRecord(
                id="item_minimal",
                task_id="task_001",
                created_at=datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)

            assert item.status == "pending"
            assert item.source_message_id is None
            assert item.source_file_path is None
            assert item.target_chat_id is None
            assert item.file_path is None
            assert item.file_size == 0
            assert item.file_sha256 is None
            assert item.telegram_file_id is None
            assert item.file_unique_id is None
            assert item.uploaded_message_id is None
            assert item.retry_count == 0
            assert item.error_code is None
            assert item.error_message is None
            assert item.media_group_id is None


# ==================== TaskItem 批量操作 ====================


class TestTaskItemBatch:
    """TaskItemRecord 批量操作测试。"""

    async def test_batch_insert_items(self, task_db):
        """批量插入子任务记录。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            for i in range(10):
                session.add(
                    _make_task_item_record(
                        id=f"item_{i:03d}",
                        source_message_id=96414 + i,
                    )
                )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(func.count()).select_from(TaskItemRecord)
            )
            assert result.scalar() == 10

    async def test_query_items_by_media_group_id(self, task_db):
        """按 media_group_id 索引查询同一相册组的子任务。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            session.add(
                _make_task_item_record(
                    id="item_001",
                    media_group_id="mg_album_001",
                )
            )
            session.add(
                _make_task_item_record(
                    id="item_002",
                    media_group_id="mg_album_001",
                )
            )
            session.add(
                _make_task_item_record(
                    id="item_003",
                    media_group_id="mg_album_002",
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(TaskItemRecord).where(
                    TaskItemRecord.media_group_id == "mg_album_001"
                )
            )
            items = result.scalars().all()
            assert len(items) == 2
            assert {i.id for i in items} == {"item_001", "item_002"}


# ==================== 跨表 JOIN 查询 ====================


class TestTaskCrossTableQuery:
    """Task 相关表的跨表 JOIN 查询测试。"""

    async def test_task_with_items_join(self, task_db):
        """任务与子任务 JOIN 查询。"""
        async with db.get_session() as session:
            session.add(_make_task_record())
            await session.commit()

        async with db.get_session() as session:
            session.add(_make_task_item_record(id="item_001", status="completed"))
            session.add(_make_task_item_record(id="item_002", status="failed"))
            await session.commit()

        async with db.get_session() as session:
            # JOIN 查询：获取任务及其子任务数
            result = await session.execute(
                select(
                    TaskRecord.id,
                    func.count(TaskItemRecord.id).label("item_count"),
                )
                .join(TaskItemRecord, TaskRecord.id == TaskItemRecord.task_id)
                .group_by(TaskRecord.id)
            )
            row = result.first()
            assert row
