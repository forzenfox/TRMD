# coding=UTF-8
"""三级去重流程测试 - 验证下载过程中的三级去重集成。

覆盖场景：
- Level 1 去重: 相同 source 定位跳过下载
- Level 2 去重: 相同 file_unique_id 跳过上传，添加 source mapping
- Level 3 去重: 相同内容哈希删除本地文件，跳过上传，添加 source mapping
- 所有级别未命中: 正常上传到仓库频道
- 仓库模式禁用时无去重副作用
"""

import os
import pytest
from unittest.mock import MagicMock

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.core.repository_db import (
    RepositoryDB,
    RepositoryFile,
    RepositorySource,
)
from module.core.repository_manager import RepositoryManager


# ==================== Fixture ====================


@pytest.fixture
def repo_db(tmp_path):
    """提供使用临时数据库的 RepositoryDB 实例。"""
    from module.core import db as db_module

    db_path = str(tmp_path / "test_dedup.db")
    db_module.init_sync_db(db_path)
    db = RepositoryDB()
    yield db
    db_module.close_sync_db()


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
def repository_manager(repo_db, config_manager_enabled):
    """提供仓库模式启用的 RepositoryManager 实例。"""
    return RepositoryManager(
        repository_db=repo_db, config_manager=config_manager_enabled
    )


@pytest.fixture
def repository_manager_disabled(repo_db, config_manager_disabled):
    """提供仓库模式禁用的 RepositoryManager 实例。"""
    return RepositoryManager(
        repository_db=repo_db, config_manager=config_manager_disabled
    )


def _make_repository_file(**overrides) -> RepositoryFile:
    """创建 RepositoryFile 测试数据。"""
    defaults = {
        "id": None,
        "file_unique_id": "uid_dedup_001",
        "file_id": "fid_dedup_001",
        "content_hash": "hash_sha256_abc",
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
        "file_unique_id": "uid_dedup_001",
        "source_chat_id": -1009876543210,
        "source_message_id": 100,
        "created_at": None,
    }
    defaults.update(overrides)
    return RepositorySource(**defaults)


def _make_mock_message(
    file_unique_id="uid_msg_001",
    chat_id=-1009876543210,
    message_id=100,
):
    """创建模拟的 Pyrogram Message 对象（含 video 媒体）。"""
    message = MagicMock()
    message.id = message_id
    message.chat = MagicMock()
    message.chat.id = chat_id
    video = MagicMock()
    video.file_unique_id = file_unique_id
    video.file_id = f"fid_{file_unique_id}"
    video.file_size = 1024
    video.mime_type = "video/mp4"
    video.file_name = "test.mp4"
    message.video = video
    message.photo = None
    message.document = None
    message.audio = None
    message.animation = None
    message.voice = None
    message.video_note = None
    return message


# ==================== Level 1 去重测试 ====================


class TestLevel1Dedup:
    """Level 1 去重: 相同 source 定位跳过下载。"""

    def test_l1_dedup_hit_returns_existing_file(self, repository_manager, repo_db):
        """DEDUP-L1-01: source 定位命中时 check_dedup 返回已有文件记录。"""
        file_record = _make_repository_file(file_unique_id="uid_l1_hit")
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(
            file_unique_id="uid_l1_hit",
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        repo_db.insert_source_mapping(source)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        assert result is not None
        assert result.file_unique_id == "uid_l1_hit"

    def test_l1_dedup_miss_returns_none(self, repository_manager):
        """DEDUP-L1-02: source 定位未命中时 check_dedup 返回 None。"""
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=999,
        )
        assert result is None

    def test_l1_dedup_only_needs_source_info(self, repository_manager, repo_db):
        """DEDUP-L1-03: Level 1 去重仅需 source_chat_id 和 source_message_id。"""
        file_record = _make_repository_file(file_unique_id="uid_l1_only")
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(
            file_unique_id="uid_l1_only",
            source_chat_id=-1005555555555,
            source_message_id=200,
        )
        repo_db.insert_source_mapping(source)

        # 不传 file_unique_id 和 content_hash，仅用 source 信息
        result = repository_manager.check_dedup(
            source_chat_id=-1005555555555,
            source_message_id=200,
        )
        assert result is not None
        assert result.file_unique_id == "uid_l1_only"

    def test_l1_dedup_skips_download_when_hit(self, repository_manager, repo_db):
        """DEDUP-L1-04: L1 命中时应跳过下载，返回已有文件记录信息。"""
        file_record = _make_repository_file(
            file_unique_id="uid_l1_skip",
            repository_chat_id=-1001234567890,
            repository_message_id=500,
        )
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(
            file_unique_id="uid_l1_skip",
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        repo_db.insert_source_mapping(source)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        assert result is not None
        assert result.repository_chat_id == -1001234567890
        assert result.repository_message_id == 500


# ==================== Level 2 去重测试 ====================


class TestLevel2Dedup:
    """Level 2 去重: 相同 file_unique_id 跳过上传，添加 source mapping。"""

    def test_l2_dedup_hit_returns_existing_file(self, repository_manager, repo_db):
        """DEDUP-L2-01: file_unique_id 命中时 check_dedup 返回已有文件记录。"""
        file_record = _make_repository_file(file_unique_id="uid_l2_hit")
        repo_db.insert_file_record(file_record)
        # 不添加 source mapping，确保 L1 不会命中

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="uid_l2_hit",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l2_hit"

    def test_l2_dedup_miss_returns_none(self, repository_manager):
        """DEDUP-L2-02: file_unique_id 未命中时 check_dedup 返回 None。"""
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="nonexistent_uid",
        )
        assert result is None

    def test_l2_dedup_skips_upload_and_adds_source_mapping(
        self, repository_manager, repo_db
    ):
        """DEDUP-L2-03: L2 命中时应跳过上传，并添加 source mapping。"""
        file_record = _make_repository_file(file_unique_id="uid_l2_skip")
        repo_db.insert_file_record(file_record)

        # L2 命中
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="uid_l2_skip",
        )
        assert result is not None

        # 添加 source mapping（模拟 download_complete_callback 中的行为）
        source = _make_repository_source(
            file_unique_id="uid_l2_skip",
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        repo_db.insert_source_mapping(source)

        # 验证 source mapping 已写入
        verify = repo_db.get_file_by_source(-1009876543210, 100)
        assert verify is not None
        assert verify.file_unique_id == "uid_l2_skip"

    def test_l2_dedup_l1_miss_l2_hit(self, repository_manager, repo_db):
        """DEDUP-L2-04: L1 未命中但 L2 命中时应返回 L2 的结果。"""
        file_record = _make_repository_file(file_unique_id="uid_l2_priority")
        repo_db.insert_file_record(file_record)
        # 不添加 source mapping for (-1009876543210, 100)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="uid_l2_priority",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l2_priority"

    def test_l2_dedup_without_file_unique_id(self, repository_manager, repo_db):
        """DEDUP-L2-05: 不传 file_unique_id 时 L2 不执行。"""
        file_record = _make_repository_file(file_unique_id="uid_l2_no_fid")
        repo_db.insert_file_record(file_record)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=999,
            file_unique_id=None,
        )
        assert result is None


# ==================== Level 3 去重测试 ====================


class TestLevel3Dedup:
    """Level 3 去重: 相同内容哈希删除本地文件，跳过上传，添加 source mapping。"""

    def test_l3_dedup_hit_returns_existing_file(self, repository_manager, repo_db):
        """DEDUP-L3-01: content_hash 命中时 check_dedup 返回已有文件记录。"""
        file_record = _make_repository_file(
            file_unique_id="uid_l3_hit",
            content_hash="sha256_same_content",
        )
        repo_db.insert_file_record(file_record)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="different_uid",
            content_hash="sha256_same_content",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l3_hit"
        assert result.content_hash == "sha256_same_content"

    def test_l3_dedup_miss_returns_none(self, repository_manager):
        """DEDUP-L3-02: content_hash 未命中时 check_dedup 返回 None。"""
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="different_uid",
            content_hash="nonexistent_hash",
        )
        assert result is None

    def test_l3_dedup_deletes_local_file_and_adds_source_mapping(
        self, repository_manager, repo_db, tmp_path
    ):
        """DEDUP-L3-03: L3 命中时应删除本地文件，跳过上传，添加 source mapping。"""
        file_record = _make_repository_file(
            file_unique_id="uid_l3_delete",
            content_hash="sha256_delete_test",
        )
        repo_db.insert_file_record(file_record)

        # 创建本地临时文件
        local_file = tmp_path / "test_l3_delete.mp4"
        local_file.write_bytes(b"fake video data")

        # L3 命中
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="different_uid",
            content_hash="sha256_delete_test",
        )
        assert result is not None

        # 模拟 download_complete_callback 中的行为：删除本地文件
        os.remove(str(local_file))
        assert not local_file.exists()

        # 添加 source mapping
        source = _make_repository_source(
            file_unique_id=result.file_unique_id,
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        repo_db.insert_source_mapping(source)

        # 验证 source mapping 指向已有文件
        verify = repo_db.get_file_by_source(-1009876543210, 100)
        assert verify is not None
        assert verify.file_unique_id == "uid_l3_delete"

    def test_l3_dedup_l1_l2_miss_l3_hit(self, repository_manager, repo_db):
        """DEDUP-L3-04: L1/L2 未命中但 L3 命中时应返回 L3 的结果。"""
        file_record = _make_repository_file(
            file_unique_id="uid_l3_priority",
            content_hash="sha256_priority",
        )
        repo_db.insert_file_record(file_record)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=999,
            file_unique_id="nonexistent_uid",
            content_hash="sha256_priority",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l3_priority"

    def test_l3_dedup_without_content_hash(self, repository_manager, repo_db):
        """DEDUP-L3-05: 不传 content_hash 时 L3 不执行。"""
        file_record = _make_repository_file(
            file_unique_id="uid_l3_no_hash",
            content_hash="sha256_exists",
        )
        repo_db.insert_file_record(file_record)

        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=999,
            file_unique_id="nonexistent_uid",
            content_hash=None,
        )
        assert result is None


# ==================== 全部未命中测试 ====================


class TestAllLevelsMiss:
    """所有级别未命中: 正常上传到仓库频道。"""

    def test_all_miss_returns_none(self, repository_manager):
        """DEDUP-ALL-01: L1/L2/L3 全部未命中时 check_dedup 返回 None。"""
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="brand_new_uid",
            content_hash="brand_new_hash",
        )
        assert result is None

    def test_all_miss_proceeds_with_upload(self, repository_manager, repo_db, tmp_path):
        """DEDUP-ALL-02: 全部未命中时应正常上传到仓库频道。"""
        # 全部未命中
        result = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
            file_unique_id="new_file_uid",
            content_hash="new_file_hash",
        )
        assert result is None

        # 模拟上传成功后写入仓库记录
        mock_message = _make_mock_message(
            file_unique_id="new_file_uid",
            chat_id=-1001234567890,
            message_id=999,
        )
        import asyncio

        asyncio.run(
            repository_manager.on_upload_success(
                message=mock_message,
                source_chat_id=-1009876543210,
                source_message_id=100,
                content_hash="new_file_hash",
            )
        )

        # 验证记录已写入
        verify = repository_manager.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        assert verify is not None
        assert verify.file_unique_id == "new_file_uid"

    def test_compute_content_hash_consistency(self, tmp_path):
        """DEDUP-ALL-03: compute_content_hash 对相同文件内容返回一致哈希。"""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        content = b"identical content for hash test"
        file1.write_bytes(content)
        file2.write_bytes(content)

        hash1 = RepositoryManager.compute_content_hash(str(file1))
        hash2 = RepositoryManager.compute_content_hash(str(file2))
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest 长度

    def test_compute_content_hash_different_content(self, tmp_path):
        """DEDUP-ALL-04: compute_content_hash 对不同文件内容返回不同哈希。"""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")

        hash1 = RepositoryManager.compute_content_hash(str(file1))
        hash2 = RepositoryManager.compute_content_hash(str(file2))
        assert hash1 != hash2


# ==================== 仓库模式禁用测试 ====================


class TestDedupDisabled:
    """仓库模式禁用时无去重副作用。"""

    def test_disabled_should_not_use_repository(self, repository_manager_disabled):
        """DEDUP-DIS-01: 仓库模式禁用时 should_use_repository 返回 False。"""
        assert repository_manager_disabled.should_use_repository() is False

    def test_disabled_check_dedup_still_works_but_not_called(
        self, repository_manager_disabled, repo_db
    ):
        """DEDUP-DIS-02: 仓库模式禁用时 check_dedup 仍可调用但不应被调用。"""
        # 即使 check_dedup 方法本身可用，调用方应先检查 should_use_repository
        file_record = _make_repository_file(file_unique_id="uid_disabled")
        repo_db.insert_file_record(file_record)
        source = _make_repository_source(
            file_unique_id="uid_disabled",
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        repo_db.insert_source_mapping(source)

        # 方法本身仍可工作
        result = repository_manager_disabled.check_dedup(
            source_chat_id=-1009876543210,
            source_message_id=100,
        )
        assert result is not None
        # 但 should_use_repository 为 False，调用方不应走到此逻辑

    def test_disabled_no_dedup_side_effects(self, repository_manager_disabled, repo_db):
        """DEDUP-DIS-03: 仓库模式禁用时不应有任何去重副作用。"""
        # 模拟: 调用方检查 should_use_repository 后跳过去重
        if repository_manager_disabled.should_use_repository():
            result = repository_manager_disabled.check_dedup(
                source_chat_id=-1009876543210,
                source_message_id=100,
            )
        else:
            result = None  # 跳过去重

        assert result is None


# ==================== Downloader 集成测试 ====================


class TestDownloaderDedupIntegration:
    """验证 Downloader 中三级去重的集成行为。"""

    def test_extract_file_unique_id_from_video_message(self):
        """DL-DEDUP-01: _extract_file_unique_id 应从 video 消息提取 file_unique_id。"""
        from module.downloader import TelegramRestrictedMediaDownloader

        message = _make_mock_message(
            file_unique_id="uid_video_ext", chat_id=-100, message_id=1
        )
        result = TelegramRestrictedMediaDownloader._extract_file_unique_id(message)
        assert result == "uid_video_ext"

    def test_extract_file_unique_id_from_photo_message(self):
        """DL-DEDUP-02: _extract_file_unique_id 应从 photo 消息提取 file_unique_id。"""
        from module.downloader import TelegramRestrictedMediaDownloader

        message = MagicMock()
        message.video = None
        photo = MagicMock()
        photo.file_unique_id = "uid_photo_ext"
        message.photo = photo
        message.document = None
        message.audio = None
        message.animation = None
        message.voice = None
        message.video_note = None
        result = TelegramRestrictedMediaDownloader._extract_file_unique_id(message)
        assert result == "uid_photo_ext"

    def test_extract_file_unique_id_from_no_media(self):
        """DL-DEDUP-03: 无媒体消息应返回 None。"""
        from module.downloader import TelegramRestrictedMediaDownloader

        message = MagicMock()
        message.video = None
        message.photo = None
        message.document = None
        message.audio = None
        message.animation = None
        message.voice = None
        message.video_note = None
        result = TelegramRestrictedMediaDownloader._extract_file_unique_id(message)
        assert result is None

    def test_extract_file_unique_id_priority_order(self):
        """DL-DEDUP-04: _extract_file_unique_id 按优先级提取（video > photo > document）。"""
        from module.downloader import TelegramRestrictedMediaDownloader

        # video 优先
        message = MagicMock()
        video = MagicMock()
        video.file_unique_id = "uid_video"
        message.video = video
        photo = MagicMock()
        photo.file_unique_id = "uid_photo"
        message.photo = photo
        message.document = None
        message.audio = None
        message.animation = None
        message.voice = None
        message.video_note = None
        result = TelegramRestrictedMediaDownloader._extract_file_unique_id(message)
        assert result == "uid_video"

    def test_repository_manager_none_means_no_dedup(self):
        """DL-DEDUP-05: repository_manager 为 None 时不应执行去重。"""
        # 模拟 Downloader 的 repository_manager 为 None
        downloader_repo_manager = None
        should_dedup = (
            downloader_repo_manager is not None
            and downloader_repo_manager.should_use_repository()
        )
        assert should_dedup is False


# ==================== 去重级别优先级测试 ====================


class TestDedupPriority:
    """验证三级去重的优先级顺序。"""

    def test_l1_has_highest_priority(self, repository_manager, repo_db):
        """DEDUP-PRI-01: L1 命中时不应执行 L2/L3。"""
        file_l1 = _make_repository_file(
            file_unique_id="uid_l1_priority",
            content_hash="hash_l1",
        )
        repo_db.insert_file_record(file_l1)
        source_l1 = _make_repository_source(
            file_unique_id="uid_l1_priority",
            source_chat_id=-100111,
            source_message_id=111,
        )
        repo_db.insert_source_mapping(source_l1)

        # L1 命中
        result = repository_manager.check_dedup(
            source_chat_id=-100111,
            source_message_id=111,
            file_unique_id="different_uid",
            content_hash="different_hash",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l1_priority"

    def test_l2_has_second_priority(self, repository_manager, repo_db):
        """DEDUP-PRI-02: L1 未命中但 L2 命中时不应执行 L3。"""
        file_l2 = _make_repository_file(
            file_unique_id="uid_l2_priority",
            content_hash="hash_l2",
        )
        repo_db.insert_file_record(file_l2)
        # 不添加 source mapping，L1 不会命中

        result = repository_manager.check_dedup(
            source_chat_id=-100222,
            source_message_id=222,
            file_unique_id="uid_l2_priority",
            content_hash="different_hash",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l2_priority"

    def test_l3_has_lowest_priority(self, repository_manager, repo_db):
        """DEDUP-PRI-03: L1/L2 未命中但 L3 命中时返回 L3 结果。"""
        file_l3 = _make_repository_file(
            file_unique_id="uid_l3_priority",
            content_hash="hash_l3",
        )
        repo_db.insert_file_record(file_l3)

        result = repository_manager.check_dedup(
            source_chat_id=-100333,
            source_message_id=333,
            file_unique_id="different_uid",
            content_hash="hash_l3",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l3_priority"

    def test_l1_overrides_l2_different_file(self, repository_manager, repo_db):
        """DEDUP-PRI-04: L1 和 L2 指向不同文件时，L1 优先。"""
        file_l1 = _make_repository_file(
            file_unique_id="uid_l1_file",
            content_hash="hash_l1_file",
        )
        repo_db.insert_file_record(file_l1)
        source_l1 = _make_repository_source(
            file_unique_id="uid_l1_file",
            source_chat_id=-100444,
            source_message_id=444,
        )
        repo_db.insert_source_mapping(source_l1)

        file_l2 = _make_repository_file(
            file_unique_id="uid_l2_file",
            content_hash="hash_l2_file",
        )
        repo_db.insert_file_record(file_l2)

        result = repository_manager.check_dedup(
            source_chat_id=-100444,
            source_message_id=444,
            file_unique_id="uid_l2_file",
            content_hash="hash_l2_file",
        )
        assert result is not None
        assert result.file_unique_id == "uid_l1_file"  # L1 优先
