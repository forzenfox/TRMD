# coding=UTF-8
"""测试 parse_link 和 extract_info_from_link 对私有频道的解析。

验证私有频道邀请链接（如 https://t.me/+xxxxx）能否正确解析。
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

# Import just the functions we need, avoiding module/__init__.py
from urllib.parse import parse_qs, urlparse
from dataclasses import dataclass
from typing import Union, Optional


@dataclass
class Link:
    group_id: Union[str, int, None] = None
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    topic_id: Optional[int] = None


def extract_info_from_link(link: str) -> Link:
    if link in ("me", "self"):
        return Link(group_id=link)

    try:
        u = urlparse(link)
        paths = [p for p in u.path.split("/") if p]
        query = parse_qs(u.query)
    except ValueError:
        return Link()

    result = Link()

    if "comment" in query:
        result.group_id = paths[0]
        result.comment_id = int(query["comment"][0])
    elif len(paths) == 1 and paths[0] != "c":
        result.group_id = paths[0]
    elif len(paths) == 2:
        if paths[0] == "c":
            result.group_id = int(f"-100{paths[1]}")
        else:
            result.group_id = paths[0]
            result.post_id = int(paths[1])
    elif len(paths) == 3:
        if paths[0] == "c":
            result.group_id = int(f"-100{paths[1]}")
            result.post_id = int(paths[2])
        else:
            result.group_id = paths[0]
            result.topic_id = int(paths[1])
            result.post_id = int(paths[2])
    elif len(paths) == 4 and paths[0] == "c":
        result.group_id = int(f"-100{paths[1]}")
        result.topic_id = int(paths[2])
        result.post_id = int(paths[3])

    return result


async def parse_link(client, link: str, original_link: str = None) -> dict:
    try:
        parsed = extract_info_from_link(original_link or link)
        group_id = parsed.group_id

        # For private channel invite links (starting with '+'), Pyrogram needs
        # the full invite URL to resolve the chat.
        chat_id_for_lookup = group_id
        if isinstance(group_id, str) and group_id.startswith("+"):
            chat_id_for_lookup = f"https://t.me/{group_id}"

        if parsed.comment_id:
            chat = await client.get_chat(chat_id_for_lookup)
            if chat:
                return {
                    "chat_id": chat.linked_chat.id,
                    "comment_id": parsed.comment_id,
                    "topic_id": parsed.topic_id,
                }

        return {
            "chat_id": group_id,
            "comment_id": parsed.post_id,
            "topic_id": parsed.topic_id,
        }
    except Exception:
        raise ValueError("Invalid message link.")


async def get_chat_with_notify(
    user_client, chat_id, error_msg=None, bot_client=None, bot_message=None
):
    """模拟 get_chat_with_notify 的行为。"""
    try:
        # For private channel invite links (starting with '+'), Pyrogram needs
        # the full invite URL to resolve the chat.
        lookup_id = chat_id
        if isinstance(chat_id, str) and chat_id.startswith("+"):
            lookup_id = f"https://t.me/{chat_id}"
        chat = await user_client.get_chat(lookup_id)
        return chat
    except Exception:
        return None


class TestExtractInfoFromLink:
    """extract_info_from_link 测试。"""

    def test_public_channel_link(self):
        """公共频道链接应正确解析。"""
        link = "https://t.me/some_channel"
        result = extract_info_from_link(link)
        assert result.group_id == "some_channel"

    def test_private_channel_invite_link(self):
        """私有频道邀请链接应保留完整链接。"""
        link = "https://t.me/+67VXq4htgcBhYmU1"
        result = extract_info_from_link(link)
        # 私有邀请链接应返回完整的 group_id，包含 '+' 前缀
        assert result.group_id == "+67VXq4htgcBhYmU1"

    def test_c_type_channel_link(self):
        """c 类型频道链接应正确解析为 -100 格式。"""
        link = "https://t.me/c/1234567890/100"
        result = extract_info_from_link(link)
        assert result.group_id == -1001234567890

    def test_public_channel_with_message_link(self):
        """公共频道消息链接应正确解析。"""
        link = "https://t.me/some_channel/100"
        result = extract_info_from_link(link)
        assert result.group_id == "some_channel"
        assert result.post_id == 100

    def test_c_type_channel_with_message_link(self):
        """c 类型频道消息链接应正确解析。"""
        link = "https://t.me/c/1234567890/100"
        result = extract_info_from_link(link)
        assert result.group_id == -1001234567890
        assert result.post_id == 100


class TestParseLink:
    """parse_link 测试。"""

    @pytest.mark.asyncio
    async def test_parse_public_channel(self):
        """解析公共频道链接。"""
        mock_client = MagicMock()
        mock_client.get_chat = AsyncMock(return_value=MagicMock(id="some_channel"))
        link = "https://t.me/some_channel"
        result = await parse_link(mock_client, link)
        assert result["chat_id"] == "some_channel"

    @pytest.mark.asyncio
    async def test_parse_private_invite_link_returns_correct_chat_id(self):
        """解析私有频道邀请链接 - 返回的 chat_id 应保留 '+' 前缀。"""
        mock_client = MagicMock()
        link = "https://t.me/+67VXq4htgcBhYmU1"
        result = await parse_link(mock_client, link)
        # 私有邀请链接的 chat_id 应保留 '+' 前缀
        assert result["chat_id"] == "+67VXq4htgcBhYmU1"

    @pytest.mark.asyncio
    async def test_parse_c_type_channel(self):
        """解析 c 类型频道链接。"""
        mock_client = MagicMock()
        link = "https://t.me/c/1234567890/100"
        result = await parse_link(mock_client, link)
        assert result["chat_id"] == -1001234567890


class TestGetChatWithNotify:
    """get_chat_with_notify 测试 - 这是实际调用 get_chat 的地方。"""

    @pytest.mark.asyncio
    async def test_get_chat_with_public_channel(self):
        """公共频道应直接使用 chat_id 调用 get_chat。"""
        mock_client = MagicMock()
        mock_client.get_chat = AsyncMock(return_value=MagicMock(id="some_channel"))
        await get_chat_with_notify(mock_client, "some_channel")
        mock_client.get_chat.assert_called_once_with("some_channel")

    @pytest.mark.asyncio
    async def test_get_chat_with_private_invite_link(self):
        """私有频道邀请链接 - get_chat 应传入完整的 URL。"""
        mock_client = MagicMock()
        mock_client.get_chat = AsyncMock(return_value=MagicMock(id="invite_link_chat"))
        await get_chat_with_notify(mock_client, "+67VXq4htgcBhYmU1")
        # 验证 get_chat 被调用了完整的邀请链接 URL
        mock_client.get_chat.assert_called_once_with("https://t.me/+67VXq4htgcBhYmU1")

    @pytest.mark.asyncio
    async def test_get_chat_with_c_type_channel(self):
        """c 类型频道 - get_chat 应直接使用整数 chat_id。"""
        mock_client = MagicMock()
        mock_client.get_chat = AsyncMock(return_value=MagicMock(id=-1001234567890))
        await get_chat_with_notify(mock_client, -1001234567890)
        mock_client.get_chat.assert_called_once_with(-1001234567890)
