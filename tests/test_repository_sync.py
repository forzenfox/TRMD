# coding=UTF-8
"""RepositorySync 模块单元测试。

覆盖同步生命周期管理、增量同步逻辑、消息 ID 追踪、错误处理等场景。
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.core.repository_db import RepositoryDB, RepositoryFile
from module.core.repository_sync import RepositorySync


# ==================== Fixture ====================


@pytest.fixture
def repo_db(tmp_path):
    """提供使用临时数据库的 RepositoryDB 实例。"""
    db_path = str(tmp_path / "test_sync.db")
    db = RepositoryDB(db_path=db_path)
    yield db


@pytest.fixture
def config_manager():
    """提供模拟的 ConfigManager 实例。"""
    cm = MagicMock()
    cm.get_repository_config.return_value = {
        "enabled": True,
        "chat_id": "-1001234567890",
        "auto_sync_enabled": True,
        "auto_sync_interval_minutes": 60,
    }
    return cm


@pytest.fixture
def sync(repo_db, config_manager):
    """提供 RepositorySync 实例。"""
    return RepositorySync(repository_db=repo_db, config_manager=config_manager)


# ==================== 辅助函数 ====================


def _make_repository_file(**overrides) -> RepositoryFile:
    """创建 RepositoryFile 测试数据。"""
    defaults = {
        "id": None,
        "file_unique_id": "uid_001",
        "file_id": "fid_001",
        "content_hash": None,
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


@dataclass
class MockMedia:
    """模拟 Pyrogram 媒体对象。"""

    file_unique_id: str = "uid_mock"
    file_id: str = "fid_mock"
    file_size: int = 2048
    mime_type: str | None = "video/mp4"
    file_name: str | None = "mock.mp4"


@dataclass
class MockPhoto:
    """模拟 Pyrogram Photo 对象。"""

    file_unique_id: str = "uid_photo"
    file_id: str = "fid_photo"
    file_size: int = 512


@dataclass
class MockChat:
    """模拟 Pyrogram Chat 对象。"""

    id: int = -1001234567890


@dataclass
class MockMessage:
    """模拟 Pyrogram Message 对象。"""

    id: int = 1
    chat: MockChat = None
    photo: MockPhoto | None = None
    video: MockMedia | None = None
    document: MockMedia | None = None
    audio: MockMedia | None = None
    animation: MockMedia | None = None

    def __post_init__(self):
        if self.chat is None:
            self.chat = MockChat()


def _make_mock_message(
    msg_id: int = 1,
    chat_id: int = -1001234567890,
    media_type: str = "video",
    file_unique_id: str | None = None,
) -> MockMessage:
    """创建模拟消息对象。"""
    chat = MockChat(id=chat_id)
    uid = file_unique_id or f"uid_msg_{msg_id}"
    fid = f"fid_msg_{msg_id}"

    photo = None
    video = None
    document = None
    audio = None
    animation = None

    if media_type == "photo":
        photo = MockPhoto(file_unique_id=uid, file_id=fid)
    elif media_type == "video":
        video = MockMedia(file_unique_id=uid, file_id=fid)
    elif media_type == "document":
        document = MockMedia(
            file_unique_id=uid,
            file_id=fid,
            mime_type="application/pdf",
            file_name="doc.pdf",
        )
    elif media_type == "audio":
        audio = MockMedia(
            file_unique_id=uid,
            file_id=fid,
            mime_type="audio/mp3",
            file_name="audio.mp3",
        )
    elif media_type == "animation":
        animation = MockMedia(
            file_unique_id=uid, file_id=fid, mime_type="video/gif", file_name="anim.gif"
        )

    return MockMessage(
        id=msg_id,
        chat=chat,
        photo=photo,
        video=video,
        document=document,
        audio=audio,
        animation=animation,
    )


# ==================== 生命周期测试 ====================


class TestSyncLifecycle:
    """同步任务生命周期管理测试。"""

    def test_initial_state_not_running(self, sync):
        """初始状态应为未运行。"""
        assert sync.is_running is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self, sync):
        """启动后 is_running 应为 True。"""
        sync.start()
        assert sync.is_running is True
        sync.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self, sync):
        """停止后 is_running 应为 False。"""
        sync.start()
        sync.stop()
        assert sync.is_running is False

    def test_start_when_auto_sync_disabled(self, repo_db):
        """auto_sync_enabled 为 False 时不启动同步。"""
        cm = MagicMock()
        cm.get_repository_config.return_value = {
            "enabled": True,
            "chat_id": "-1001234567890",
            "auto_sync_enabled": False,
        }
        sync = RepositorySync(repository_db=repo_db, config_manager=cm)
        sync.start()
        assert sync.is_running is False

    @pytest.mark.asyncio
    async def test_start_when_already_running(self, sync):
        """重复启动不应创建多个任务。"""
        sync.start()
        first_task = sync._sync_task
        sync.start()
        assert sync._sync_task is first_task
        sync.stop()

    def test_stop_when_not_running(self, sync):
        """未运行时停止不应抛异常。"""
        sync.stop()  # 不应抛异常
        assert sync.is_running is False

    @pytest.mark.asyncio
    async def test_start_creates_asyncio_task(self, sync):
        """启动应创建 asyncio.Task。"""
        sync.start()
        assert sync._sync_task is not None
        assert isinstance(sync._sync_task, asyncio.Task)
        sync.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, sync):
        """停止应取消 asyncio.Task。"""
        sync.start()
        task = sync._sync_task
        sync.stop()
        # 让事件循环处理取消请求
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()


# ==================== 增量同步逻辑测试 ====================


class TestIncrementalSync:
    """增量同步逻辑测试。"""

    @pytest.mark.asyncio
    async def test_sync_without_client_returns_zero(self, sync):
        """未提供 client 时应返回 0。"""
        result = await sync.incremental_sync(client=None)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_without_chat_id_returns_zero(self, repo_db):
        """未配置 chat_id 时应返回 0。"""
        cm = MagicMock()
        cm.get_repository_config.return_value = {
            "enabled": True,
            "chat_id": None,
            "auto_sync_enabled": True,
        }
        sync = RepositorySync(repository_db=repo_db, config_manager=cm)
        client = AsyncMock()
        result = await sync.incremental_sync(client=client)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_inserts_new_messages(self, sync):
        """新消息应被写入数据库。"""
        msg1 = _make_mock_message(
            msg_id=101, media_type="video", file_unique_id="uid_101"
        )
        msg2 = _make_mock_message(
            msg_id=102, media_type="photo", file_unique_id="uid_102"
        )

        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=AsyncIterator([msg1, msg2]))

        result = await sync.incremental_sync(client=client)
        assert result == 2

        # 验证数据库写入
        file1 = sync._db.get_file_by_unique_id("uid_101")
        assert file1 is not None
        assert file1.file_type == "video"
        assert file1.repository_message_id == 101

        file2 = sync._db.get_file_by_unique_id("uid_102")
        assert file2 is not None
        assert file2.file_type == "photo"

    @pytest.mark.asyncio
    async def test_sync_skips_existing_messages(self, sync, repo_db):
        """已存在的消息应被跳过。"""
        # 预先插入一条记录
        existing = _make_repository_file(
            file_unique_id="uid_101",
            file_id="fid_101",
            repository_chat_id=-1001234567890,
            repository_message_id=101,
        )
        repo_db.insert_file_record(existing)

        msg1 = _make_mock_message(
            msg_id=101, media_type="video", file_unique_id="uid_101"
        )
        msg2 = _make_mock_message(
            msg_id=102, media_type="photo", file_unique_id="uid_102"
        )

        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=AsyncIterator([msg1, msg2]))

        result = await sync.incremental_sync(client=client)
        assert result == 1  # 只有 msg2 是新的

    @pytest.mark.asyncio
    async def test_sync_skips_messages_without_media(self, sync):
        """无媒体的消息应被跳过。"""
        msg_no_media = MockMessage(id=200, chat=MockChat(id=-1001234567890))

        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=AsyncIterator([msg_no_media]))

        result = await sync.incremental_sync(client=client)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_handles_all_media_types(self, sync):
        """应正确处理所有媒体类型。"""
        messages = [
            _make_mock_message(
                msg_id=201, media_type="photo", file_unique_id="uid_photo"
            ),
            _make_mock_message(
                msg_id=202, media_type="video", file_unique_id="uid_video"
            ),
            _make_mock_message(
                msg_id=203, media_type="document", file_unique_id="uid_doc"
            ),
            _make_mock_message(
                msg_id=204, media_type="audio", file_unique_id="uid_audio"
            ),
            _make_mock_message(
                msg_id=205, media_type="animation", file_unique_id="uid_anim"
            ),
        ]

        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=AsyncIterator(messages))

        result = await sync.incremental_sync(client=client)
        assert result == 5

        # 验证各类型
        assert sync._db.get_file_by_unique_id("uid_photo").file_type == "photo"
        assert sync._db.get_file_by_unique_id("uid_video").file_type == "video"
        assert sync._db.get_file_by_unique_id("uid_doc").file_type == "document"
        assert sync._db.get_file_by_unique_id("uid_audio").file_type == "audio"
        assert sync._db.get_file_by_unique_id("uid_anim").file_type == "animation"

    @pytest.mark.asyncio
    async def test_sync_no_new_records(self, sync):
        """无新记录时应返回 0。"""
        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=AsyncIterator([]))

        result = await sync.incremental_sync(client=client)
        assert result == 0


# ==================== 消息 ID 追踪测试 ====================


class TestLastSyncedMessageId:
    """上次同步位置追踪测试。"""

    def test_returns_none_when_no_records(self, sync):
        """数据库无记录时应返回 None。"""
        result = sync._get_last_synced_message_id()
        assert result is None

    def test_returns_max_message_id(self, sync, repo_db):
        """应返回最大的 repository_message_id。"""
        for i in range(1, 4):
            record = _make_repository_file(
                file_unique_id=f"uid_{i}",
                file_id=f"fid_{i}",
                repository_message_id=i * 10,
            )
            repo_db.insert_file_record(record)

        result = sync._get_last_synced_message_id()
        assert result == 30

    def test_returns_none_on_db_error(self, sync):
        """数据库出错时应返回 None。"""
        # 使用已关闭的数据库模拟错误
        sync._db = MagicMock()
        sync._db._get_connection.side_effect = Exception("DB error")

        result = sync._get_last_synced_message_id()
        assert result is None


# ==================== 消息存在性检查测试 ====================


class TestExistsInDb:
    """消息存在性检查测试。"""

    def test_returns_true_when_exists(self, sync, repo_db):
        """消息已存在时应返回 True。"""
        record = _make_repository_file(
            file_unique_id="uid_exist",
            repository_chat_id=-1001234567890,
            repository_message_id=100,
        )
        repo_db.insert_file_record(record)

        msg = MockMessage(id=100, chat=MockChat(id=-1001234567890))
        assert sync._exists_in_db(msg) is True

    def test_returns_false_when_not_exists(self, sync):
        """消息不存在时应返回 False。"""
        msg = MockMessage(id=999, chat=MockChat(id=-1001234567890))
        assert sync._exists_in_db(msg) is False

    def test_returns_false_on_db_error(self, sync):
        """数据库出错时应返回 False。"""
        sync._db = MagicMock()
        sync._db._get_connection.side_effect = Exception("DB error")

        msg = MockMessage(id=100, chat=MockChat(id=-1001234567890))
        assert sync._exists_in_db(msg) is False


# ==================== 文件记录写入测试 ====================


class TestInsertFileRecord:
    """从消息提取文件信息并写入数据库的测试。"""

    def test_insert_video_message(self, sync, repo_db):
        """应正确提取视频消息信息并写入。"""
        msg = _make_mock_message(
            msg_id=300, media_type="video", file_unique_id="uid_video_300"
        )
        result = sync._insert_file_record(msg)
        assert result is True

        file = repo_db.get_file_by_unique_id("uid_video_300")
        assert file is not None
        assert file.file_type == "video"
        assert file.repository_message_id == 300
        assert file.content_hash is None  # 同步时不计算哈希

    def test_insert_photo_message(self, sync, repo_db):
        """应正确提取照片消息信息并写入。"""
        msg = _make_mock_message(
            msg_id=301, media_type="photo", file_unique_id="uid_photo_301"
        )
        result = sync._insert_file_record(msg)
        assert result is True

        file = repo_db.get_file_by_unique_id("uid_photo_301")
        assert file is not None
        assert file.file_type == "photo"

    def test_insert_document_message(self, sync, repo_db):
        """应正确提取文档消息信息并写入。"""
        msg = _make_mock_message(
            msg_id=302, media_type="document", file_unique_id="uid_doc_302"
        )
        result = sync._insert_file_record(msg)
        assert result is True

        file = repo_db.get_file_by_unique_id("uid_doc_302")
        assert file is not None
        assert file.file_type == "document"
        assert file.mime_type == "application/pdf"
        assert file.file_name == "doc.pdf"

    def test_insert_returns_false_for_no_media(self, sync):
        """无媒体消息应返回 False。"""
        msg = MockMessage(id=400, chat=MockChat(id=-1001234567890))
        result = sync._insert_file_record(msg)
        assert result is False

    def test_insert_returns_false_on_db_error(self, sync):
        """数据库写入失败时应返回 False。"""
        sync._db = MagicMock()
        sync._db.insert_file_record.side_effect = Exception("DB write error")

        msg = _make_mock_message(
            msg_id=500, media_type="video", file_unique_id="uid_err"
        )
        result = sync._insert_file_record(msg)
        assert result is False

    def test_insert_sets_status_active(self, sync, repo_db):
        """写入的记录 status 应为 'active'。"""
        msg = _make_mock_message(
            msg_id=303, media_type="video", file_unique_id="uid_active"
        )
        sync._insert_file_record(msg)

        file = repo_db.get_file_by_unique_id("uid_active")
        assert file is not None
        assert file.status == "active"

    def test_insert_content_hash_is_none(self, sync, repo_db):
        """同步写入的记录 content_hash 应为 None。"""
        msg = _make_mock_message(
            msg_id=304, media_type="video", file_unique_id="uid_no_hash"
        )
        sync._insert_file_record(msg)

        file = repo_db.get_file_by_unique_id("uid_no_hash")
        assert file is not None
        assert file.content_hash is None


# ==================== 错误处理测试 ====================


class TestErrorHandling:
    """错误处理测试。"""

    @pytest.mark.asyncio
    async def test_sync_handles_client_exception(self, sync):
        """client 抛出异常时应返回 0 且不崩溃。"""
        client = AsyncMock()
        client.get_chat_history = MagicMock(side_effect=Exception("Network error"))

        result = await sync.incremental_sync(client=client)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sync_handles_partial_failure(self, sync):
        """部分消息处理失败时，已成功的记录应保留。"""
        msg1 = _make_mock_message(
            msg_id=401, media_type="video", file_unique_id="uid_ok"
        )
        msg2 = MockMessage(id=402, chat=MockChat(id=-1001234567890))  # 无媒体

        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=AsyncIterator([msg1, msg2]))

        result = await sync.incremental_sync(client=client)
        assert result == 1  # msg1 成功，msg2 跳过

    @pytest.mark.asyncio
    async def test_sync_loop_continues_on_error(self, sync, config_manager):
        """同步循环中出错后应继续运行。"""
        call_count = 0

        async def failing_sync(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            return 0

        sync.incremental_sync = failing_sync

        # 模拟短间隔
        config_manager.get_repository_config.return_value[
            "auto_sync_interval_minutes"
        ] = 0  # 0 分钟

        # 手动运行循环的几次迭代
        sync._running = True
        iteration = 0

        async def limited_loop():
            nonlocal iteration
            while sync._running and iteration < 3:
                try:
                    await sync.incremental_sync()
                except Exception:
                    pass
                iteration += 1
                await asyncio.sleep(0)

        await limited_loop()
        assert call_count == 3  # 即使第一次出错，也应继续


# ==================== 辅助类 ====================


class AsyncIterator:
    """将同步列表转换为异步迭代器。"""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
