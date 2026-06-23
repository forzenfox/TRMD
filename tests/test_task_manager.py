# coding=UTF-8
"""TaskManager 单元测试

覆盖场景：
- 任务创建与状态转换
- 任务队列与并发调度
- 取消任务
- 重试任务
- 子任务状态管理
- 资源保护（大小阈值、磁盘空间）
- SQLite 持久化
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from module.core.task_manager import (
    TaskManager,
    Task,
    TaskItem,
    TaskType,
    TaskStatus,
    ItemStatus,
    InvalidStateTransition,
)


@pytest.fixture
def db_path():
    """创建临时数据库路径。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest.fixture
def task_manager(db_path):
    """创建 TaskManager 实例。"""
    return TaskManager(db_path=db_path, max_concurrent_tasks=2)


# ============================================================
# 测试：Task 数据模型
# ============================================================


class TestTaskModel:
    """测试 Task 数据类。"""

    def test_create_download_task(self):
        """测试创建下载任务。"""
        task = Task(
            task_id="task_001",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(100, 200),
            status=TaskStatus.PENDING,
        )
        assert task.task_id == "task_001"
        assert task.task_type == TaskType.DOWNLOAD
        assert task.chat_id == -1001234567890
        assert task.message_range == (100, 200)
        assert task.status == TaskStatus.PENDING
        assert task.items == []
        assert task.retry_count == 0
        assert task.total_size == 0

    def test_create_forward_task(self):
        """测试创建转发任务。"""
        task = Task(
            task_id="task_002",
            task_type=TaskType.FORWARD,
            chat_id=-1001234567890,
            target_chat_id=-1009876543210,
            message_range=(1, 50),
            status=TaskStatus.PENDING,
            delete_after_upload=True,
        )
        assert task.task_type == TaskType.FORWARD
        assert task.target_chat_id == -1009876543210
        assert task.delete_after_upload is True

    def test_create_upload_task(self):
        """测试创建上传任务。"""
        task = Task(
            task_id="task_003",
            task_type=TaskType.UPLOAD,
            chat_id=-1001234567890,
            file_paths=["/path/to/file1.mp4", "/path/to/file2.mp4"],
            status=TaskStatus.PENDING,
        )
        assert task.task_type == TaskType.UPLOAD
        assert len(task.file_paths) == 2

    def test_task_progress_calculation(self):
        """测试任务进度计算。"""
        task = Task(
            task_id="task_004",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            status=TaskStatus.PENDING,
        )
        task.items = [
            TaskItem(item_id="1", status=ItemStatus.SUCCESS),
            TaskItem(item_id="2", status=ItemStatus.SUCCESS),
            TaskItem(item_id="3", status=ItemStatus.FAILED),
            TaskItem(item_id="4", status=ItemStatus.PENDING),
        ]
        assert task.success_count == 2
        assert task.failed_count == 1
        assert task.pending_count == 1
        assert task.progress == 50.0  # 2/4 = 50%

    def test_task_progress_empty(self):
        """测试空任务进度。"""
        task = Task(
            task_id="task_005",
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            status=TaskStatus.PENDING,
        )
        assert task.progress == 0.0


# ============================================================
# 测试：TaskItem 数据模型
# ============================================================


class TestTaskItemModel:
    """测试 TaskItem 数据类。"""

    def test_create_task_item(self):
        """测试创建子任务项。"""
        item = TaskItem(
            item_id="msg_100",
            message_id=100,
            status=ItemStatus.PENDING,
            file_size=1024 * 1024,  # 1MB
        )
        assert item.item_id == "msg_100"
        assert item.message_id == 100
        assert item.status == ItemStatus.PENDING
        assert item.file_size == 1048576
        assert item.error_reason is None
        assert item.retry_count == 0

    def test_task_item_mark_success(self):
        """测试标记子任务成功。"""
        item = TaskItem(item_id="msg_100", status=ItemStatus.PENDING)
        item.mark_success()
        assert item.status == ItemStatus.SUCCESS

    def test_task_item_mark_failed(self):
        """测试标记子任务失败。"""
        item = TaskItem(item_id="msg_100", status=ItemStatus.RUNNING)
        item.mark_failed(reason="FloodWait")
        assert item.status == ItemStatus.FAILED
        assert item.error_reason == "FloodWait"
        assert item.retry_count == 1

    def test_task_item_mark_skipped(self):
        """测试标记子任务跳过。"""
        item = TaskItem(item_id="msg_100", status=ItemStatus.PENDING)
        item.mark_skipped(reason="已存在")
        assert item.status == ItemStatus.SKIPPED

    def test_task_item_can_retry(self):
        """测试可重试判定。"""
        # FloodWait 可重试
        item1 = TaskItem(
            item_id="msg_100", status=ItemStatus.FAILED, error_reason="FloodWait"
        )
        assert item1.can_retry() is True

        # 网络超时 可重试
        item2 = TaskItem(
            item_id="msg_101", status=ItemStatus.FAILED, error_reason="TimeoutError"
        )
        assert item2.can_retry() is True

        # 消息已删除 不可重试
        item3 = TaskItem(
            item_id="msg_102",
            status=ItemStatus.FAILED,
            error_reason="MESSAGE_ID_INVALID",
        )
        assert item3.can_retry() is False

        # 无权限 不可重试
        item4 = TaskItem(
            item_id="msg_103", status=ItemStatus.FAILED, error_reason="CHAT_FORBIDDEN"
        )
        assert item4.can_retry() is False


# ============================================================
# 测试：任务创建
# ============================================================


class TestCreateTask:
    """测试任务创建。"""

    @pytest.mark.asyncio
    async def test_create_download_task(self, task_manager):
        """测试创建下载任务。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(100, 200),
        )
        assert task.task_type == TaskType.DOWNLOAD
        assert task.chat_id == -1001234567890
        assert task.status == TaskStatus.PENDING
        assert task.task_id is not None

    @pytest.mark.asyncio
    async def test_create_forward_task(self, task_manager):
        """测试创建转发任务。"""
        task = await task_manager.create_task(
            task_type=TaskType.FORWARD,
            chat_id=-1001234567890,
            target_chat_id=-1009876543210,
            message_range=(1, 50),
            delete_after_upload=True,
        )
        assert task.task_type == TaskType.FORWARD
        assert task.target_chat_id == -1009876543210
        assert task.delete_after_upload is True

    @pytest.mark.asyncio
    async def test_create_upload_task(self, task_manager):
        """测试创建上传任务。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.mp4")
            Path(file_path).touch()
            task = await task_manager.create_task(
                task_type=TaskType.UPLOAD,
                chat_id=-1001234567890,
                file_paths=[file_path],
            )
            assert task.task_type == TaskType.UPLOAD
            assert len(task.file_paths) == 1

    @pytest.mark.asyncio
    async def test_create_task_persisted(self, task_manager, db_path):
        """测试任务创建后持久化到 SQLite。"""
        await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1


# ============================================================
# 测试：任务状态转换
# ============================================================


class TestTaskStateTransitions:
    """测试任务状态转换。"""

    @pytest.mark.asyncio
    async def test_pending_to_running(self, task_manager):
        """测试 pending → running。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        assert task.status == TaskStatus.PENDING
        await task_manager.start_task(task.task_id)
        assert task.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_pending_to_queued(self, task_manager):
        """测试并发已满时 pending → queued。"""
        # 创建 2 个任务并启动（max_concurrent_tasks=2）
        task1 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        task2 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(11, 20),
        )
        await task_manager.start_task(task1.task_id)
        await task_manager.start_task(task2.task_id)
        # 第 3 个任务应进入队列
        task3 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(21, 30),
        )
        await task_manager.start_task(task3.task_id)
        assert task3.status == TaskStatus.QUEUED

    @pytest.mark.asyncio
    async def test_running_to_completed(self, task_manager):
        """测试 running → completed。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        await task_manager.complete_task(task.task_id)
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_running_to_failed(self, task_manager):
        """测试 running → failed。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        await task_manager.fail_task(task.task_id, reason="测试失败")
        assert task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_running_to_cancelled(self, task_manager):
        """测试 running → cancelled。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        await task_manager.cancel_task(task.task_id)
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_task_raises(self, task_manager):
        """测试取消已完成任务抛出异常。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        await task_manager.complete_task(task.task_id)
        with pytest.raises(InvalidStateTransition):
            await task_manager.cancel_task(task.task_id)

    @pytest.mark.asyncio
    async def test_cancel_queued_task(self, task_manager):
        """测试取消排队中的任务。"""
        task1 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        task2 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(11, 20),
        )
        await task_manager.start_task(task1.task_id)
        await task_manager.start_task(task2.task_id)
        task3 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(21, 30),
        )
        await task_manager.start_task(task3.task_id)
        assert task3.status == TaskStatus.QUEUED
        await task_manager.cancel_task(task3.task_id)
        assert task3.status == TaskStatus.CANCELLED


# ============================================================
# 测试：重试逻辑
# ============================================================


class TestRetryLogic:
    """测试重试逻辑。"""

    @pytest.mark.asyncio
    async def test_retry_failed_task(self, task_manager):
        """测试重试失败任务。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        await task_manager.fail_task(task.task_id, reason="网络超时")
        assert task.status == TaskStatus.FAILED
        await task_manager.retry_task(task.task_id)
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_cancelled_task(self, task_manager):
        """测试重试取消任务。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        await task_manager.cancel_task(task.task_id)
        await task_manager.retry_task(task.task_id)
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_retry_running_task_raises(self, task_manager):
        """测试重试运行中任务抛出异常。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.start_task(task.task_id)
        with pytest.raises(InvalidStateTransition):
            await task_manager.retry_task(task.task_id)

    @pytest.mark.asyncio
    async def test_item_retry_logic(self):
        """测试子任务级别重试判定。"""
        # FloodWait 可重试
        item = TaskItem(
            item_id="msg_100",
            status=ItemStatus.FAILED,
            error_reason="FloodWait",
            max_retries=3,
        )
        assert item.can_retry() is True

        # 消息被删除 不可重试
        item2 = TaskItem(
            item_id="msg_101",
            status=ItemStatus.FAILED,
            error_reason="MESSAGE_ID_INVALID",
            max_retries=3,
        )
        assert item2.can_retry() is False

        # 达到最大重试次数 不可重试
        item3 = TaskItem(
            item_id="msg_102",
            status=ItemStatus.FAILED,
            error_reason="TimeoutError",
            max_retries=3,
        )
        item3.retry_count = 3
        assert item3.can_retry() is False


# ============================================================
# 测试：资源保护
# ============================================================


class TestResourceProtection:
    """测试资源保护机制。"""

    @pytest.mark.asyncio
    async def test_task_size_under_warning(self, task_manager):
        """测试任务大小低于告警阈值。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
            estimated_size=3 * 1024 * 1024 * 1024,  # 3GB
        )
        assert task.estimated_size == 3 * 1024 * 1024 * 1024
        assert task_manager.check_size_threshold(3 * 1024 * 1024 * 1024) == "ok"

    @pytest.mark.asyncio
    async def test_task_size_warning(self, task_manager):
        """测试任务大小触发告警。"""
        size = 7 * 1024 * 1024 * 1024  # 7GB
        result = task_manager.check_size_threshold(size)
        assert result == "warning"

    @pytest.mark.asyncio
    async def test_task_size_exceeded(self, task_manager):
        """测试任务大小超过上限。"""
        size = 12 * 1024 * 1024 * 1024  # 12GB
        result = task_manager.check_size_threshold(size)
        assert result == "exceeded"

    @pytest.mark.asyncio
    async def test_disk_space_check(self, task_manager):
        """测试磁盘空间检查。"""
        with patch("shutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.return_value = MagicMock(
                total=50 * 1024**3,
                used=49 * 1024**3,
                free=1 * 1024**3,  # 1GB 剩余
            )
            assert task_manager.check_disk_space() is False

    @pytest.mark.asyncio
    async def test_disk_space_sufficient(self, task_manager):
        """测试磁盘空间充足。"""
        with patch("shutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.return_value = MagicMock(
                total=50 * 1024**3,
                used=40 * 1024**3,
                free=10 * 1024**3,  # 10GB 剩余
            )
            assert task_manager.check_disk_space() is True


# ============================================================
# 测试：任务列表与查询
# ============================================================


class TestTaskList:
    """测试任务列表查询。"""

    @pytest.mark.asyncio
    async def test_list_all_tasks(self, task_manager):
        """测试列出所有任务。"""
        await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.create_task(
            task_type=TaskType.UPLOAD,
            chat_id=-1001234567890,
            file_paths=["/tmp/test.mp4"],
        )
        tasks = await task_manager.list_tasks()
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, task_manager):
        """测试按状态过滤任务列表。"""
        task1 = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(11, 20),
        )
        await task_manager.start_task(task1.task_id)
        await task_manager.complete_task(task1.task_id)
        completed = await task_manager.list_tasks(status=TaskStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].task_id == task1.task_id

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, task_manager):
        """测试通过 ID 获取任务。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        fetched = await task_manager.get_task(task.task_id)
        assert fetched is not None
        assert fetched.task_id == task.task_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, task_manager):
        """测试获取不存在的任务返回 None。"""
        result = await task_manager.get_task("nonexistent_id")
        assert result is None


# ============================================================
# 测试：子任务管理
# ============================================================


class TestTaskItemManagement:
    """测试子任务管理。"""

    @pytest.mark.asyncio
    async def test_add_task_items(self, task_manager):
        """测试添加子任务项。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        items = [
            TaskItem(item_id="msg_1", message_id=1, status=ItemStatus.PENDING),
            TaskItem(item_id="msg_2", message_id=2, status=ItemStatus.PENDING),
        ]
        await task_manager.add_items(task.task_id, items)
        fetched_task = await task_manager.get_task(task.task_id)
        assert len(fetched_task.items) == 2

    @pytest.mark.asyncio
    async def test_update_item_status(self, task_manager):
        """测试更新子任务状态。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 5),
        )
        item = TaskItem(item_id="msg_1", message_id=1, status=ItemStatus.PENDING)
        await task_manager.add_items(task.task_id, [item])
        await task_manager.update_item_status(task.task_id, "msg_1", ItemStatus.SUCCESS)
        fetched_task = await task_manager.get_task(task.task_id)
        assert fetched_task.items[0].status == ItemStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_get_failed_items(self, task_manager):
        """测试获取失败的子任务。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 5),
        )
        items = [
            TaskItem(item_id="msg_1", message_id=1, status=ItemStatus.SUCCESS),
            TaskItem(item_id="msg_2", message_id=2, status=ItemStatus.FAILED),
            TaskItem(item_id="msg_3", message_id=3, status=ItemStatus.SUCCESS),
            TaskItem(item_id="msg_4", message_id=4, status=ItemStatus.FAILED),
        ]
        await task_manager.add_items(task.task_id, items)
        failed = await task_manager.get_failed_items(task.task_id)
        assert len(failed) == 2


# ============================================================
# 测试：持久化与恢复
# ============================================================


class TestPersistenceAndRecovery:
    """测试持久化与重启恢复。"""

    @pytest.mark.asyncio
    async def test_tasks_survive_restart(self, db_path):
        """测试任务在重启后仍然存在。"""
        # 第一轮：创建任务
        tm1 = TaskManager(db_path=db_path, max_concurrent_tasks=2)
        task = await tm1.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        task_id = task.task_id
        await tm1.start_task(task_id)
        await tm1.complete_task(task_id)

        # 第二轮：重新加载
        tm2 = TaskManager(db_path=db_path, max_concurrent_tasks=2)
        tasks = await tm2.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_id == task_id
        assert tasks[0].status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_load_pending_tasks_on_start(self, db_path):
        """测试启动时加载未完成任务。"""
        tm1 = TaskManager(db_path=db_path, max_concurrent_tasks=2)
        task1 = await tm1.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(1, 10),
        )
        task2 = await tm1.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            message_range=(11, 20),
        )
        await tm1.start_task(task1.task_id)
        # task1 未完成，task2 未启动

        tm2 = TaskManager(db_path=db_path, max_concurrent_tasks=2)
        pending = await tm2.list_tasks(status=TaskStatus.PENDING)
        running = await tm2.list_tasks(status=TaskStatus.RUNNING)
        assert len(pending) == 1
        assert len(running) == 1
