# coding=UTF-8
"""Downloader 内容保护限制降级策略测试。"""

import os

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


class TestDownloadRangeDtype:
    """测试 download_range 对媒体类型的识别与临时文件名生成。"""

    @pytest.fixture
    def downloader(self):
        """构造带真实 get_temp_file_path 的 Downloader 实例。"""
        with patch("module.downloader.Bot.__init__", return_value=None):
            with patch("module.downloader.Application"):
                with patch("asyncio.get_event_loop"):
                    from module.app import Application
                    from module.downloader import TelegramRestrictedMediaDownloader

                    dl = TelegramRestrictedMediaDownloader()
                    real_app = Application.__new__(Application)
                    real_app.temp_directory = os.path.join(
                        os.getcwd(), "tests", "tmp", "trmd"
                    )
                    dl.app = real_app
                    dl.resume_download = AsyncMock(return_value="/mock/final_path")
                    return dl

    def _make_message(self, dtype: str, msg_id: int = 96396):
        """构造一个指定媒体类型的 Pyrogram Message Mock。"""
        media_obj = MagicMock(
            file_id="valid_file_id_for_test",
            mime_type=f"{dtype}/mp4" if dtype == "video" else f"{dtype}/jpg",
            file_size=1024,
        )
        msg = MagicMock(
            id=msg_id,
            chat=MagicMock(id=-100123, full_name="test_chat"),
            media=MagicMock(name=dtype.upper()),
        )
        # 清空所有媒体属性，仅保留目标类型
        for attr in (
            "video",
            "photo",
            "document",
            "audio",
            "voice",
            "animation",
            "video_note",
        ):
            setattr(msg, attr, None)
        setattr(msg, dtype, media_obj)
        return msg

    @pytest.mark.asyncio
    async def test_video_message_uses_lowercase_dtype(self, downloader):
        """视频消息应被识别为小写 video，临时文件名不应为 .unknown。"""
        msg = self._make_message("video")
        downloader.app.client = AsyncMock()
        downloader.app.client.get_messages = AsyncMock(return_value=msg)
        downloader.env_save_directory = MagicMock(
            return_value=os.path.join(os.getcwd(), "tests", "tmp", "downloads")
        )

        with patch("module.app.get_extension", return_value="mp4"):
            with patch("module.downloader.is_file_duplicate", return_value=False):
                await downloader.download_range(
                    chat_id=-100123,
                    start_id=96396,
                    end_id=96396,
                    task_id="task_1",
                )

        call = downloader.resume_download.call_args
        file_name = call.kwargs["file_name"]
        assert not file_name.endswith(".unknown"), (
            f"视频消息生成的文件名不应以 .unknown 结尾: {file_name}"
        )
        assert file_name.endswith(".mp4"), (
            f"视频消息生成的文件名应使用 .mp4: {file_name}"
        )

    @pytest.mark.asyncio
    async def test_photo_message_uses_lowercase_dtype(self, downloader):
        """图片消息应被识别为小写 photo，临时文件名不应为 .unknown。"""
        msg = self._make_message("photo")
        downloader.app.client = AsyncMock()
        downloader.app.client.get_messages = AsyncMock(return_value=msg)
        downloader.env_save_directory = MagicMock(
            return_value=os.path.join(os.getcwd(), "tests", "tmp", "downloads")
        )

        with patch("module.app.get_extension", return_value="jpg"):
            with patch("module.downloader.is_file_duplicate", return_value=False):
                await downloader.download_range(
                    chat_id=-100123,
                    start_id=96396,
                    end_id=96396,
                    task_id="task_1",
                )

        call = downloader.resume_download.call_args
        file_name = call.kwargs["file_name"]
        assert not file_name.endswith(".unknown"), (
            f"图片消息生成的文件名不应以 .unknown 结尾: {file_name}"
        )
        assert file_name.endswith(".jpg"), (
            f"图片消息生成的文件名应使用 .jpg: {file_name}"
        )

    @pytest.mark.asyncio
    async def test_unrenamed_temp_file_reported_as_failed(self, downloader):
        """当 resume_download 未重命名 .temp 文件时，子任务应报告失败。"""
        msg = self._make_message("video")
        downloader.app.client = AsyncMock()
        downloader.app.client.get_messages = AsyncMock(return_value=msg)
        downloader.env_save_directory = MagicMock(
            return_value=os.path.join(os.getcwd(), "tests", "tmp", "downloads")
        )
        progress_callback = AsyncMock()

        # 模拟 resume_download 返回目标路径，但目标文件不存在而 .temp 存在
        target_path = os.path.join(
            os.getcwd(), "tests", "tmp", "downloads", "96396 - None.mp4"
        )
        downloader.resume_download = AsyncMock(return_value=target_path)

        def _fake_exists(path):
            return str(path).endswith(".temp")

        with patch("module.app.get_extension", return_value="mp4"):
            with patch("module.downloader.is_file_duplicate", return_value=False):
                with patch("os.path.exists", side_effect=_fake_exists):
                    await downloader.download_range(
                        chat_id=-100123,
                        start_id=96396,
                        end_id=96396,
                        task_id="task_1",
                        progress_callback=progress_callback,
                    )

        # 验证进度回调报告了 FAILED 而不是 SUCCESS
        failed_calls = [
            call
            for call in progress_callback.call_args_list
            if call.args[2].value == "failed"
        ]
        assert len(failed_calls) == 1, "未重命名的临时文件应报告失败"
        assert "临时文件未重命名" in failed_calls[0].args[3]


class TestResumeDownloadProgress:
    """测试 resume_download 在无 progress 回调时的行为。"""

    @pytest.fixture
    def downloader(self):
        """构造最小化的 Downloader 实例。"""
        with patch("module.downloader.Bot.__init__", return_value=None):
            with patch("module.downloader.Application"):
                with patch("asyncio.get_event_loop"):
                    from module.downloader import TelegramRestrictedMediaDownloader

                    dl = TelegramRestrictedMediaDownloader()
                    dl.app = MagicMock()
                    return dl

    @pytest.mark.asyncio
    async def test_resume_download_without_progress_callback(
        self, downloader, tmp_path
    ):
        """不传入 progress 回调时，resume_download 应正常完成重命名。"""
        target_file = str(tmp_path / "test.jpg")
        target_size = 4

        async def _stream(*args, **kwargs):
            yield b"1234"

        downloader.app.client.stream_media = _stream

        with patch("module.downloader.safe_replace") as mock_safe_replace:
            mock_safe_replace.return_value = {"e_code": None}
            result = await downloader.resume_download(
                message=MagicMock(),
                file_name=target_file,
                compare_size=target_size,
            )
            assert result == target_file
            mock_safe_replace.assert_called_once()
