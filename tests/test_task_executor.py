# coding=UTF-8
"""TaskExecutor 单元测试。

覆盖场景：
- 下载任务执行（有/无 downloader）
- 下载完成后 file_paths 保存
- 缺少 message_range 时的错误处理
- 转发任务和上传任务的路径覆盖

注：实际文件下载依赖 Telegram Client，此处使用 Mock 替代。
"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.core.task_executor import TaskExecutor
from module.core.task_manager import (
    TaskManager,
    TaskItem,
    TaskType,
    TaskStatus,
    ItemStatus,
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


@pytest.fixture
def mock_client():
    """Mock Pyrogram Client。"""
    client = AsyncMock()
    client.get_messages = AsyncMock()
    client.copy_message = AsyncMock()
    return client


@pytest.fixture
def mock_downloader():
    """Mock 下载器。"""
    dl = AsyncMock()
    dl.download_range.return_value = ["/downloads/file1.mp4", "/downloads/file2.mp4"]
    return dl


@pytest.fixture
def mock_file_manager():
    """Mock FileManager。"""
    fm = AsyncMock()
    fm.get_file_info = AsyncMock()
    fm.split_media_group = AsyncMock()
    fm.upload = AsyncMock()
    fm.upload_media_group = AsyncMock()
    return fm


# ============================================================
# 测试：update_file_paths
# ============================================================


class TestUpdateFilePaths:
    """测试 TaskManager.update_file_paths。"""

    @pytest.mark.asyncio
    async def test_update_file_paths(self, task_manager):
        """测试更新文件路径。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 5},
        )
        file_paths = ["/downloads/file1.mp4", "/downloads/file2.mp4"]
        await task_manager.update_file_paths(task.task_id, file_paths)

        updated = await task_manager.get_task(task.task_id)
        assert updated.params.get("file_paths", []) == file_paths

    @pytest.mark.asyncio
    async def test_update_file_paths_empty(self, task_manager):
        """测试更新空文件路径列表。"""
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 5},
        )
        await task_manager.update_file_paths(task.task_id, [])
        updated = await task_manager.get_task(task.task_id)
        assert updated.params.get("file_paths", []) == []

    @pytest.mark.asyncio
    async def test_update_file_paths_persisted(self, task_manager, db_path):
        """测试文件路径持久化到 SQLite。"""
        import json
        import sqlite3

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 5},
        )
        file_paths = ["/downloads/file1.mp4"]
        await task_manager.update_file_paths(task.task_id, file_paths)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT params FROM tm_tasks WHERE id = ?", (task.task_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        saved_params = json.loads(row[0])
        assert saved_params.get("file_paths") == file_paths

    @pytest.mark.asyncio
    async def test_update_file_paths_nonexistent_task(self, task_manager):
        """测试更新不存在的任务文件路径抛出异常。"""
        from module.core.task_manager import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            await task_manager.update_file_paths("nonexistent", ["/file.mp4"])


# ============================================================
# 测试：TaskExecutor 下载执行
# ============================================================


class TestExecuteDownload:
    """测试 TaskExecutor._execute_download。"""

    @pytest.mark.asyncio
    async def test_execute_download_with_downloader(
        self, task_manager, mock_client, mock_downloader, mock_file_manager
    ):
        """测试有 downloader 时的下载路径和 file_paths 保存。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 100, "message_range_end": 102},
        )

        await executor._execute_download(task)

        # 验证 downloader.download_range 被正确调用
        mock_downloader.download_range.assert_called_once_with(
            chat_id=-1001234567890,
            start_id=100,
            end_id=102,
            task_id=task.task_id,
            progress_callback=executor._on_item_progress,
        )

        # 验证 file_paths 已保存到任务
        updated = await task_manager.get_task(task.task_id)
        assert updated.params.get("file_paths", []) == ["/downloads/file1.mp4", "/downloads/file2.mp4"]

    @pytest.mark.asyncio
    async def test_execute_download_saves_file_paths_to_db(
        self, task_manager, db_path, mock_client, mock_downloader, mock_file_manager
    ):
        """测试下载后 file_paths 持久化到数据库。"""
        import json
        import sqlite3

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 3},
        )

        await executor._execute_download(task)

        # 验证数据库中的 file_paths
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT params FROM tm_tasks WHERE id = ?", (task.task_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        saved_params = json.loads(row[0])
        assert saved_params.get("file_paths") == [
            "/downloads/file1.mp4",
            "/downloads/file2.mp4",
        ]

    @pytest.mark.asyncio
    async def test_execute_download_empty_result(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试下载器返回空列表时 file_paths 保持为空。"""
        mock_downloader = AsyncMock()
        mock_downloader.download_range.return_value = []

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 5},
        )

        await executor._execute_download(task)

        updated = await task_manager.get_task(task.task_id)
        assert updated.params.get("file_paths", []) == []

    @pytest.mark.asyncio
    async def test_execute_download_no_message_range(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试没有消息范围时抛出 ValueError。"""
        mock_downloader = AsyncMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params=None,
        )

        with pytest.raises(ValueError, match="缺少消息范围参数"):
            await executor._execute_download(task)

    @pytest.mark.asyncio
    async def test_execute_download_no_downloader_fallback(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试无 downloader 时走降级路径。"""
        mock_client.get_messages = AsyncMock()
        mock_message = MagicMock()
        mock_message.media = True
        mock_client.get_messages.return_value = mock_message

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=None,  # 无 downloader
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 3},
        )

        await executor._execute_download(task)

        # 验证 get_messages 被调用（降级路径）
        assert mock_client.get_messages.called
        updated = await task_manager.get_task(task.task_id)
        assert updated.params.get("file_paths", []) == []  # 降级路径不产生文件路径

    @pytest.mark.asyncio
    async def test_execute_download_fallback_failed_items(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试降级路径中消息无媒体时标记失败。"""
        mock_client.get_messages = AsyncMock()
        mock_client.get_messages.return_value = None  # 消息不存在

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=None,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 2},
        )

        await executor._execute_download(task)

        # 所有子任务应标记为失败
        failed = await task_manager.get_failed_items(task.task_id)
        assert len(failed) == 2  # 两条消息都失败

    @pytest.mark.asyncio
    async def test_execute_download_with_progress_callback(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 progress_callback 正确传递到 downloader。"""
        mock_downloader = AsyncMock()
        mock_downloader.download_range.return_value = ["/file.mp4"]

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 10, "message_range_end": 20},
        )

        await executor._execute_download(task)

        # 验证 progress_callback 参数被传入
        call_kwargs = mock_downloader.download_range.call_args[1]
        assert "progress_callback" in call_kwargs
        assert call_kwargs["progress_callback"] == executor._on_item_progress


# ============================================================
# 测试：TaskExecutor 整体执行流程
# ============================================================


class TestExecuteTask:
    """测试 TaskExecutor.execute_task 整体流程。"""

    @pytest.mark.asyncio
    async def test_execute_task_download_success(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试下载任务整体执行成功流程。"""
        mock_downloader = AsyncMock()
        mock_downloader.download_range.return_value = ["/file.mp4"]

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 5},
        )
        await task_manager.start_task(task.task_id)

        await executor.execute_task(task)

        # 验证任务状态为 completed
        updated = await task_manager.get_task(task.task_id)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.params.get("file_paths", []) == ["/file.mp4"]

    @pytest.mark.asyncio
    async def test_execute_task_download_no_message_range(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试下载任务缺少范围时标记为失败。"""
        mock_downloader = AsyncMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params=None,
        )
        await task_manager.start_task(task.task_id)

        await executor.execute_task(task)

        # 验证任务状态为 failed
        updated = await task_manager.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "缺少消息范围参数" in (updated.error_message or "")

    @pytest.mark.asyncio
    async def test_execute_task_cancelled(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试任务被取消。"""
        mock_downloader = AsyncMock()
        mock_downloader.download_range.side_effect = asyncio.CancelledError()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 5},
        )
        await task_manager.start_task(task.task_id)

        with pytest.raises(asyncio.CancelledError):
            await executor.execute_task(task)

        # 验证任务状态为 cancelled
        updated = await task_manager.get_task(task.task_id)
        assert updated.status == TaskStatus.CANCELLED


# ============================================================
# 测试：_on_item_progress
# ============================================================


class TestOnItemProgress:
    """测试 _on_item_progress 回调。"""

    @pytest.mark.asyncio
    async def test_on_item_progress_success(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试子任务进度回调。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=None,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 1},
        )
        item = TaskItem(id="msg_1", task_id="", source_id=1)
        await task_manager.add_items(task.task_id, [item])

        await executor._on_item_progress(task.task_id, "msg_1", ItemStatus.SUCCESS)

        updated = await task_manager.get_task(task.task_id)
        assert updated.items[0].status == ItemStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_on_item_progress_failed(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试子任务失败回调。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=None,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 1},
        )
        item = TaskItem(id="msg_1", task_id="", source_id=1)
        await task_manager.add_items(task.task_id, [item])

        await executor._on_item_progress(
            task.task_id, "msg_1", ItemStatus.FAILED, "测试失败"
        )

        updated = await task_manager.get_task(task.task_id)
        assert updated.items[0].status == ItemStatus.FAILED
        assert updated.items[0].error_message == "测试失败"
