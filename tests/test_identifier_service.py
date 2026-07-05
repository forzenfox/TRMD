# coding=UTF-8
"""IdentifierService 单元测试。

覆盖统一标识符解析服务的核心逻辑：格式检测、规范化、
client.get_chat 调用、ResolvedChat 组装以及异常映射。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from module.core.identifier_service import (
    IdentifierFormat,
    IdentifierService,
    ResolvedChat,
    InvalidIdentifierError,
    UserNotFoundError,
    AccessDeniedError,
    RateLimitedError,
    ResolveTimeoutError,
    ClientNotConnectedError,
)


class MockChat:
    """模拟 Pyrogram Chat 对象。"""

    def __init__(
        self,
        chat_id,
        type_value,
        title=None,
        first_name=None,
        last_name=None,
        username=None,
        is_bot=False,
    ):
        self.id = chat_id
        self.type = MagicMock(value=type_value)
        self.title = title
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.is_bot = is_bot


def make_service(mock_client=None):
    """构造带 mock client 的 IdentifierService。"""
    client = mock_client or MagicMock()
    return IdentifierService(client)


class TestDetectFormat:
    """格式检测测试。"""

    def test_numeric_id_positive(self):
        assert (
            IdentifierService._detect_format("8288406549")
            == IdentifierFormat.NUMERIC_ID
        )

    def test_numeric_id_negative(self):
        assert (
            IdentifierService._detect_format("-1001234567890")
            == IdentifierFormat.NUMERIC_ID
        )

    def test_at_username(self):
        assert (
            IdentifierService._detect_format("@seseYunBot")
            == IdentifierFormat.AT_USERNAME
        )

    def test_bare_username(self):
        assert (
            IdentifierService._detect_format("seseYunBot")
            == IdentifierFormat.BARE_USERNAME
        )

    def test_t_me_link_https(self):
        assert (
            IdentifierService._detect_format("https://t.me/seseYunBot")
            == IdentifierFormat.T_ME_LINK
        )

    def test_t_me_link_no_scheme(self):
        assert (
            IdentifierService._detect_format("t.me/seseYunBot")
            == IdentifierFormat.T_ME_LINK
        )

    def test_t_me_link_with_post_invalid(self):
        """带 post_id 的消息链接应视为 INVALID。"""
        assert (
            IdentifierService._detect_format("https://t.me/seseYunBot/123")
            == IdentifierFormat.INVALID
        )

    def test_invalid_special_chars(self):
        assert (
            IdentifierService._detect_format("not valid!!") == IdentifierFormat.INVALID
        )

    def test_empty(self):
        assert IdentifierService._detect_format("") == IdentifierFormat.INVALID

    def test_whitespace_only(self):
        assert IdentifierService._detect_format("   ") == IdentifierFormat.INVALID


class TestNormalize:
    """规范化测试。"""

    def test_normalize_numeric_id(self):
        assert (
            IdentifierService._normalize("8288406549", IdentifierFormat.NUMERIC_ID)
            == 8288406549
        )

    def test_normalize_numeric_id_negative(self):
        assert (
            IdentifierService._normalize("-1001234567890", IdentifierFormat.NUMERIC_ID)
            == -1001234567890
        )

    def test_normalize_at_username(self):
        assert (
            IdentifierService._normalize("@seseYunBot", IdentifierFormat.AT_USERNAME)
            == "seseYunBot"
        )

    def test_normalize_bare_username(self):
        assert (
            IdentifierService._normalize("seseYunBot", IdentifierFormat.BARE_USERNAME)
            == "seseYunBot"
        )

    def test_normalize_t_me_link(self):
        assert (
            IdentifierService._normalize(
                "https://t.me/seseYunBot", IdentifierFormat.T_ME_LINK
            )
            == "seseYunBot"
        )

    def test_normalize_t_me_link_no_scheme(self):
        assert (
            IdentifierService._normalize("t.me/seseYunBot", IdentifierFormat.T_ME_LINK)
            == "seseYunBot"
        )

    def test_normalize_t_me_link_invite(self):
        assert (
            IdentifierService._normalize(
                "https://t.me/+AbCdEfGhIjKlMnOp", IdentifierFormat.T_ME_LINK
            )
            == "https://t.me/+AbCdEfGhIjKlMnOp"
        )

    def test_normalize_t_me_link_none_group_id(self):
        """extract_info_from_link 返回空 Link 时应抛出 InvalidIdentifierError。"""
        from unittest.mock import patch

        with patch(
            "module.core.identifier_service.extract_info_from_link",
            return_value=MagicMock(group_id=None),
        ):
            with pytest.raises(InvalidIdentifierError):
                IdentifierService._normalize(
                    "https://t.me/somepath", IdentifierFormat.T_ME_LINK
                )

    def test_normalize_unsupported_format(self):
        """_normalize 遇到未处理的 IdentifierFormat 应抛出 InvalidIdentifierError。"""
        with pytest.raises(InvalidIdentifierError):
            IdentifierService._normalize("x", IdentifierFormat.INVALID)


class TestResolveSuccess:
    """解析成功场景测试。"""

    @pytest.mark.asyncio
    async def test_resolve_numeric_id(self):
        chat = MockChat(
            8288406549, "private", first_name="Bot", username="seseYunBot", is_bot=True
        )
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("8288406549")

        assert result == ResolvedChat(
            chat_id=8288406549,
            chat_type="bot",
            chat_name="Bot",
            username="seseYunBot",
            message_count=-1,
            media_count=-1,
            has_access=True,
            is_private=True,
        )
        client.get_chat.assert_awaited_once_with(8288406549)

    @pytest.mark.asyncio
    async def test_resolve_at_username(self):
        chat = MockChat(
            123456, "private", first_name="Alice", last_name="Smith", username="alice"
        )
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("@alice")

        assert result == ResolvedChat(
            chat_id=123456,
            chat_type="private",
            chat_name="Alice Smith",
            username="alice",
            message_count=-1,
            media_count=-1,
            has_access=True,
            is_private=True,
        )
        client.get_chat.assert_awaited_once_with("alice")

    @pytest.mark.asyncio
    async def test_resolve_bare_username(self):
        chat = MockChat(
            -1001234567890, "channel", title="My Channel", username="mychannel"
        )
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("mychannel")

        assert result == ResolvedChat(
            chat_id=-1001234567890,
            chat_type="channel",
            chat_name="My Channel",
            username="mychannel",
            message_count=-1,
            media_count=-1,
            has_access=True,
            is_private=False,
        )
        client.get_chat.assert_awaited_once_with("mychannel")

    @pytest.mark.asyncio
    async def test_resolve_t_me_link(self):
        chat = MockChat(789, "supergroup", title="Dev Group", username="devgroup")
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("https://t.me/devgroup")

        assert result == ResolvedChat(
            chat_id=789,
            chat_type="supergroup",
            chat_name="Dev Group",
            username="devgroup",
            message_count=-1,
            media_count=-1,
            has_access=True,
            is_private=False,
        )
        client.get_chat.assert_awaited_once_with("devgroup")

    @pytest.mark.asyncio
    async def test_resolve_group(self):
        chat = MockChat(-987, "group", title="Family Group")
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("-987")

        assert result.chat_type == "group"
        assert result.is_private is False

    @pytest.mark.asyncio
    async def test_chat_name_fallback_to_username(self):
        chat = MockChat(111, "private", username="bobby_bot")
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("bobby_bot")

        assert result.chat_name == "bobby_bot"

    @pytest.mark.asyncio
    async def test_chat_name_fallback_to_chat_id(self):
        chat = MockChat(222, "private")
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=chat)
        service = make_service(client)

        result = await service.resolve("222")

        assert result.chat_name == "chat_222"


class TestResolveErrors:
    """解析异常映射测试。"""

    @pytest.mark.asyncio
    async def test_invalid_identifier(self):
        service = make_service()
        with pytest.raises(InvalidIdentifierError):
            await service.resolve("not valid!!")

    @pytest.mark.asyncio
    async def test_user_not_found_username_not_occupied(self):
        from pyrogram.errors.exceptions.bad_request_400 import UsernameNotOccupied

        client = MagicMock()
        client.get_chat = AsyncMock(side_effect=UsernameNotOccupied())
        service = make_service(client)

        with pytest.raises(UserNotFoundError) as exc_info:
            await service.resolve("@missing")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_user_not_found_peer_id_invalid(self):
        from pyrogram.errors.exceptions.bad_request_400 import PeerIdInvalid

        client = MagicMock()
        client.get_chat = AsyncMock(side_effect=PeerIdInvalid())
        service = make_service(client)

        with pytest.raises(UserNotFoundError):
            await service.resolve("12345")

    @pytest.mark.asyncio
    async def test_access_denied_chat_forbidden(self):
        from pyrogram.errors.exceptions.forbidden_403 import ChatForbidden

        client = MagicMock()
        client.get_chat = AsyncMock(side_effect=ChatForbidden())
        service = make_service(client)

        with pytest.raises(AccessDeniedError) as exc_info:
            await service.resolve("@private")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_limited(self):
        from pyrogram.errors.exceptions.flood_420 import FloodWait

        client = MagicMock()
        client.get_chat = AsyncMock(side_effect=FloodWait(30))
        service = make_service(client)

        with pytest.raises(RateLimitedError) as exc_info:
            await service.resolve("@busy_bot")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_resolve_timeout(self):
        import asyncio

        async def raise_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        client = MagicMock()
        client.get_chat = raise_timeout
        service = make_service(client)

        with pytest.raises(ResolveTimeoutError) as exc_info:
            await service.resolve("@slow_bot")
        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_unexpected_error_500(self):
        client = MagicMock()
        client.get_chat = AsyncMock(side_effect=RuntimeError("boom"))
        service = make_service(client)

        with pytest.raises(Exception) as exc_info:
            await service.resolve("@whatever")
        # 兜底异常保持 IdentifierServiceError 基类行为
        assert hasattr(exc_info.value, "status_code")
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_client_not_connected(self):
        """client 为 None 时应抛出 503 ClientNotConnectedError。"""
        service = IdentifierService(client=None)

        with pytest.raises(ClientNotConnectedError) as exc_info:
            await service.resolve("@anyone")
        assert exc_info.value.status_code == 503


class TestResolvedChatEquality:
    """ResolvedChat 作为 frozen dataclass 的行为测试。"""

    def test_frozen_and_hashable(self):
        a = ResolvedChat(1, "private", "A", "a", -1, -1, True, True)
        b = ResolvedChat(1, "private", "A", "a", -1, -1, True, True)
        assert a == b
        assert hash(a) == hash(b)
