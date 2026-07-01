# coding=UTF-8
"""Downloader 内容保护限制降级策略测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pyrogram.errors.exceptions.bad_request_400 import (
    ChatForwardsRestricted as ChatForwardsRestricted_400,
)


class AsyncIterator:
    """将列表包装为异步生成器。"""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class TestCheckType:
    """测试 check_type 方法。"""

    @pytest.fixture
    def downloader(self):
        """构造轻量级 Downloader 实例。"""
        with patch("module.downloader.Bot.__init__", return_value=None):
            with patch("module.downloader.Application"):
                with patch("asyncio.get_event_loop"):
                    from module.downloader import TelegramRestrictedMediaDownloader

                    dl = TelegramRestrictedMediaDownloader()
                    dl.app = MagicMock()
                    dl.app.config = {
                        "preference": {
                            "forward_type": {
                                "video": True,
                                "photo": True,
                                "audio": False,
                                "document": False,
                                "voice": False,
                                "text": True,
                                "animation": False,
                                "video_note": False,
                            }
                        }
                    }
                    return dl

    def test_check_type_video(self, downloader):
        """视频消息应通过类型检查。"""
        msg = MagicMock(video=MagicMock(), photo=None, text=None)
        assert downloader.check_type(msg) is True

    def test_check_type_text(self, downloader):
        """文本消息应通过类型检查（当 text 启用时）。"""
        msg = MagicMock(video=None, photo=None, text="hello")
        assert downloader.check_type(msg) is True

    def test_check_type_filtered(self, downloader):
        """被过滤的类型应返回 False。"""
        msg = MagicMock(video=None, photo=None, audio=MagicMock(), text=None)
        assert downloader.check_type(msg) is False

    def test_check_type_no_media_no_text(self, downloader):
        """无媒体无文本消息应返回 False。"""
        msg = MagicMock(
            video=None,
            photo=None,
            audio=None,
            document=None,
            voice=None,
            text=None,
            animation=None,
            video_note=None,
        )
        assert downloader.check_type(msg) is False


class TestContentProtectionFallback:
    """内容保护限制降级策略测试（批量转发循环）。"""

    @pytest.fixture
    def downloader(self):
        """构造带 Mock 依赖的 Downloader 实例。"""
        with patch("module.downloader.Bot.__init__", return_value=None):
            with patch("module.downloader.Application"):
                with patch("asyncio.get_event_loop"):
                    from module.downloader import TelegramRestrictedMediaDownloader

                    dl = TelegramRestrictedMediaDownloader()
                    dl._commands = MagicMock()
                    dl._commands.get_forward_link_from_bot = AsyncMock(
                        return_value={
                            "origin_link": "https://t.me/origin/1",
                            "target_link": "https://t.me/target/1",
                            "message_range": [1, 1],
                        }
                    )
                    dl.app = MagicMock()
                    dl.app.client = AsyncMock()
                    dl.app.config = {
                        "preference": {
                            "forward_type": {
                                "video": True,
                                "photo": True,
                                "text": True,
                            },
                            "upload": {"download_upload": True},
                        }
                    }
                    dl.check_type = MagicMock(return_value=True)
                    dl.cd = MagicMock()
                    dl.get_download_link_from_bot = AsyncMock()
                    dl.last_client = AsyncMock()
                    dl.last_message = MagicMock()
                    dl.forward = AsyncMock()
                    dl.done_notice = AsyncMock()
                    dl.repository_manager = None
                    return dl

    @pytest.mark.asyncio
    async def test_text_message_direct_forward_on_restrict(self, downloader):
        """文本消息在 ChatForwardsRestricted 时直接 send_message，不走下载后上传。"""
        text_msg = MagicMock(text="hello", media=None, id=100)

        # 直接替换为异步生成器函数
        async def _gen(*args, **kwargs):
            yield text_msg

        downloader.app.client.get_chat_history = _gen

        downloader.forward.side_effect = ChatForwardsRestricted_400

        client_mock = AsyncMock()
        client_mock.me = MagicMock(id=999)

        with patch(
            "module.downloader.parse_link",
            side_effect=[
                {"chat_id": -100111},
                {"chat_id": -100222},
            ],
        ):
            with patch(
                "module.downloader.get_chat_with_notify",
                side_effect=[
                    MagicMock(id=-100111, username="origin"),
                    MagicMock(id=-100222, username="target"),
                ],
            ):
                with patch("module.downloader.get_my_id", return_value=123):
                    await downloader.get_forward_link_from_bot(
                        client=client_mock,
                        message=MagicMock(
                            from_user=MagicMock(id=123),
                            text="/forward https://t.me/origin/1 https://t.me/target/1 1 1",
                            id=1,
                        ),
                    )

        # 验证 send_message 被调用（至少2次：加载消息 + 文本转发）
        assert client_mock.send_message.call_count >= 2
        # 找到目标 chat_id 的调用
        target_calls = [
            call
            for call in client_mock.send_message.call_args_list
            if call.kwargs.get("chat_id") == -100222
            and call.kwargs.get("text") == "hello"
        ]
        assert len(target_calls) == 1, "应有一次向目标频道发送文本消息的调用"

        # 验证没有走下载后上传
        downloader.get_download_link_from_bot.assert_not_called()

    @pytest.mark.asyncio
    async def test_media_message_uses_download_upload_on_restrict(self, downloader):
        """媒体消息在 ChatForwardsRestricted 时走 get_download_link_from_bot。"""
        media_msg = MagicMock(text=None, media=MagicMock(), id=200)

        async def _gen(*args, **kwargs):
            yield media_msg

        downloader.app.client.get_chat_history = _gen

        downloader.forward.side_effect = ChatForwardsRestricted_400
        downloader.check_type.return_value = True

        client_mock = AsyncMock()
        client_mock.me = MagicMock(id=999)

        with patch(
            "module.downloader.parse_link",
            side_effect=[
                {"chat_id": -100111},
                {"chat_id": -100222},
            ],
        ):
            with patch(
                "module.downloader.get_chat_with_notify",
                side_effect=[
                    MagicMock(id=-100111, username="origin"),
                    MagicMock(id=-100222, username="target"),
                ],
            ):
                with patch("module.downloader.get_my_id", return_value=123):
                    await downloader.get_forward_link_from_bot(
                        client=client_mock,
                        message=MagicMock(
                            from_user=MagicMock(id=123),
                            text="/forward https://t.me/origin/1 https://t.me/target/1 1 1",
                            id=1,
                        ),
                    )

        # 验证没有向目标频道直接 send_message（因为不是文本）
        target_calls = [
            call
            for call in client_mock.send_message.call_args_list
            if call.kwargs.get("chat_id") == -100222
        ]
        assert len(target_calls) == 0, "不应有直接发送到目标频道的调用"
        # 验证走了下载后上传
        downloader.get_download_link_from_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_filtered_type_skipped_even_on_restrict(self, downloader):
        """被 check_type 过滤的消息在 ChatForwardsRestricted 时跳过。"""
        filtered_msg = MagicMock(text=None, media=MagicMock(), id=300)

        async def _gen(*args, **kwargs):
            yield filtered_msg

        downloader.app.client.get_chat_history = _gen

        downloader.forward.side_effect = ChatForwardsRestricted_400
        downloader.check_type.return_value = False

        client_mock = AsyncMock()
        client_mock.me = MagicMock(id=999)

        with patch(
            "module.downloader.parse_link",
            side_effect=[
                {"chat_id": -100111},
                {"chat_id": -100222},
            ],
        ):
            with patch(
                "module.downloader.get_chat_with_notify",
                side_effect=[
                    MagicMock(id=-100111, username="origin"),
                    MagicMock(id=-100222, username="target"),
                ],
            ):
                with patch("module.downloader.get_my_id", return_value=123):
                    await downloader.get_forward_link_from_bot(
                        client=client_mock,
                        message=MagicMock(
                            from_user=MagicMock(id=123),
                            text="/forward https://t.me/origin/1 https://t.me/target/1 1 1",
                            id=1,
                        ),
                    )

        # 验证没有向目标频道直接 send_message
        target_calls = [
            call
            for call in client_mock.send_message.call_args_list
            if call.kwargs.get("chat_id") == -100222
        ]
        assert len(target_calls) == 0
        # 验证没有走下载后上传
        downloader.get_download_link_from_bot.assert_not_called()
