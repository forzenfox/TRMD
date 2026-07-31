# coding=UTF-8
"""数据模型 v2 结构验证测试。

验证数据模型设计文档 v1.1 中 P0+P2 改造后的模型结构：
- TaskRecord 含 chat_id/chat_username/chat_type 独立列
- TaskRecord 不含已移除的 4 个汇总字段
- TaskItemRecord 含 source_message_id/source_file_path/target_chat_id
- TaskItemRecord 不含 source_id/source_link/target_id/last_progress_bytes
- TaskEventRecord 类已移除
- Task dataclass 含 total_items/skipped_count property
- RepositorySourceRecord 不含 source_link
- TokenRecordDB.revoked 无索引
"""

import pytest

from module.core import (
    RepositorySourceRecord,
    TaskItemRecord,
    TaskRecord,
    TokenRecordDB,
)


# ==================== TaskRecord 字段结构 ====================


class TestTaskRecordFields:
    """TaskRecord 字段结构验证。"""

    def test_task_record_has_chat_id_column(self):
        """TaskRecord 含 chat_id 独立列。"""
        assert "chat_id" in TaskRecord.model_fields

    def test_task_record_has_chat_username_column(self):
        """TaskRecord 含 chat_username 字段。"""
        assert "chat_username" in TaskRecord.model_fields

    def test_task_record_has_chat_type_column(self):
        """TaskRecord 含 chat_type 字段。"""
        assert "chat_type" in TaskRecord.model_fields

    def test_task_record_no_summary_fields(self):
        """TaskRecord 不含已移除的汇总字段。"""
        for legacy in ("total_items", "success_items", "failed_items", "skipped_items"):
            assert legacy not in TaskRecord.model_fields, f"不应存在字段: {legacy}"


# ==================== TaskItemRecord 字段结构 ====================


class TestTaskItemRecordFields:
    """TaskItemRecord 字段结构验证。"""

    def test_task_item_record_has_source_message_id(self):
        """TaskItemRecord 含 source_message_id。"""
        assert "source_message_id" in TaskItemRecord.model_fields

    def test_task_item_record_has_source_file_path(self):
        """TaskItemRecord 含 source_file_path。"""
        assert "source_file_path" in TaskItemRecord.model_fields

    def test_task_item_record_has_target_chat_id(self):
        """TaskItemRecord 含 target_chat_id。"""
        assert "target_chat_id" in TaskItemRecord.model_fields

    def test_task_item_record_no_legacy_fields(self):
        """TaskItemRecord 不含已移除字段。"""
        for legacy in (
            "source_id",
            "source_link",
            "target_id",
            "last_progress_bytes",
        ):
            assert legacy not in TaskItemRecord.model_fields, f"不应存在字段: {legacy}"


# ==================== TaskEventRecord 已移除 ====================


class TestTaskEventRecordRemoved:
    """TaskEventRecord 类已移除。"""

    def test_task_event_record_not_exported(self):
        """__init__.py 不应导出 TaskEventRecord。"""
        from module.core import __all__ as models_all

        assert "TaskEventRecord" not in models_all

    def test_task_event_record_import_fails(self):
        """直接从 task 模块导入 TaskEventRecord 应失败。"""
        with pytest.raises(ImportError):
            from module.core.task.models import TaskEventRecord  # noqa: F401


# ==================== Task dataclass property ====================


class TestTaskDataclassProperties:
    """Task dataclass 实时计算 property 验证。"""

    def test_task_total_items_property(self):
        """Task.total_items property 返回 len(items)。"""
        from module.core.task.manager import Task, TaskItem, TaskType

        task = Task(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        assert task.total_items == 0
        task.items.append(TaskItem(id="i1", task_id="test_task"))
        task.items.append(TaskItem(id="i2", task_id="test_task"))
        assert task.total_items == 2

    def test_task_success_count_pure_realtime(self):
        """success_count 纯实时计算。"""
        from module.core.task.manager import (
            ItemStatus,
            Task,
            TaskItem,
            TaskType,
        )

        task = Task(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        i1 = TaskItem(id="i1", task_id="test_task")
        i2 = TaskItem(id="i2", task_id="test_task")
        task.items = [i1, i2]
        assert task.success_count == 0
        i1.status = ItemStatus.SUCCESS
        assert task.success_count == 1
        i2.status = ItemStatus.SUCCESS
        assert task.success_count == 2

    def test_task_skipped_count_property(self):
        """skipped_count property 返回跳过的子任务数。"""
        from module.core.task.manager import (
            ItemStatus,
            Task,
            TaskItem,
            TaskType,
        )

        task = Task(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        i1 = TaskItem(id="i1", task_id="test_task", status=ItemStatus.SKIPPED)
        i2 = TaskItem(id="i2", task_id="test_task", status=ItemStatus.SUCCESS)
        task.items = [i1, i2]
        assert task.skipped_count == 1

    def test_task_no_summary_attributes(self):
        """Task dataclass 不应含已移除的汇总字段（但允许 property）。"""
        from module.core.task.manager import Task, TaskType

        task = Task(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        # dataclass 字段不应含汇总字段（property 不算 dataclass 字段）
        for legacy in (
            "total_items",
            "success_items",
            "failed_items",
            "skipped_items",
        ):
            assert legacy not in Task.__dataclass_fields__, (
                f"Task 不应含 dataclass 字段: {legacy}"
            )
            # 但 total_items/skipped_count 作为 property 应可访问
        assert task.total_items == 0
        assert task.skipped_count == 0


# ==================== RepositorySourceRecord 字段结构 ====================


class TestRepositorySourceRecordFields:
    """RepositorySourceRecord 字段结构验证。"""

    def test_repository_source_record_no_source_link(self):
        """RepositorySourceRecord 不含 source_link。"""
        assert "source_link" not in RepositorySourceRecord.model_fields


# ==================== TokenRecordDB 索引 ====================


class TestTokenRecordRevokedNoIndex:
    """TokenRecordDB.revoked 字段无索引验证。"""

    def test_token_revoked_no_index(self):
        """TokenRecordDB.revoked 字段不应有 index=True。"""
        revoked_field = TokenRecordDB.model_fields["revoked"]
        assert revoked_field is not None

        # 通过 SQLAlchemy 引擎建表并查询索引（最可靠）
        from sqlalchemy import create_engine, inspect

        engine = create_engine("sqlite:///:memory:")
        TokenRecordDB.metadata.create_all(engine)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("tokens")
        engine.dispose()

        # revoked 字段不应有单独索引
        revoked_indexes = [idx for idx in indexes if "revoked" in idx["name"].lower()]
        assert not revoked_indexes, f"revoked 字段不应有索引，但存在: {revoked_indexes}"


# ==================== P1 时间字段统一为 datetime ====================


class TestTimeFieldsUnified:
    """P1 改造回归测试：验证时间字段为 datetime 类型、cache_entries.chat_id 为 int。

    使用本地内存引擎（无 fixture 依赖）写入并读回，验证 SQLAlchemy 序列化/
    反序列化后字段类型符合 P1 改造要求。
    """

    def test_task_record_created_at_is_datetime(self):
        """TaskRecord.created_at 写入后读回应为 datetime 类型。"""
        from datetime import datetime, timezone

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:")
        TaskRecord.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        try:
            with Session(engine) as session:
                record = TaskRecord(
                    id="task_type_check",
                    task_type="download",
                    status="pending",
                    chat_id=-1001234567890,
                    created_at=now,
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                assert isinstance(record.created_at, datetime)
        finally:
            engine.dispose()

    def test_cache_entry_record_expires_at_is_datetime(self):
        """CacheEntryRecord.expires_at 写入后读回应为 datetime 类型。"""
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from module.core.cache.models import CacheEntryRecord

        engine = create_engine("sqlite:///:memory:")
        CacheEntryRecord.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        try:
            with Session(engine) as session:
                record = CacheEntryRecord(
                    cache_key="type_check",
                    cache_type="test",
                    payload=b"data",
                    expires_at=now + timedelta(seconds=600),
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                assert isinstance(record.expires_at, datetime)
        finally:
            engine.dispose()

    def test_token_record_db_created_at_is_datetime(self):
        """TokenRecordDB.created_at 写入后读回应为 datetime 类型。"""
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:")
        TokenRecordDB.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        try:
            with Session(engine) as session:
                record = TokenRecordDB(
                    token="tk_type_check",
                    created_at=now,
                    expires_at=now + timedelta(seconds=3600),
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                assert isinstance(record.created_at, datetime)
        finally:
            engine.dispose()

    def test_cache_entry_chat_id_is_int(self):
        """CacheEntryRecord.chat_id 写入 int 后读回应为 int 类型。"""
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from module.core.cache.models import CacheEntryRecord

        engine = create_engine("sqlite:///:memory:")
        CacheEntryRecord.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        try:
            with Session(engine) as session:
                record = CacheEntryRecord(
                    cache_key="chat_id_type_check",
                    cache_type="test",
                    chat_id=-1001234567890,
                    payload=b"data",
                    expires_at=now + timedelta(seconds=600),
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                assert isinstance(record.chat_id, int)
                assert record.chat_id == -1001234567890
        finally:
            engine.dispose()

    def test_task_items_generic_annotation(self):
        """Task.items 类型注解应为 list[TaskItem]。"""
        from typing import get_type_hints

        from module.core.task.manager import Task, TaskItem

        hints = get_type_hints(Task)
        items_hint = hints.get("items")
        assert items_hint is not None, "Task.items 应有类型注解"
        args = getattr(items_hint, "__args__", None)
        assert args is not None and TaskItem in args, (
            f"expected list[TaskItem], got {items_hint}"
        )
