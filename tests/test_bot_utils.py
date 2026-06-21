# coding=UTF-8
"""Bot 工具方法单元测试。

测试 module/bot_utils.py 中的工具类：
- MessageHelper: 消息安全发送/编辑
- TextFormatter: 文本格式化
- ValidationHelper: 输入验证
- LinkHelper: 链接解析

使用 mock 模拟 Pyrogram 客户端，不实际连接 Telegram。
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import pyrogram
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified
from pyrogram.errors import FloodWait

from module.bot.utils import (
    MessageHelper,
    TextFormatter,
    ValidationHelper,
    LinkHelper,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_client():
    """模拟 Pyrogram 客户端。"""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.edit_message_text = AsyncMock()
    client.name = "test_bot"
    return client


@pytest.fixture
def mock_message():
    """模拟 Pyrogram 消息对象。"""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.id = 100
    return message


# ==================== MessageHelper 测试 ====================


class TestMessageHelper:
    """MessageHelper 测试。"""

    @pytest.mark.asyncio
    async def test_safe_process_message_sends_new(self, mock_client, mock_message):
        """safe_process_message 应发送新消息（无 last_message_id 时）。"""
        result = await MessageHelper.safe_process_message(
            mock_client, mock_message, "hello world"
        )
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert kwargs["chat_id"] == 12345
        assert kwargs["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_safe_process_message_edits_existing(self, mock_client, mock_message):
        """safe_process_message 应编辑已有消息（有 last_message_id 时）。"""
        result = await MessageHelper.safe_process_message(
            mock_client, mock_message, ["hello"], last_message_id=50
        )
        mock_client.edit_message_text.assert_called_once()
        args, kwargs = mock_client.edit_message_text.call_args
        assert kwargs["chat_id"] == 12345
        assert kwargs["message_id"] == 50

    @pytest.mark.asyncio
    async def test_safe_process_message_multi_text(self, mock_client, mock_message):
        """safe_process_message 应支持多条文本发送。"""
        mock_client.send_message = AsyncMock(
            side_effect=[MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
        )
        texts = ["msg1", "msg2", "msg3"]
        await MessageHelper.safe_process_message(mock_client, mock_message, texts)
        assert mock_client.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_safe_edit_message_text_success(self, mock_client, mock_message):
        """safe_edit_message_text 应成功编辑文本。"""
        result = await MessageHelper.safe_edit_message_text(
            mock_client, mock_message, 50, "new text"
        )
        mock_client.edit_message_text.assert_called_once()
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_edit_message_text_not_modified(self, mock_client, mock_message):
        """safe_edit_message_text 应处理 MessageNotModified 异常。"""
        mock_client.edit_message_text.side_effect = MessageNotModified("Not modified")
        result = await MessageHelper.safe_edit_message_text(
            mock_client, mock_message, 50, "same text"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_edit_message_text_flood_wait(self, mock_client, mock_message):
        """safe_edit_message_text 应处理 FloodWait 后重试。"""
        # 第一次触发 FloodWait，第二次成功
        mock_client.edit_message_text.side_effect = [FloodWait(value=1), MagicMock()]
        with patch("asyncio.sleep", AsyncMock()):
            result = await MessageHelper.safe_edit_message_text(
                mock_client, mock_message, 50, "text after wait"
            )
        assert mock_client.edit_message_text.call_count == 2

    @pytest.mark.asyncio
    async def test_safe_edit_message_with_list(self, mock_client, mock_message):
        """safe_edit_message 支持列表文本时委托给 safe_process_message。"""
        mock_client.edit_message_text = AsyncMock()
        await MessageHelper.safe_edit_message(
            mock_client, mock_message, 50, ["single item"]
        )
        mock_client.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_edit_message_with_str(self, mock_client, mock_message):
        """safe_edit_message 支持字符串文本时委托给 safe_edit_message_text。"""
        mock_client.edit_message_text = AsyncMock()
        await MessageHelper.safe_edit_message(
            mock_client, mock_message, 50, "text string"
        )
        mock_client.edit_message_text.assert_called_once()


# ==================== TextFormatter 测试 ====================


class TestTextFormatter:
    """TextFormatter 测试。"""

    def test_update_text_with_right_only(self):
        """update_text 只有有效链接时。"""
        result = TextFormatter.update_text(
            right_link={"https://t.me/a/1", "https://t.me/a/2"}, invalid_link=set()
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert "https://t.me/a" in result[0]

    def test_update_text_with_invalid_only(self):
        """update_text 只有无效链接时。"""
        result = TextFormatter.update_text(right_link=set(), invalid_link={"bad_link"})
        assert isinstance(result, list)
        assert "bad_link" in result[0]

    def test_update_text_with_both(self):
        """update_text 同时有有效和无效链接时。"""
        result = TextFormatter.update_text(
            right_link={"https://t.me/a/1"}, invalid_link={"bad_link"}
        )
        assert isinstance(result, list)
        assert len(result) == 1

    def test_update_text_with_exist(self):
        """update_text 包含已存在链接时。"""
        result = TextFormatter.update_text(
            right_link={"https://t.me/a/1"},
            invalid_link=set(),
            exist_link={"https://t.me/a/2"},
        )
        assert isinstance(result, list)
        text = result[0]
        assert "https://t.me/a/1" in text

    def test_update_text_empty(self):
        """update_text 所有集合为空时。"""
        result = TextFormatter.update_text(right_link=set(), invalid_link=set())
        assert isinstance(result, list)
        # safe_message 对空字符串会添加换行符
        assert len(result) == 1


# ==================== ValidationHelper 测试 ====================


class TestValidationHelper:
    """ValidationHelper 测试。"""

    @pytest.mark.asyncio
    async def test_check_download_range_valid(self, mock_client, mock_message):
        """check_download_range 起始 <= 结束时应返回 True。"""
        mock_client.send_message = AsyncMock()
        result = await ValidationHelper.check_download_range(
            1, 100, mock_client, mock_message
        )
        assert result is True
        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_download_range_start_greater(self, mock_client, mock_message):
        """check_download_range 起始 > 结束时应返回 False。"""
        mock_client.send_message = AsyncMock()
        result = await ValidationHelper.check_download_range(
            100, 1, mock_client, mock_message
        )
        assert result is False
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_download_range_no_start(self, mock_client, mock_message):
        """check_download_range 没有指定起始 ID 时应返回 False。"""
        mock_client.send_message = AsyncMock()
        result = await ValidationHelper.check_download_range(
            -1, 100, mock_client, mock_message
        )
        assert result is False
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_download_range_no_end(self, mock_client, mock_message):
        """check_download_range 没有指定结束 ID 时应返回 False。"""
        mock_client.send_message = AsyncMock()
        result = await ValidationHelper.check_download_range(
            1, -1, mock_client, mock_message
        )
        assert result is False
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_download_range_neither(self, mock_client, mock_message):
        """check_download_range 没有指定任何 ID 时应返回 False。"""
        mock_client.send_message = AsyncMock()
        result = await ValidationHelper.check_download_range(
            -1, -1, mock_client, mock_message
        )
        assert result is False
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_download_range_with_end_minus_one(
        self, mock_client, mock_message
    ):
        """check_download_range end_id=-1 且 start_id 有效时。"""
        mock_client.send_message = AsyncMock()
        result = await ValidationHelper.check_download_range(
            5, -1, mock_client, mock_message
        )
        assert result is False
        mock_client.send_message.assert_called_once()


# ==================== LinkHelper 测试 ====================


class TestLinkHelper:
    """LinkHelper 测试。"""

    def test_parse_download_links_single(self):
        """parse_download_links 解析单条链接。"""
        result = LinkHelper.parse_download_links("/download https://t.me/a/123")
        assert result["is_range"] is False
        assert "https://t.me/a/123" in result["links"]

    def test_parse_download_links_multiple(self):
        """parse_download_links 解析多条链接。"""
        result = LinkHelper.parse_download_links(
            "/download https://t.me/a/1 https://t.me/a/2"
        )
        assert len(result["links"]) == 2
        assert "https://t.me/a/1" in result["links"]
        assert "https://t.me/a/2" in result["links"]

    def test_parse_download_links_range(self):
        """parse_download_links 解析范围下载（3个参数的链接）。"""
        result = LinkHelper.parse_download_links("/download https://t.me/a 1 100")
        assert result["is_range"] is True
        assert len(result["links"]) == 3

    def test_parse_download_links_range_invalid_v2(self):
        """parse_download_links 第二个参数也是链接时不是范围。"""
        result = LinkHelper.parse_download_links(
            "/download https://t.me/a https://t.me/b https://t.me/c"
        )
        assert result["is_range"] is False
        assert len(result["links"]) == 3

    def test_parse_download_links_strips_trailing_slash(self):
        """parse_download_links 应去除链接末尾的斜杠。"""
        result = LinkHelper.parse_download_links("/download https://t.me/a/123/")
        assert result["links"][0].endswith("/") is False

    def test_extract_range_links(self):
        """extract_range_links 应生成范围内的所有链接。"""
        result = LinkHelper.extract_range_links("https://t.me/a", 1, 3)
        assert len(result) == 3
        assert "https://t.me/a/1?single" in result
        assert "https://t.me/a/2?single" in result
        assert "https://t.me/a/3?single" in result

    def test_extract_range_links_single(self):
        """extract_range_links 起始结束相同时只生成一个链接。"""
        result = LinkHelper.extract_range_links("https://t.me/a", 5, 5)
        assert len(result) == 1
        assert "https://t.me/a/5?single" in result

    def test_extract_range_links_zero_based(self):
        """extract_range_links 从 0 开始。"""
        result = LinkHelper.extract_range_links("https://t.me/a", 0, 2)
        assert len(result) == 3
        assert "https://t.me/a/0?single" in result
        assert "https://t.me/a/2?single" in result
