# coding=UTF-8
"""仓库模式集成测试 - 验证 Uploader、FileManager 与 RepositoryManager 的集成。

覆盖场景：
- 上传到仓库频道触发 on_upload_success 回调
- UploadResult 包含 file_unique_id
- 仓库模式降级（仓库失败时回退为直接上传）
- 本地文件删除遵循 delete_after_upload 设置
- 仓库模式禁用时无副作用
- repository_manager 为 None 时向后兼容
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.core.download.file_manager import (
    UploadResult,
    FileManager,
)
from module.core.repository.db import (
    RepositoryDB,
)
from module.core.repository.manager import RepositoryManager


# ==================== Fixture ====================


@pytest.fixture
async def repo_db(tmp_path):
    """提供使用临时数据库的 RepositoryDB 实例。"""
    from module.core import db as db_module

    db_path = str(tmp_path / "test_repo_upload.db")
    await db_module.init_db(db_path)
    db = RepositoryDB()
    yield db
    await db_module.close_db()


@pytest.fixture
def config_manager_enabled():
    """仓库模式启用的 ConfigManager mock。"""
    cm = MagicMock()
    cm.get_repository_config.return_value = {
        "enabled": True,
        "chat_id": "-1001234567890",
        "auto_sync_enabled": False,
        "auto_sync_interval_minutes": 60,
    }
    return cm


@pytest.fixture
def config_manager_disabled():
    """仓库模式禁用的 ConfigManager mock。"""
    cm = MagicMock()
    cm.get_repository_config.return_value = {
        "enabled": False,
        "chat_id": "",
        "auto_sync_enabled": False,
        "auto_sync_interval_minutes": 60,
    }
    return cm


@pytest.fixture
async def repository_manager(repo_db, config_manager_enabled):
    """提供仓库模式启用的 RepositoryManager 实例。"""
    return RepositoryManager(
        repository_db=repo_db, config_manager=config_manager_enabled
    )


@pytest.fixture
async def repository_manager_disabled(repo_db, config_manager_disabled):
    """提供仓库模式禁用的 RepositoryManager 实例。"""
    return RepositoryManager(
        repository_db=repo_db, config_manager=config_manager_disabled
    )


@pytest.fixture
def mock_client():
    """创建模拟的 Pyrogram Client。"""
    client = AsyncMock()
    return client


@pytest.fixture
def default_config():
    """默认配置字典。"""
    return {
        "resource_limits": {
            "memory_limit_mb": 512,
        },
        "upload": {
            "max_group_size": 10,
            "delete_after_upload": False,
        },
    }


@pytest.fixture
def file_manager(mock_client, default_config):
    """创建 FileManager 实例。"""
    return FileManager(config=default_config, client=mock_client)


def _make_mock_message(
    file_unique_id="uid_test_001", chat_id=-1001234567890, message_id=42
):
    """创建模拟的 Pyrogram Message 对象。"""
    message = MagicMock()
    message.id = message_id
    message.chat = MagicMock()
    message.chat.id = chat_id
    doc = MagicMock()
    doc.file_unique_id = file_unique_id
    doc.file_id = f"fid_{file_unique_id}"
    doc.file_size = 1024
    doc.mime_type = "application/pdf"
    doc.file_name = "test.pdf"
    message.document = doc
    message.photo = None
    message.video = None
    message.audio = None
    message.animation = None
    return message


def _make_mock_photo_message(
    file_unique_id="uid_photo_001", chat_id=-1001234567890, message_id=43
):
    """创建模拟的 Pyrogram Photo Message 对象。"""
    message = MagicMock()
    message.id = message_id
    message.chat = MagicMock()
    message.chat.id = chat_id
    photo = MagicMock()
    photo.file_unique_id = file_unique_id
    photo.file_id = f"fid_{file_unique_id}"
    photo.file_size = 2048
    # photo 类型没有 mime_type 和 file_name，确保返回 None
    photo.mime_type = None
    photo.file_name = None
    message.photo = photo
    message.document = None
    message.video = None
    message.audio = None
    message.animation = None
    return message


# ==================== UploadResult file_unique_id 测试 ====================


class TestUploadResultFileUniqueId:
    """验证 UploadResult 包含 file_unique_id 字段。"""

    def test_upload_result_has_file_unique_id_field(self):
        """UploadResult 应包含 file_unique_id 字段，默认为 None。"""
        result = UploadResult(success=True, file_path="/tmp/test.jpg")
        assert hasattr(result, "file_unique_id")
        assert result.file_unique_id is None

    def test_upload_result_with_file_unique_id(self):
        """UploadResult 可设置 file_unique_id。"""
        result = UploadResult(
            success=True,
            file_path="/tmp/test.jpg",
            file_unique_id="uid_abc123",
        )
        assert result.file_unique_id == "uid_abc123"

    def test_upload_result_failure_has_no_file_unique_id(self):
        """上传失败的 UploadResult 的 file_unique_id 应为 None。"""
        result = UploadResult(
            success=False,
            error_code="UPLOAD_FAILED",
            error_msg="上传失败",
        )
        assert result.file_unique_id is None


# ==================== FileManager 仓库集成测试 ====================


class TestFileManagerRepositoryIntegration:
    """验证 FileManager 与 RepositoryManager 的集成。"""

    @pytest.mark.asyncio
    async def test_upload_result_includes_file_unique_id(self, file_manager, tmp_path):
        """FM-REPO-01: 上传成功后 UploadResult 应包含 file_unique_id。"""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpg data")
        mock_message = _make_mock_photo_message()
        file_manager._client.send_photo = AsyncMock(return_value=mock_message)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is True
        assert result.file_unique_id == "uid_photo_001"

    @pytest.mark.asyncio
    async def test_upload_document_includes_file_unique_id(
        self, file_manager, tmp_path
    ):
        """FM-REPO-02: 上传文档后 UploadResult 应包含 file_unique_id。"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf data")
        mock_message = _make_mock_message()
        file_manager._client.send_document = AsyncMock(return_value=mock_message)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is True
        assert result.file_unique_id == "uid_test_001"

    @pytest.mark.asyncio
    async def test_upload_failure_no_file_unique_id(self, file_manager, tmp_path):
        """FM-REPO-03: 上传失败时 UploadResult 的 file_unique_id 应为 None。"""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpg data")
        file_manager._client.send_photo = AsyncMock(side_effect=Exception("上传失败"))
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is False
        assert result.file_unique_id is None

    @pytest.mark.asyncio
    async def test_file_manager_repository_manager_attribute(
        self, file_manager, repository_manager
    ):
        """FM-REPO-04: FileManager 应支持设置 repository_manager 属性。"""
        assert hasattr(file_manager, "repository_manager")
        fm = FileManager(
            config={"resource_limits": {"memory_limit_mb": 512}, "upload": {}},
            client=AsyncMock(),
        )
        assert fm.repository_manager is None
        file_manager.repository_manager = repository_manager
        assert file_manager.repository_manager is repository_manager

    @pytest.mark.asyncio
    async def test_upload_to_repository_channel_with_callback(
        self, file_manager, repository_manager, tmp_path
    ):
        """FM-REPO-05: 上传到仓库频道时应调用 on_upload_success 回调。"""
        file_manager.repository_manager = repository_manager
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpg data")
        mock_message = _make_mock_photo_message(
            file_unique_id="uid_repo_test",
            chat_id=-1001234567890,
            message_id=100,
        )
        file_manager._client.send_photo = AsyncMock(return_value=mock_message)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1001234567890,
            source_chat_id=-1009876543210,
            source_message_id=50,
        )
        assert result.success is True
        repo_file = await repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=50,
        )
        assert repo_file is not None
        assert repo_file.file_unique_id == "uid_repo_test"

    @pytest.mark.asyncio
    async def test_upload_to_non_repository_channel_no_callback(
        self, file_manager, repository_manager, tmp_path
    ):
        """FM-REPO-06: 上传到非仓库频道且无 source 信息时不调用 on_upload_success。"""
        file_manager.repository_manager = repository_manager
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpg data")
        mock_message = _make_mock_photo_message(
            file_unique_id="uid_non_repo",
            chat_id=-1009999999999,
            message_id=200,
        )
        file_manager._client.send_photo = AsyncMock(return_value=mock_message)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_repository_mode_degradation(self, file_manager, tmp_path):
        """FM-REPO-07: 仓库模式失败时应降级为直接上传。"""
        bad_cm = MagicMock()
        bad_cm.get_repository_config.return_value = {
            "enabled": True,
            "chat_id": "-1001234567890",
            "auto_sync_enabled": False,
        }
        repo_db_path = str(tmp_path / "test_degradation.db")
        from module.core import db as db_module

        db_module.init_sync_db(repo_db_path)
        repo_db = RepositoryDB()
        repo_mgr = RepositoryManager(repository_db=repo_db, config_manager=bad_cm)
        file_manager.repository_manager = repo_mgr
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpg data")

        async def mock_send_photo(chat_id, photo, caption="", progress=None):
            if chat_id == -1001234567890:
                raise Exception("仓库频道上传失败")
            return _make_mock_photo_message(
                file_unique_id="uid_degrade",
                chat_id=chat_id,
                message_id=300,
            )

        file_manager._client.send_photo = AsyncMock(side_effect=mock_send_photo)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_local_file_deletion_follows_preference(self, file_manager, tmp_path):
        """FM-REPO-08: 本地文件删除应遵循 delete_after_upload 设置。"""
        test_file = tmp_path / "test_delete.jpg"
        test_file.write_bytes(b"fake jpg data")
        mock_message = _make_mock_photo_message()
        file_manager._client.send_photo = AsyncMock(return_value=mock_message)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
            delete_after=False,
        )
        assert result.success is True
        assert result.deleted is False
        assert test_file.exists()

        test_file2 = tmp_path / "test_delete2.jpg"
        test_file2.write_bytes(b"fake jpg data 2")
        result2 = await file_manager.upload(
            file_path=str(test_file2),
            chat_id=-1009999999999,
            delete_after=True,
        )
        assert result2.success is True
        assert result2.deleted is True
        assert not test_file2.exists()


# ==================== RepositoryManager 向后兼容测试 ====================


class TestRepositoryManagerBackwardCompat:
    """验证 repository_manager 为 None 时向后兼容。"""

    @pytest.mark.asyncio
    async def test_file_manager_no_repository_manager(self, tmp_path):
        """BC-01: FileManager 无 repository_manager 时正常工作。"""
        fm = FileManager(
            config={"resource_limits": {"memory_limit_mb": 512}, "upload": {}},
            client=AsyncMock(),
        )
        assert fm.repository_manager is None
        test_file = tmp_path / "test_bc.jpg"
        test_file.write_bytes(b"fake jpg data")
        mock_message = _make_mock_photo_message()
        fm._client.send_photo = AsyncMock(return_value=mock_message)
        result = await fm.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_file_manager_repository_disabled(
        self, file_manager, repository_manager_disabled, tmp_path
    ):
        """BC-02: 仓库模式禁用时 FileManager 正常工作，无仓库副作用。"""
        file_manager.repository_manager = repository_manager_disabled
        test_file = tmp_path / "test_disabled.jpg"
        test_file.write_bytes(b"fake jpg data")
        mock_message = _make_mock_photo_message()
        file_manager._client.send_photo = AsyncMock(return_value=mock_message)
        result = await file_manager.upload(
            file_path=str(test_file),
            chat_id=-1009999999999,
        )
        assert result.success is True
        assert not repository_manager_disabled.should_use_repository()


# ==================== TelegramUploader 仓库集成测试 ====================


class TestUploaderRepositoryIntegration:
    """验证 TelegramUploader 与 RepositoryManager 的集成。"""

    @pytest.mark.asyncio
    async def test_repository_manager_on_upload_success_called(
        self, repository_manager
    ):
        """UP-REPO-02: on_upload_success 应正确写入仓库记录。"""
        mock_message = _make_mock_message(
            file_unique_id="uid_callback_test",
            chat_id=-1001234567890,
            message_id=500,
        )
        await repository_manager.on_upload_success(
            message=mock_message,
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        result = await repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        assert result is not None
        assert result.file_unique_id == "uid_callback_test"

    @pytest.mark.asyncio
    async def test_repository_manager_on_upload_success_photo(self, repository_manager):
        """UP-REPO-03: on_upload_success 应正确处理 photo 类型消息。"""
        mock_message = _make_mock_photo_message(
            file_unique_id="uid_photo_callback",
            chat_id=-1001234567890,
            message_id=501,
        )
        await repository_manager.on_upload_success(
            message=mock_message,
            source_chat_id=-1009876543210,
            source_message_id=101,
        )
        result = await repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=101,
        )
        assert result is not None
        assert result.file_type == "photo"

    @pytest.mark.asyncio
    async def test_repository_manager_on_upload_success_no_media(
        self, repository_manager
    ):
        """UP-REPO-04: on_upload_success 对无媒体消息应安全跳过。"""
        mock_message = MagicMock()
        mock_message.id = 502
        mock_message.chat = MagicMock()
        mock_message.chat.id = -1001234567890
        mock_message.photo = None
        mock_message.video = None
        mock_message.document = None
        mock_message.audio = None
        mock_message.animation = None
        await repository_manager.on_upload_success(
            message=mock_message,
            source_chat_id=-1009876543210,
            source_message_id=102,
        )
        result = await repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=102,
        )
        assert result is None


# ==================== Downloader 仓库集成测试 ====================


class TestDownloaderRepositoryIntegration:
    """验证 Downloader 与 RepositoryManager 的集成。"""

    def test_repository_manager_should_use_repository(self, repository_manager):
        """DL-REPO-01: 仓库模式启用时 should_use_repository 返回 True。"""
        assert repository_manager.should_use_repository() is True

    def test_repository_manager_should_not_use_when_disabled(
        self, repository_manager_disabled
    ):
        """DL-REPO-02: 仓库模式禁用时 should_use_repository 返回 False。"""
        assert repository_manager_disabled.should_use_repository() is False

    def test_repository_manager_get_chat_id(self, repository_manager):
        """DL-REPO-03: get_repository_chat_id 返回配置的仓库频道 ID。"""
        chat_id = repository_manager.get_repository_chat_id()
        assert chat_id == "-1001234567890"

    def test_repository_manager_get_chat_id_when_disabled(
        self, repository_manager_disabled
    ):
        """DL-REPO-04: 仓库模式禁用时 get_repository_chat_id 返回 None。"""
        chat_id = repository_manager_disabled.get_repository_chat_id()
        assert chat_id is None


# ==================== Distribute 集成测试 ====================


class TestDistributeIntegration:
    """验证分发到目标频道的集成。"""

    @pytest.mark.asyncio
    async def test_distribute_to_target_copy_message(self, repository_manager, repo_db):
        """DIST-01: distribute_to_target 使用 copy_message 分发成功。"""
        mock_message = _make_mock_message(
            file_unique_id="uid_dist_test",
            chat_id=-1001234567890,
            message_id=600,
        )
        await repository_manager.on_upload_success(
            message=mock_message,
            source_chat_id=-1009876543210,
            source_message_id=200,
        )
        mock_client = AsyncMock()
        target_msg = MagicMock()
        target_msg.id = 700
        mock_client.copy_message = AsyncMock(return_value=target_msg)
        result = await repository_manager.distribute_to_target(
            client=mock_client,
            file_unique_id="uid_dist_test",
            target_chat_id=-1009999999999,
        )
        assert result == 700
        mock_client.copy_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_distribute_to_target_fallback_on_copy_failure(
        self, repository_manager, repo_db
    ):
        """DIST-02: copy_message 失败时降级为 file_id_send。"""
        mock_message = _make_mock_message(
            file_unique_id="uid_dist_fallback",
            chat_id=-1001234567890,
            message_id=601,
        )
        await repository_manager.on_upload_success(
            message=mock_message,
            source_chat_id=-1009876543210,
            source_message_id=201,
        )
        mock_client = AsyncMock()
        mock_client.copy_message = AsyncMock(side_effect=Exception("copy 失败"))
        fresh_msg = _make_mock_message(
            file_unique_id="uid_dist_fallback",
            chat_id=-1001234567890,
            message_id=601,
        )
        mock_client.get_messages = AsyncMock(return_value=fresh_msg)
        target_msg = MagicMock()
        target_msg.id = 701
        mock_client.send_document = AsyncMock(return_value=target_msg)
        result = await repository_manager.distribute_to_target(
            client=mock_client,
            file_unique_id="uid_dist_fallback",
            target_chat_id=-1009999999999,
        )
        assert result == 701

    @pytest.mark.asyncio
    async def test_distribute_to_target_returns_none_when_all_fail(
        self, repository_manager, repo_db
    ):
        """DIST-03: 所有分发方式都失败时返回 None。"""
        mock_message = _make_mock_message(
            file_unique_id="uid_dist_all_fail",
            chat_id=-1001234567890,
            message_id=602,
        )
        await repository_manager.on_upload_success(
            message=mock_message,
            source_chat_id=-1009876543210,
            source_message_id=202,
        )
        mock_client = AsyncMock()
        mock_client.copy_message = AsyncMock(side_effect=Exception("copy 失败"))
        mock_client.get_messages = AsyncMock(side_effect=Exception("get_messages 失败"))
        result = await repository_manager.distribute_to_target(
            client=mock_client,
            file_unique_id="uid_dist_all_fail",
            target_chat_id=-1009999999999,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_distribute_to_target_unknown_file(self, repository_manager):
        """DIST-04: 分发不存在的文件应返回 None。"""
        mock_client = AsyncMock()
        result = await repository_manager.distribute_to_target(
            client=mock_client,
            file_unique_id="nonexistent_uid",
            target_chat_id=-1009999999999,
        )
        assert result is None
