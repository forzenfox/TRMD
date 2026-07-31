# coding=UTF-8
"""Repository distribution integration tests for the forward() method.

Tests the integration of repository mode distribution into the forward()
method of TelegramRestrictedMediaDownloader. Covers:
- Distribution via copy_message (default)
- Fallback to file_id_send when copy_message fails
- Fallback to re-download when both fail
- Distribution record written to database
- Original forward behavior preserved when repository mode is disabled
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.core.repository.db import (
    RepositoryDB,
    RepositoryFile,
    RepositorySource,
)
from module.core.repository.manager import RepositoryManager


# ==================== Mock Pyrogram Objects ====================


@dataclass
class MockMedia:
    """Mock Pyrogram media object with file_unique_id."""

    file_unique_id: str = "uid_mock"
    file_id: str = "fid_mock"
    file_size: int = 2048


@dataclass
class MockChat:
    """Mock Pyrogram Chat object."""

    id: int = -1001234567890
    is_creator: bool = False
    is_admin: bool = False


@dataclass
class MockUser:
    """Mock Pyrogram User object."""

    id: int = 123456789


@dataclass
class MockMessage:
    """Mock Pyrogram Message object for forward() testing."""

    id: int = 1
    chat: MockChat = None
    from_user: MockUser = None
    video: MockMedia | None = None
    photo: None = None
    document: None = None
    audio: None = None
    animation: None = None
    voice: None = None
    video_note: None = None
    text: None = None
    link: str = "https://t.me/channel/1"

    def __post_init__(self):
        if self.chat is None:
            self.chat = MockChat()
        if self.from_user is None:
            self.from_user = MockUser()


# ==================== Fixtures ====================


@pytest.fixture
async def repo_db(tmp_path):
    """Provide RepositoryDB with temporary database."""
    from module.core import db as db_module

    db_path = str(tmp_path / "test_distribute.db")
    await db_module.init_db(db_path)
    db = RepositoryDB()
    yield db
    await db_module.close_db()


@pytest.fixture
def config_enabled():
    """Mock ConfigManager with repository enabled."""
    cm = MagicMock()
    cm.get_repository_config.return_value = {
        "enabled": True,
        "chat_id": "-1009999999999",
    }
    return cm


@pytest.fixture
def config_disabled():
    """Mock ConfigManager with repository disabled."""
    cm = MagicMock()
    cm.get_repository_config.return_value = {
        "enabled": False,
        "chat_id": "",
    }
    return cm


@pytest.fixture
async def repo_manager(repo_db, config_enabled):
    """Provide RepositoryManager with repository enabled."""
    return RepositoryManager(repository_db=repo_db, config_manager=config_enabled)


@pytest.fixture
async def repo_manager_disabled(repo_db, config_disabled):
    """Provide RepositoryManager with repository disabled."""
    return RepositoryManager(repository_db=repo_db, config_manager=config_disabled)


# ==================== Helpers ====================


def _make_video_message(
    msg_id: int = 1,
    chat_id: int = -1001234567890,
    file_unique_id: str = "uid_video_001",
) -> MockMessage:
    """Create a mock message with video media."""
    media = MockMedia(file_unique_id=file_unique_id, file_id=f"fid_{file_unique_id}")
    chat = MockChat(id=chat_id)
    return MockMessage(id=msg_id, chat=chat, video=media)


async def _seed_repository(
    repo_db: RepositoryDB,
    file_unique_id: str = "uid_video_001",
    source_chat_id: int = -1001234567890,
    source_message_id: int = 1,
) -> None:
    """Insert file record and source mapping into repository database."""
    file_record = RepositoryFile(
        id=None,
        file_unique_id=file_unique_id,
        file_id=f"fid_{file_unique_id}",
        content_hash=None,
        file_size=2048,
        file_type="video",
        mime_type="video/mp4",
        file_name="test.mp4",
        repository_chat_id=-1009999999999,
        repository_message_id=100,
        created_at=None,
        updated_at=None,
        status="active",
    )
    await repo_db.insert_file_record(file_record)
    source = RepositorySource(
        id=None,
        file_unique_id=file_unique_id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        created_at=None,
    )
    await repo_db.insert_source_mapping(source)


def _create_downloader(repo_manager_instance) -> object:
    """Create a minimal mocked downloader for forward() testing.

    Uses object.__new__ to bypass __init__ and manually sets only
    the attributes needed by the forward() method.
    """
    from module.core.download.downloader import TelegramRestrictedMediaDownloader

    dl = object.__new__(TelegramRestrictedMediaDownloader)
    dl.app = MagicMock()
    dl.app.client = AsyncMock()
    dl.gc = MagicMock()
    dl.gc.download_upload = True
    dl.gc.forward_type = {
        "video": True,
        "photo": True,
        "document": True,
        "audio": True,
        "voice": True,
        "animation": True,
        "text": True,
        "video_note": True,
    }
    dl.bot = AsyncMock()
    dl.last_client = AsyncMock()
    dl.last_message = MagicMock()
    dl.last_message.text = ""
    dl.repository_manager = repo_manager_instance
    dl.check_type = MagicMock(return_value=True)
    dl.done_notice = AsyncMock()
    dl.get_download_link_from_bot = AsyncMock()
    return dl


def _get_cfr_exception():
    """Get ChatForwardsRestricted exception class.

    Tries to import from pyrogram; falls back to a simple Exception
    subclass if pyrogram is not installed in the test environment.
    """
    try:
        from pyrogram.errors.exceptions.bad_request_400 import (
            ChatForwardsRestricted,
        )

        return ChatForwardsRestricted
    except ImportError:
        # Fallback for environments without pyrogram
        class ChatForwardsRestricted(Exception):
            pass

        return ChatForwardsRestricted


# ==================== Test: Distribution via copy_message ====================


class TestDistributeViaCopyMessage:
    """Distribution via copy_message (default method)."""

    @pytest.mark.asyncio
    async def test_forward_uses_repository_when_file_exists(
        self, repo_db, repo_manager
    ):
        """When file exists in repository, forward() should use distribute_to_target."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()

        # Make copy_message raise ChatForwardsRestricted
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # Mock distribute_to_target to succeed
        repo_manager.distribute_to_target = AsyncMock(return_value=200)

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        # Repository distribution was attempted
        repo_manager.distribute_to_target.assert_called_once()
        # Original download-upload was NOT called
        dl.get_download_link_from_bot.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_notifies_on_repository_success(self, repo_db, repo_manager):
        """forward() should call done_notice on successful repository distribution."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())
        repo_manager.distribute_to_target = AsyncMock(return_value=200)

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        dl.done_notice.assert_called_once()


# ==================== Test: Fallback to file_id_send ====================


class TestFallbackToFileIdSend:
    """Fallback to file_id_send when copy_message fails.

    From forward()'s perspective, distribute_to_target succeeds regardless
    of whether it used copy_message or file_id_send internally.
    """

    @pytest.mark.asyncio
    async def test_forward_succeeds_when_file_id_send_used(self, repo_db, repo_manager):
        """When copy_message fails but file_id_send works, forward() should succeed."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # distribute_to_target succeeds (internally uses file_id_send)
        repo_manager.distribute_to_target = AsyncMock(return_value=201)

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        repo_manager.distribute_to_target.assert_called_once()
        dl.get_download_link_from_bot.assert_not_called()


# ==================== Test: Fallback to re-download ====================


class TestFallbackToRedownload:
    """Fallback to re-download when repository distribution fails completely."""

    @pytest.mark.asyncio
    async def test_forward_falls_back_when_distribute_returns_none(
        self, repo_db, repo_manager
    ):
        """When distribute_to_target returns None, forward() should fall back."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())
        repo_manager.distribute_to_target = AsyncMock(return_value=None)

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_falls_back_when_file_not_in_repo(
        self, repo_db, repo_manager
    ):
        """When file is not in repository, forward() should fall back."""
        # Do NOT seed repository - file does not exist
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_falls_back_on_repo_exception(self, repo_db, repo_manager):
        """When repository mode throws, forward() should fall back."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())
        repo_manager.distribute_to_target = AsyncMock(
            side_effect=Exception("Repository error")
        )

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        dl.get_download_link_from_bot.assert_called_once()


# ==================== Test: Distribution record in database ====================


class TestDistributionRecordInDb:
    """Distribution record written to database after successful distribution."""

    @pytest.mark.asyncio
    async def test_distribute_called_with_correct_file_unique_id(
        self, repo_db, repo_manager
    ):
        """forward() should pass the correct file_unique_id to distribute_to_target."""
        await _seed_repository(repo_db, file_unique_id="uid_db_rec")
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())
        repo_manager.distribute_to_target = AsyncMock(return_value=300)

        message = _make_video_message(file_unique_id="uid_db_rec")
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        call_kwargs = repo_manager.distribute_to_target.call_args[1]
        assert call_kwargs["file_unique_id"] == "uid_db_rec"

    @pytest.mark.asyncio
    async def test_record_written_by_repository_manager(self, repo_db, repo_manager):
        """RepositoryManager._record_distribution should write to file_distributions."""
        await _seed_repository(repo_db, file_unique_id="uid_rec_write")

        await repo_manager._record_distribution(
            file_unique_id="uid_rec_write",
            target_chat_id=-1008888888888,
            target_message_id=300,
            method="copy_message",
        )

        from module.core.db import get_session
        from sqlmodel import select, text

        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT file_unique_id, target_chat_id, target_message_id, method "
                    "FROM file_distributions WHERE file_unique_id = :fuid"
                ),
                {"fuid": "uid_rec_write"},
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == "uid_rec_write"
        assert row[1] == -1008888888888
        assert row[2] == 300
        assert row[3] == "copy_message"


# ==================== Test: Original forward preserved ====================


class TestOriginalForwardPreserved:
    """Original forward behavior preserved when repository mode is disabled."""

    @pytest.mark.asyncio
    async def test_no_repo_calls_when_disabled(self, repo_db, repo_manager_disabled):
        """When repository mode is disabled, no repository methods should be called."""
        dl = _create_downloader(repo_manager_disabled)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # Spy on repository methods
        repo_manager_disabled.check_dedup = MagicMock()
        repo_manager_disabled.distribute_to_target = AsyncMock()

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        repo_manager_disabled.check_dedup.assert_not_called()
        repo_manager_disabled.distribute_to_target.assert_not_called()
        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_forward_works_when_disabled(
        self, repo_db, repo_manager_disabled
    ):
        """When repository mode is disabled, normal copy_message should work."""
        dl = _create_downloader(repo_manager_disabled)

        result_msg = MagicMock()
        result_msg.id = 500
        dl.app.client.copy_message = AsyncMock(return_value=result_msg)

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
        )

        dl.app.client.copy_message.assert_called_once()
        dl.done_notice.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_repo_when_manager_is_none(self, repo_db):
        """When repository_manager is None, original logic should be used."""
        dl = _create_downloader(None)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        dl.get_download_link_from_bot.assert_called_once()


# ==================== Test: Degradation when repository mode fails ====================


class TestDegradationWhenRepositoryFails:
    """Degradation when repository mode fails at various steps.

    Tests that the forward() method gracefully degrades to the original
    download-upload logic when repository mode encounters errors at
    different stages of the distribution pipeline.
    """

    @pytest.mark.asyncio
    async def test_check_dedup_exception_falls_back(self, repo_db, repo_manager):
        """When check_dedup raises an exception, forward() should fall back."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # Make check_dedup raise an exception (e.g., database error)
        repo_manager.check_dedup = MagicMock(
            side_effect=Exception("DB connection lost")
        )

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        # Should fall back to original download-upload logic
        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_media_file_unique_id_falls_back(self, repo_db, repo_manager):
        """When message has no media (file_unique_id is None), forward() should fall back.

        Without a file_unique_id, only Level 1 (source) dedup can match.
        If the source is also not in the repository, the system falls back.
        """
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # Create a message with no media attributes
        message = MockMessage(
            id=1,
            chat=MockChat(id=-1001234567890),
            video=None,
            photo=None,
            document=None,
            audio=None,
            animation=None,
            voice=None,
            video_note=None,
            text=None,
        )

        # Do NOT seed repository - no file record for this source
        repo_manager.distribute_to_target = AsyncMock(return_value=999)

        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        # File not in repo (no file_unique_id and no source match), falls back
        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_distribute_exception_falls_back(self, repo_db, repo_manager):
        """When distribute_to_target raises, forward() should fall back."""
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # check_dedup succeeds but distribute_to_target raises
        repo_manager.distribute_to_target = AsyncMock(
            side_effect=RuntimeError("Telegram API error")
        )

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_use_repository_false_skips_repo(
        self, repo_db, config_enabled
    ):
        """When should_use_repository returns False, repository block is skipped entirely."""
        # Configure: enabled but empty chat_id -> should_use_repository returns False
        config_enabled.get_repository_config.return_value = {
            "enabled": True,
            "chat_id": "",
        }
        repo_mgr = RepositoryManager(
            repository_db=repo_db, config_manager=config_enabled
        )
        await _seed_repository(repo_db)

        dl = _create_downloader(repo_mgr)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # Spy on repository methods
        repo_mgr.check_dedup = MagicMock()
        repo_mgr.distribute_to_target = AsyncMock()

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        repo_mgr.check_dedup.assert_not_called()
        repo_mgr.distribute_to_target.assert_not_called()
        dl.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_sequential_repo_failures_still_degrade(self, repo_db, repo_manager):
        """Multiple sequential repository failures should still degrade gracefully.

        Simulates: check_dedup finds file, distribute_to_target returns None
        (both copy_message and file_id_send failed internally), then falls
        back to original download-upload logic.
        """
        await _seed_repository(repo_db)
        dl = _create_downloader(repo_manager)
        CFR = _get_cfr_exception()
        dl.app.client.copy_message = AsyncMock(side_effect=CFR())

        # distribute_to_target returns None (all internal methods failed)
        repo_manager.distribute_to_target = AsyncMock(return_value=None)

        message = _make_video_message()
        await dl.forward(
            client=dl.last_client,
            message=message,
            message_id=1,
            origin_chat_id=-1001234567890,
            target_chat_id=-1008888888888,
            target_link="https://t.me/target",
            download_upload=True,
        )

        # Repository was attempted but failed, falls back
        repo_manager.distribute_to_target.assert_called_once()
        dl.get_download_link_from_bot.assert_called_once()
