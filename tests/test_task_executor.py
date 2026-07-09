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
import inspect
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.core.task_executor import TaskExecutor
from module.core.task_manager import (
    TaskManager,
    TaskItem,
    TaskType,
    TaskStatus,
    ItemStatus,
    ExecutorError,
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


@pytest.fixture
def task_executor(task_manager, mock_client, mock_file_manager):
    """提供带默认参数的 TaskExecutor 实例。"""
    return TaskExecutor(
        task_manager=task_manager,
        file_manager=mock_file_manager,
        client=mock_client,
    )


@pytest.fixture
def mock_repository_manager():
    """Mock RepositoryManager。"""
    rm = MagicMock()
    rm.should_use_repository.return_value = True
    rm.check_dedup.return_value = None
    rm.compute_content_hash.return_value = "abc123sha256"
    rm.distribute_to_target = AsyncMock(return_value=999)
    return rm


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
# 测试：TaskExecutor 跨 loop 提交
# ============================================================


class TestSubmitTask:
    """测试 submit_task 将任务提交到创建时的事件循环。"""

    def test_executor_captures_creation_event_loop(
        self, task_manager, mock_client, mock_file_manager
    ):
        """TaskExecutor 应保存创建时所在的事件循环。"""
        target_loop = asyncio.new_event_loop()
        executor = None

        async def _create():
            nonlocal executor
            executor = TaskExecutor(
                task_manager=task_manager,
                file_manager=mock_file_manager,
                client=mock_client,
            )

        try:
            target_loop.run_until_complete(_create())
            assert executor._event_loop is target_loop
        finally:
            target_loop.close()

    def test_submit_task_uses_run_coroutine_threadsafe(
        self, task_manager, mock_client, mock_file_manager
    ):
        """submit_task 应通过 run_coroutine_threadsafe 提交到目标 loop。"""
        target_loop = asyncio.new_event_loop()
        executor = None

        async def _create():
            nonlocal executor
            executor = TaskExecutor(
                task_manager=task_manager,
                file_manager=mock_file_manager,
                client=mock_client,
            )

        try:
            target_loop.run_until_complete(_create())

            task = MagicMock()
            task.task_id = "task_1"

            with patch(
                "module.core.task_executor.asyncio.run_coroutine_threadsafe"
            ) as mock_run:
                expected_future = MagicMock()
                mock_run.return_value = expected_future

                result = executor.submit_task(task)

                mock_run.assert_called_once()
                coro, loop = mock_run.call_args[0]
                assert inspect.iscoroutine(coro)
                assert loop is target_loop
                assert result is expected_future
        finally:
            target_loop.close()

    def test_submit_task_raises_when_no_event_loop(
        self, task_manager, mock_client, mock_file_manager
    ):
        """未绑定事件循环时 submit_task 应抛出 RuntimeError。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        # 显式清除 event_loop 模拟非 loop 环境创建
        executor._event_loop = None

        task = MagicMock()
        task.task_id = "task_1"

        with pytest.raises(RuntimeError, match="未绑定事件循环"):
            executor.submit_task(task)


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
        assert updated.params.get("file_paths", []) == [
            "/downloads/file1.mp4",
            "/downloads/file2.mp4",
        ]

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
        """测试没有消息范围时抛出 ExecutorError。"""
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
            params={"min_id": 1, "max_id": 5},  # 提供 min_id 以通过 create_task 校验
        )

        # 清空 params 中的消息范围，模拟缺少消息范围的情况
        task.params.pop("min_id", None)
        task.params.pop("max_id", None)

        with pytest.raises(ExecutorError, match="缺少消息范围参数"):
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
            params={"min_id": 1, "max_id": 5},  # 提供 min_id 以通过 create_task 校验
        )
        # 清空 params 中的消息范围，模拟缺少消息范围的情况
        task.params.pop("min_id", None)
        task.params.pop("max_id", None)
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

    @pytest.mark.asyncio
    async def test_executor_error_marks_task_failed(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 ExecutorError 导致任务被标记为 failed。"""
        mock_downloader = AsyncMock()
        # 模拟 _execute_download 抛出 ExecutorError
        mock_downloader.download_range.side_effect = ExecutorError("下载器内部错误")

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

        # 验证任务状态为 failed
        updated = await task_manager.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "下载器内部错误" in (updated.error_message or "")


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


# ============================================================
# 测试：消息范围解析
# ============================================================


class TestResolveMessageIds:
    """测试 _resolve_message_ids 方法。"""

    @pytest.mark.asyncio
    async def test_resolve_message_ids_id_range(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 id_range 模式正常解析。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "id_range", "min_id": 1, "max_id": 5},
        )

        result = await executor._resolve_message_ids(task)
        assert result == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_resolve_message_ids_multiple_ids(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 multiple_ids 模式解析（含链接和纯数字）。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={
                "range_mode": "multiple_ids",
                "message_list": ["123", "https://t.me/channel/456", "789"],
            },
        )

        result = await executor._resolve_message_ids(task)
        assert result == [123, 456, 789]

    @pytest.mark.asyncio
    async def test_resolve_message_ids_date_range(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 date_range 模式通过 mock client 获取消息 ID。"""
        from datetime import datetime, timezone

        # 创建 mock 消息
        msg1 = MagicMock()
        msg1.id = 100
        msg1.date = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)

        msg2 = MagicMock()
        msg2.id = 101
        msg2.date = datetime(2024, 6, 10, 12, 0, tzinfo=timezone.utc)

        msg3 = MagicMock()
        msg3.id = 102
        msg3.date = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)  # 早于 start_date

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg1, msg2, msg3])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={
                "range_mode": "date_range",
                "start_date": "2024-06-05",
                "end_date": "2024-06-20",
            },
        )

        result = await executor._resolve_message_ids(task)
        # msg3 的日期早于 start_date，应被 break 排除
        assert 100 in result
        assert 101 in result

    @pytest.mark.asyncio
    async def test_resolve_message_ids_all(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 all 模式通过 mock client 遍历消息。"""
        msg1 = MagicMock()
        msg1.id = 1
        msg2 = MagicMock()
        msg2.id = 2

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg1, msg2])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all"},
        )

        result = await executor._resolve_message_ids(task)
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_resolve_message_ids_date_range_missing_params(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 date_range 缺少日期参数抛 ExecutorError。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        # 使用 all 模式创建任务（不需要额外参数），然后手动修改 params
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all"},
        )
        # 修改为 date_range 但不提供日期参数
        task.params["range_mode"] = "date_range"
        task.params.pop("start_date", None)
        task.params.pop("end_date", None)

        with pytest.raises(ExecutorError, match="date_range 模式缺少"):
            await executor._resolve_message_ids(task)

    @pytest.mark.asyncio
    async def test_resolve_message_ids_invalid_date_format(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试日期格式无效抛 ExecutorError。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        # 使用 all 模式创建任务，然后手动修改 params
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all"},
        )
        task.params["range_mode"] = "date_range"
        task.params["start_date"] = "not-a-date"
        task.params["end_date"] = "2024-06-20"

        with pytest.raises(ExecutorError, match="日期格式无效"):
            await executor._resolve_message_ids(task)


class TestParseMessageIdList:
    """测试 _parse_message_id_list 静态方法。"""

    def test_parse_pure_numbers(self):
        """测试纯数字解析。"""
        result = TaskExecutor._parse_message_id_list(["123", "456"])
        assert result == [123, 456]

    def test_parse_links(self):
        """测试链接格式解析。"""
        result = TaskExecutor._parse_message_id_list(
            ["https://t.me/channel/789", "t.me/channel/101"]
        )
        assert result == [789, 101]

    def test_parse_mixed(self):
        """测试混合格式解析。"""
        result = TaskExecutor._parse_message_id_list(
            ["123", "https://t.me/channel/456", "", "  789  "]
        )
        assert result == [123, 456, 789]


class TestGetMediaTypeExtended:
    """测试 _get_media_type 扩展类型。"""

    def test_get_media_type_voice(self):
        """测试语音消息返回 'voice'。"""
        message = MagicMock()
        message.media = MagicMock()
        message.media.voice = MagicMock()
        message.media.video = None
        message.media.photo = None
        message.media.document = None
        message.media.audio = None
        message.media.animation = None
        message.media.video_note = None
        assert TaskExecutor._get_media_type(message) == "voice"

    def test_get_media_type_video_note(self):
        """测试视频笔记返回 'video_note'。"""
        message = MagicMock()
        message.media = MagicMock()
        message.media.video_note = MagicMock()
        message.media.video = None
        message.media.photo = None
        message.media.document = None
        message.media.audio = None
        message.media.animation = None
        message.media.voice = None
        assert TaskExecutor._get_media_type(message) == "video_note"


class AsyncIteratorMock:
    """模拟异步迭代器。"""

    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


# ============================================================
# 测试：并发控制
# ============================================================


class TestConcurrencyControl:
    """测试并发控制行为。"""

    @pytest.mark.asyncio
    async def test_download_semaphore_created(self, task_executor):
        """验证下载 Semaphore 被创建且值正确。"""
        assert hasattr(task_executor, "_download_semaphore")
        assert isinstance(task_executor._download_semaphore, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_forward_semaphore_created(self, task_executor):
        """验证转发 Semaphore 被创建且值正确。"""
        assert hasattr(task_executor, "_forward_semaphore")
        assert isinstance(task_executor._forward_semaphore, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_upload_semaphore_created(self, task_executor):
        """验证上传 Semaphore 被创建且值正确。"""
        assert hasattr(task_executor, "_upload_semaphore")
        assert isinstance(task_executor._upload_semaphore, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_download_semaphore_default_value(self, task_executor):
        """默认值应为 3。"""
        assert task_executor._download_semaphore._value == 3

    @pytest.mark.asyncio
    async def test_forward_semaphore_default_value(self, task_executor):
        """默认值应为 1。"""
        assert task_executor._forward_semaphore._value == 1

    @pytest.mark.asyncio
    async def test_upload_semaphore_default_value(self, task_executor):
        """默认值应为 1。"""
        assert task_executor._upload_semaphore._value == 1


# ============================================================
# 测试：去重与字段填充
# ============================================================


class TestDedupAndFieldPopulation:
    """去重与字段填充测试。"""

    @pytest.mark.asyncio
    async def test_download_l2_dedup_hit(
        self, task_manager, mock_client, mock_file_manager, mock_repository_manager
    ):
        """file_unique_id 命中仓库去重 → 标记 SKIPPED。"""
        mock_repository_manager.check_dedup.return_value = MagicMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            repository_manager=mock_repository_manager,
        )

        mock_msg = MagicMock()
        mock_msg.media = MagicMock()
        mock_msg.media.file_unique_id = "uniq_123"
        mock_msg.media.file_id = "file_123"
        mock_client.get_messages = AsyncMock(return_value=mock_msg)

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 1},
        )

        await executor._execute_download(task)

        updated = await task_manager.get_task(task.task_id)
        assert updated.items[0].status == ItemStatus.SKIPPED
        mock_repository_manager.check_dedup.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_l2_dedup_miss(
        self, task_manager, mock_client, mock_file_manager, mock_repository_manager
    ):
        """file_unique_id 未命中 → 正常 SUCCESS。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            repository_manager=mock_repository_manager,
        )

        mock_msg = MagicMock()
        mock_media = MagicMock(spec=[])
        mock_media.file_unique_id = "uniq_new"
        mock_media.file_id = "file_new"
        mock_msg.media = mock_media
        mock_client.get_messages = AsyncMock(return_value=mock_msg)

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 1},
        )

        await executor._execute_download(task)

        updated = await task_manager.get_task(task.task_id)
        assert updated.items[0].status == ItemStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_download_populates_fields(
        self, task_manager, mock_client, mock_file_manager, mock_repository_manager
    ):
        """下载成功后 TaskItem 的 file_unique_id 和 telegram_file_id 被填充。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            repository_manager=mock_repository_manager,
        )

        mock_msg = MagicMock()
        mock_media = MagicMock(spec=[])
        mock_media.file_unique_id = "uniq_filled"
        mock_media.file_id = "file_filled"
        mock_msg.media = mock_media
        mock_client.get_messages = AsyncMock(return_value=mock_msg)

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"message_range_start": 1, "message_range_end": 1},
        )

        await executor._execute_download(task)

        updated = await task_manager.get_task(task.task_id)
        item = updated.items[0]
        assert item.file_unique_id == "uniq_filled"
        assert item.telegram_file_id == "file_filled"

    @pytest.mark.asyncio
    async def test_forward_populates_target_fields(
        self, task_manager, mock_client, mock_file_manager
    ):
        """转发成功后 target_id 和 uploaded_message_id 被填充。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        mock_result = MagicMock()
        mock_result.id = 98765
        mock_client.copy_message = AsyncMock(return_value=mock_result)

        task = await task_manager.create_task(
            task_type=TaskType.FORWARD,
            chat_id=-1001234567890,
            params={
                "target_chat_id": -1009876543210,
                "message_range_start": 1,
                "message_range_end": 1,
            },
        )

        await executor._execute_forward(task)

        updated = await task_manager.get_task(task.task_id)
        item = updated.items[0]
        assert item.target_id == -1009876543210
        assert item.uploaded_message_id == 98765

    @pytest.mark.asyncio
    async def test_upload_l3_dedup_hit(
        self, task_manager, mock_client, mock_file_manager, mock_repository_manager
    ):
        """SHA256 命中仓库 → 用 distribute_to_target 替代上传。"""
        dedup_result = MagicMock()
        dedup_result.file_unique_id = "uniq_existing"
        mock_repository_manager.check_dedup.return_value = dedup_result

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            repository_manager=mock_repository_manager,
        )

        mock_file_info = MagicMock()
        mock_file_info.path = "/tmp/test.mp4"
        mock_file_manager.get_file_info = AsyncMock(return_value=mock_file_info)
        mock_file_manager.split_media_group = AsyncMock(
            return_value=[{"is_album": False, "files": [mock_file_info]}]
        )

        task = await task_manager.create_task(
            task_type=TaskType.UPLOAD,
            chat_id=-1001234567890,
            params={"file_paths": ["/tmp/test.mp4"]},
        )

        await executor._execute_upload(task)

        updated = await task_manager.get_task(task.task_id)
        item = updated.items[0]
        assert item.status == ItemStatus.SUCCESS
        assert item.target_id == -1001234567890
        assert item.uploaded_message_id == 999
        mock_repository_manager.distribute_to_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_l3_dedup_miss(
        self, task_manager, mock_client, mock_file_manager, mock_repository_manager
    ):
        """SHA256 未命中 → 正常上传。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            repository_manager=mock_repository_manager,
        )

        mock_file_info = MagicMock()
        mock_file_info.path = "/tmp/test.mp4"
        mock_file_manager.get_file_info = AsyncMock(return_value=mock_file_info)
        mock_file_manager.split_media_group = AsyncMock(
            return_value=[{"is_album": False, "files": [mock_file_info]}]
        )
        mock_result = MagicMock()
        mock_result.success = True
        mock_file_manager.upload = AsyncMock(return_value=mock_result)

        task = await task_manager.create_task(
            task_type=TaskType.UPLOAD,
            chat_id=-1001234567890,
            params={"file_paths": ["/tmp/test.mp4"]},
        )

        await executor._execute_upload(task)

        updated = await task_manager.get_task(task.task_id)
        item = updated.items[0]
        assert item.status == ItemStatus.SUCCESS
        mock_file_manager.upload.assert_called_once()


class TestResumeDownload:
    """断点续传集成测试。"""

    def test_resume_download_uses_resume_method(
        self, task_manager, mock_client, mock_file_manager, mock_downloader
    ):
        """有 downloader 时 download_range 被调用即具备断点续传能力。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )
        assert executor._downloader is mock_downloader


# ============================================================
# 测试：阶段 2 新特性（recent 模式与媒体过滤）
# ============================================================


class TestPhase2RecentAndMediaFilter:
    """测试 recent 模式解析与媒体/大小过滤。"""

    @pytest.mark.asyncio
    async def test_resolve_message_ids_recent_mode(
        self, task_manager, mock_client, mock_file_manager
    ):
        """_resolve_message_ids 在 range_mode=recent 时调用 _resolve_recent_ids。"""
        msg1 = MagicMock()
        msg1.id = 10
        msg2 = MagicMock()
        msg2.id = 9

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg1, msg2])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "recent", "recent_count": 2},
        )
        result = await executor._resolve_message_ids(task)
        assert result == [10, 9]

    @pytest.mark.asyncio
    async def test_resolve_recent_ids(
        self, task_manager, mock_client, mock_file_manager
    ):
        """recent 模式返回最近 N 条消息 ID。"""
        msg1 = MagicMock()
        msg1.id = 10
        msg2 = MagicMock()
        msg2.id = 9
        msg3 = MagicMock()
        msg3.id = 8

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg1, msg2, msg3])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "recent", "recent_count": 3},
        )
        result = await executor._resolve_recent_ids(task)
        assert result == [10, 9, 8]

    @pytest.mark.asyncio
    async def test_resolve_recent_ids_missing_count_raises(
        self, task_manager, mock_client, mock_file_manager
    ):
        """recent 模式缺少有效 recent_count 时抛出 ExecutorError。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "recent", "recent_count": 1},
        )
        # 绕过 TaskManager 的校验，模拟执行时参数缺失
        task.params.pop("recent_count")
        with pytest.raises(ExecutorError, match="recent_count"):
            await executor._resolve_recent_ids(task)

    @pytest.mark.asyncio
    async def test_resolve_recent_ids_truncated_by_task_manager(
        self, task_manager, mock_client, mock_file_manager
    ):
        """TaskManager 已将 recent_count 截断至 1000，Executor 仍按 params 取值工作。"""
        messages = [MagicMock(id=i) for i in range(1000, 0, -1)]
        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock(messages)
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "recent", "recent_count": 1000},
        )
        result = await executor._resolve_recent_ids(task)
        assert len(result) == 1000
        assert result[0] == 1000
        assert result[-1] == 1

    def _make_message(self, msg_id, media_type=None, file_size=None):
        """构造含媒体的 mock Message。"""
        msg = MagicMock()
        msg.id = msg_id
        if media_type:
            msg.media = MagicMock()
            for attr in (
                "video",
                "photo",
                "document",
                "audio",
                "animation",
                "voice",
                "video_note",
            ):
                setattr(msg.media, attr, None)
            media_obj = MagicMock()
            media_obj.file_size = file_size
            media_obj.file_unique_id = f"unique_{msg_id}"
            media_obj.file_id = f"file_{msg_id}"
            setattr(msg.media, media_type, media_obj)
        else:
            msg.media = None
        return msg

    @pytest.mark.asyncio
    async def test_filter_media_messages_by_criteria(
        self, task_manager, mock_client, mock_file_manager
    ):
        """media_types 过滤仅保留指定类型的消息。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        messages = [
            self._make_message(1, "video", 1024),
            self._make_message(2, "photo", 512),
            self._make_message(3, "audio", 2048),
            self._make_message(4, None),
        ]
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all", "media_types": ["video", "photo"]},
        )
        result = executor._filter_media_messages_by_criteria(task, messages)
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_filter_messages_by_size(
        self, task_manager, mock_client, mock_file_manager
    ):
        """min_size / max_size 按字节过滤媒体文件。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        messages = [
            self._make_message(1, "video", 100),
            self._make_message(2, "video", 500),
            self._make_message(3, "video", 1000),
            self._make_message(4, "video", 2000),
        ]
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all", "min_size": 300, "max_size": 1200},
        )
        result = executor._filter_media_messages_by_criteria(task, messages)
        assert result == [2, 3]

    def test_get_message_file_size_various_media(self):
        """_get_message_file_size 覆盖视频、照片、无媒体、不支持的媒体类型。"""
        # 无媒体消息
        msg_no_media = MagicMock()
        msg_no_media.media = None
        assert TaskExecutor._get_message_file_size(msg_no_media) is None

        # 视频消息
        msg_video = self._make_message(1, "video", 1024)
        assert TaskExecutor._get_message_file_size(msg_video) == 1024

        # 照片消息（sizes 列表取最后一个）
        msg_photo = MagicMock()
        msg_photo.media = MagicMock()
        for attr in (
            "video",
            "document",
            "audio",
            "animation",
            "voice",
            "video_note",
        ):
            setattr(msg_photo.media, attr, None)
        msg_photo.media.photo = MagicMock()
        size1 = MagicMock(file_size=100)
        size2 = MagicMock(file_size=200)
        msg_photo.media.photo.sizes = [size1, size2]
        assert TaskExecutor._get_message_file_size(msg_photo) == 200

        # 不支持的媒体类型
        msg_unsupported = MagicMock()
        msg_unsupported.media = MagicMock()
        for attr in (
            "video",
            "document",
            "audio",
            "animation",
            "voice",
            "video_note",
            "photo",
        ):
            setattr(msg_unsupported.media, attr, None)
        assert TaskExecutor._get_message_file_size(msg_unsupported) is None

    @pytest.mark.asyncio
    async def test_filter_media_messages_no_filter_returns_all(
        self, task_manager, mock_client, mock_file_manager
    ):
        """无过滤条件时返回所有非空消息 ID。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        messages = [
            self._make_message(1, "video", 1024),
            self._make_message(2, "photo", 512),
            MagicMock(),
        ]
        messages[2].id = 3
        messages[2].media = None
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all"},
        )
        result = executor._filter_media_messages_by_criteria(task, messages)
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_apply_media_filter_with_mock_client(
        self, task_manager, mock_client, mock_file_manager
    ):
        """_apply_media_filter 获取消息对象后调用过滤逻辑。"""
        messages = [
            self._make_message(1, "video", 1024),
            self._make_message(2, "photo", 512),
            self._make_message(3, "audio", 2048),
        ]
        mock_client.get_messages = AsyncMock(
            side_effect=lambda _chat, msg_id: messages[msg_id - 1]
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all", "media_types": ["video"]},
        )
        result = await executor._apply_media_filter(task, [1, 2, 3])
        assert result == [1]
        assert mock_client.get_messages.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_download_applies_media_filter(
        self, task_manager, mock_client, mock_file_manager
    ):
        """端到端：下载任务执行时先应用媒体过滤再创建 TaskItem。"""
        messages = [
            self._make_message(1, "video", 1024),
            self._make_message(2, "photo", 512),
            self._make_message(3, "video", 2048),
        ]
        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock(messages)
        )
        mock_client.get_messages = AsyncMock(
            side_effect=lambda _chat, msg_id: messages[msg_id - 1]
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
            params={"range_mode": "all", "media_types": ["video"]},
        )
        await executor._execute_download(task)
        # 过滤后应只有 2 个 video 消息生成 item
        assert len(task.items) == 2
        assert all(item.source_id in (1, 3) for item in task.items)


# ============================================================
# 测试：Phase 3 - execute_task() 分发
# ============================================================


class TestPhase3ExecuteTaskDispatch:
    """测试 execute_task() 正确分发 LISTEN_DOWNLOAD/LISTEN_FORWARD。"""

    @pytest.mark.asyncio
    async def test_execute_task_dispatches_listen_download(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 execute_task() 分发到 LISTEN_DOWNLOAD 分支。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(task.task_id)
        await executor.execute_task(task)
        # 验证 add_handler 被调用（表示分发到了正确的分支）
        mock_client.add_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_dispatches_listen_forward(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 execute_task() 分发到 LISTEN_FORWARD 分支。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "target_identifier": "@targetchannel",
            },
        )
        await task_manager.start_task(task.task_id)
        await executor.execute_task(task)
        mock_client.add_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_task_does_not_complete(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试监听任务执行后不进入 completed 状态（保持 running）。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(task.task_id)
        # 监听任务即使内部异常，也不会进入 completed 状态
        await executor.execute_task(task)
        updated = await task_manager.get_task(task.task_id)
        assert updated.status != TaskStatus.COMPLETED


# ============================================================
# 测试：Phase 3 - 私聊下载/转发复用
# ============================================================


class TestPhase3PrivateChatReuse:
    """测试私聊下载/转发复用现有 _execute_download() / _execute_forward()。"""

    @pytest.mark.asyncio
    async def test_private_chat_download_reuses_execute_download(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试私聊下载任务（source_identifier 创建）走 _execute_download() 路径。"""
        mock_downloader = AsyncMock()
        mock_downloader.download_range.return_value = ["/downloads/file.mp4"]

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )
        # 模拟私聊任务：chat_id 为负数 Bot ID
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=8288406549,  # 私聊 Bot ID
            params={
                "source_identifier": "@seseYunBot",
                "source_type": "private",
                "message_range_start": 100,
                "message_range_end": 102,
            },
        )
        await executor._execute_download(task)
        # 验证 downloader 被正确调用
        mock_downloader.download_range.assert_called_once()
        call_kwargs = mock_downloader.download_range.call_args[1]
        assert call_kwargs["chat_id"] == 8288406549

    @pytest.mark.asyncio
    async def test_private_chat_forward_reuses_execute_forward(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试私聊转发任务（source_identifier 创建）走 _execute_forward() 路径。"""
        mock_client.copy_message = AsyncMock(return_value=MagicMock(id=200))
        mock_client.get_messages = AsyncMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.FORWARD,
            chat_id=8288406549,
            params={
                "source_identifier": "@seseYunBot",
                "source_type": "private",
                "target_identifier": "@my_channel",
                "target_chat_id": -1002000000000,
                "message_range_start": 100,
                "message_range_end": 100,
            },
        )
        await executor._execute_forward(task)
        # 验证 copy_message 被调用（转发路径）
        assert mock_client.copy_message.called


# ============================================================
# 测试：Phase 3 - _start_listener() / _stop_listener()
# ============================================================


class TestPhase3ListenerLifecycle:
    """测试监听任务 Handler 生命周期管理。"""

    @pytest.mark.asyncio
    async def test_start_listener_registers_handler(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 _start_listener() 注册 MessageHandler 并存储引用。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        async def dummy_callback(client, message):
            pass

        await executor._start_listener(task, dummy_callback)

        # 验证 add_handler 被调用
        mock_client.add_handler.assert_called_once()
        # 验证 handler 引用已存储
        assert "_handler" in task.extra
        assert task.extra["_handler"] is not None

    @pytest.mark.asyncio
    async def test_start_listener_uses_chat_id_filter(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 _start_listener() 创建的 Handler 使用 chat_id 过滤。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        async def dummy_callback(client, message):
            pass

        await executor._start_listener(task, dummy_callback)

        # 验证 handler 被创建（通过 add_handler 调用验证）
        args = mock_client.add_handler.call_args[0]
        assert len(args) >= 1
        from pyrogram.handlers import MessageHandler

        assert isinstance(args[0], MessageHandler)

    @pytest.mark.asyncio
    async def test_execute_listen_download_calls_start_listener(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 _execute_listen_download() 调用 _start_listener()。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(task.task_id)

        await executor._execute_listen_download(task)

        # 验证 add_handler 被调用
        mock_client.add_handler.assert_called_once()
        # 验证 handler 引用已存储
        assert "_handler" in task.extra

    @pytest.mark.asyncio
    async def test_execute_listen_forward_calls_start_listener(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 _execute_listen_forward() 调用 _start_listener()。"""
        mock_client.add_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "target_identifier": "@targetchannel",
            },
        )
        await task_manager.start_task(task.task_id)

        await executor._execute_listen_forward(task)

        mock_client.add_handler.assert_called_once()
        assert "_handler" in task.extra

    @pytest.mark.asyncio
    async def test_stop_listener_removes_handler(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 _stop_listener() 移除 Handler 并清理引用。"""
        mock_client.add_handler = MagicMock()
        mock_client.remove_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        async def dummy_callback(client, message):
            pass

        # 先 start
        await executor._start_listener(task, dummy_callback)
        assert "_handler" in task.extra

        # 再 stop
        await executor._stop_listener(task)
        mock_client.remove_handler.assert_called_once()
        assert "_handler" not in task.extra

    @pytest.mark.asyncio
    async def test_stop_listener_idempotent(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 _stop_listener() 多次调用不报错。"""
        mock_client.add_handler = MagicMock()
        mock_client.remove_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        async def dummy_callback(client, message):
            pass

        await executor._start_listener(task, dummy_callback)
        await executor._stop_listener(task)
        # 第二次调用不应报错
        await executor._stop_listener(task)
        assert "_handler" not in task.extra

    @pytest.mark.asyncio
    async def test_cancel_listen_task_stops_listener(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试取消监听任务时调用 _stop_listener()。"""
        mock_client.add_handler = MagicMock()
        mock_client.remove_handler = MagicMock()
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(task.task_id)
        await executor._execute_listen_download(task)
        assert "_handler" in task.extra

        # 取消任务
        await executor.cancel_listen_task(task.task_id)
        mock_client.remove_handler.assert_called_once()
        assert "_handler" not in task.extra


# ============================================================
# 测试：Phase 3 - _handle_listen_download()
# ============================================================


class TestPhase3HandleListenDownload:
    """测试监听下载回调 _handle_listen_download()。"""

    @pytest.mark.asyncio
    async def test_handle_listen_download_no_media_skips(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试无媒体消息被跳过（不创建 TaskItem）。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        mock_message = MagicMock()
        mock_message.id = 999
        mock_message.media = None  # 无媒体

        await executor._handle_listen_download(task.task_id, mock_client, mock_message)

        # 验证没有创建 TaskItem
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 0

    @pytest.mark.asyncio
    async def test_handle_listen_download_creates_item(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试有媒体消息创建 TaskItem。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.video = MagicMock()
        mock_message.media.video.file_unique_id = "uniq123"
        mock_message.media.video.file_id = "file123"

        await executor._handle_listen_download(task.task_id, mock_client, mock_message)

        # 验证创建了 TaskItem
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 1
        assert updated.items[0].source_id == 12345

    @pytest.mark.asyncio
    async def test_handle_listen_download_dedup(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试同一 message_id 不会重复创建 TaskItem。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.video = MagicMock()
        mock_message.media.video.file_unique_id = "uniq123"
        mock_message.media.video.file_id = "file123"

        # 第一次调用
        await executor._handle_listen_download(task.task_id, mock_client, mock_message)
        # 第二次调用（同一消息）
        await executor._handle_listen_download(task.task_id, mock_client, mock_message)

        # 验证只创建了一个 TaskItem
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 1

    @pytest.mark.asyncio
    async def test_handle_listen_download_media_type_filter(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 media_types 过滤：不匹配的媒体类型被跳过。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "media_types": ["video"],  # 只接受 video
            },
        )

        # 创建一个 photo 消息（不应被接受）
        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.photo = MagicMock()
        mock_message.media.photo.file_unique_id = "photo123"
        mock_message.media.video = None

        await executor._handle_listen_download(task.task_id, mock_client, mock_message)

        # 验证没有创建 TaskItem（photo 不在 media_types 中）
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 0

    @pytest.mark.asyncio
    async def test_handle_listen_download_with_downloader(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试有 downloader 时执行下载并标记成功。"""
        mock_downloader = AsyncMock()
        mock_downloader.download_range.return_value = ["/downloads/file.mp4"]

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
            downloader=mock_downloader,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )

        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.video = MagicMock()
        mock_message.media.video.file_unique_id = "uniq123"
        mock_message.media.video.file_id = "file123"

        await executor._handle_listen_download(task.task_id, mock_client, mock_message)

        # 验证 downloader.download_range 被调用
        mock_downloader.download_range.assert_called_once()
        call_kwargs = mock_downloader.download_range.call_args[1]
        assert call_kwargs["chat_id"] == -1001234567890
        assert call_kwargs["start_id"] == 12345
        assert call_kwargs["end_id"] == 12345

        # 验证 item 状态为 SUCCESS
        updated = await task_manager.get_task(task.task_id)
        assert updated.items[0].status == ItemStatus.SUCCESS


# ============================================================
# 测试：Phase 3 - _handle_listen_forward()
# ============================================================


class TestPhase3HandleListenForward:
    """测试监听转发回调 _handle_listen_forward()。"""

    @pytest.mark.asyncio
    async def test_handle_listen_forward_no_media_skips(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试无媒体消息被跳过（不创建 TaskItem）。"""
        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "target_identifier": "@targetchannel",
                "target_chat_id": -1002000000000,
            },
        )

        mock_message = MagicMock()
        mock_message.id = 999
        mock_message.media = None  # 无媒体

        await executor._handle_listen_forward(task.task_id, mock_client, mock_message)

        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 0

    @pytest.mark.asyncio
    async def test_handle_listen_forward_creates_item(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试有媒体消息创建 TaskItem 并执行转发。"""
        mock_client.copy_message = AsyncMock(return_value=MagicMock(id=200))

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "target_identifier": "@targetchannel",
                "target_chat_id": -1002000000000,
            },
        )

        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.video = MagicMock()
        mock_message.media.video.file_unique_id = "uniq123"

        await executor._handle_listen_forward(task.task_id, mock_client, mock_message)

        # 验证创建了 TaskItem
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 1
        assert updated.items[0].source_id == 12345

        # 验证 copy_message 被调用
        mock_client.copy_message.assert_called_once_with(
            chat_id=-1002000000000,
            from_chat_id=-1001234567890,
            message_id=12345,
        )

    @pytest.mark.asyncio
    async def test_handle_listen_forward_dedup(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试同一 message_id 不会重复转发。"""
        mock_client.copy_message = AsyncMock(return_value=MagicMock(id=200))

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "target_identifier": "@targetchannel",
                "target_chat_id": -1002000000000,
            },
        )

        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.video = MagicMock()
        mock_message.media.video.file_unique_id = "uniq123"

        # 第一次调用
        await executor._handle_listen_forward(task.task_id, mock_client, mock_message)
        # 第二次调用（同一消息）
        await executor._handle_listen_forward(task.task_id, mock_client, mock_message)

        # 验证只转发了一次
        assert mock_client.copy_message.call_count == 1
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 1

    @pytest.mark.asyncio
    async def test_handle_listen_forward_media_type_filter(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 media_types 过滤：不匹配的媒体类型被跳过。"""
        mock_client.copy_message = AsyncMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            params={
                "source_identifier": "@testchannel",
                "target_identifier": "@targetchannel",
                "target_chat_id": -1002000000000,
                "media_types": ["video"],
            },
        )

        # 创建一个 photo 消息（不应被接受）
        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.media = MagicMock()
        mock_message.media.photo = MagicMock()
        mock_message.media.video = None

        await executor._handle_listen_forward(task.task_id, mock_client, mock_message)

        # 验证没有创建 TaskItem 也没有转发
        updated = await task_manager.get_task(task.task_id)
        assert len(updated.items) == 0
        mock_client.copy_message.assert_not_called()


# ============================================================
# 测试：Phase 3 - recover_listeners()
# ============================================================


class TestPhase3RecoverListeners:
    """测试监听任务恢复 recover_listeners()。"""

    @pytest.mark.asyncio
    async def test_recover_listeners_restores_handlers(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试 recover_listeners() 恢复 running 状态的监听任务 Handler。"""
        mock_client.add_handler = MagicMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        # 创建 running 状态的监听下载任务
        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(task.task_id)

        # 执行恢复
        await executor.recover_listeners()

        # 验证 add_handler 被调用（Handler 已重新注册）
        mock_client.add_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_listeners_no_tasks(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试没有 running 监听任务时 recover_listeners() 不报错。"""
        mock_client.add_handler = MagicMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        # 没有任何监听任务，恢复应该不报错
        await executor.recover_listeners()

        # 验证没有注册任何 Handler
        mock_client.add_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_recover_listeners_restores_both_types(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试同时恢复 LISTEN_DOWNLOAD 和 LISTEN_FORWARD 任务。"""
        mock_client.add_handler = MagicMock()

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        # 创建 running 状态的监听下载任务
        dl_task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(dl_task.task_id)

        # 创建 running 状态的监听转发任务
        fw_task = await task_manager.create_task(
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1002000000000,
            params={
                "source_identifier": "@testchannel2",
                "target_identifier": "@targetchannel",
                "target_chat_id": -1003000000000,
            },
        )
        await task_manager.start_task(fw_task.task_id)

        # 执行恢复
        await executor.recover_listeners()

        # 验证两个 Handler 都被注册
        assert mock_client.add_handler.call_count == 2

    @pytest.mark.asyncio
    async def test_recover_listeners_failed_task_marked_failed(
        self, task_manager, mock_client, mock_file_manager
    ):
        """测试恢复失败的任务被标记为 failed。"""
        # 模拟 add_handler 抛出异常
        mock_client.add_handler = MagicMock(side_effect=RuntimeError("Mock error"))

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )

        task = await task_manager.create_task(
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            params={"source_identifier": "@testchannel"},
        )
        await task_manager.start_task(task.task_id)

        # 执行恢复（add_handler 会抛出异常）
        await executor.recover_listeners()

        # 验证任务被标记为 failed
        updated = await task_manager.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "恢复失败" in (updated.error_message or "")
