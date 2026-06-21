# coding=UTF-8
"""键盘管理单元测试。

测试 module/keyboard_manager.py 中的类：
- KeyboardManager: 静态键盘构建方法
- KeyboardButtonHandler: 键盘按钮交互处理

使用 mock 模拟 Pyrogram 客户端和回调查询。
"""

from unittest.mock import MagicMock, AsyncMock

import pytest
from pyrogram.types.bots_and_keyboards import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified

from module.bot.keyboard_manager import KeyboardManager, KeyboardButtonHandler
from module.enums import CalenderKeyboard, DownloadType, BotCallbackText, BotButton


# ==================== KeyboardManager 测试 ====================


class TestKeyboardManagerBuild:
    """KeyboardManager 静态构建方法测试。"""

    def test_build_help_keyboard(self):
        """build_help_keyboard 应返回 InlineKeyboardMarkup。"""
        keyboard = KeyboardManager.build_help_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert keyboard.inline_keyboard is not None
        # 应有 GitHub, 订阅频道, 视频教程 至少三行
        assert len(keyboard.inline_keyboard) >= 3

    def test_build_table_keyboard(self):
        """build_table_keyboard 应返回 InlineKeyboardMarkup。"""
        keyboard = KeyboardManager.build_table_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 应有链接表、计数表、上传表三行 + 返回帮助页一行
        assert len(keyboard.inline_keyboard) >= 3

    def test_build_setting_keyboard(self):
        """build_setting_keyboard 应返回包含各设置的键盘。"""
        global_config = {
            BotCallbackText.NOTICE: True,
            "upload": {"download_upload": False, "delete": False},
        }
        user_config = {"is_shutdown": False}
        keyboard = KeyboardManager.build_setting_keyboard(global_config, user_config)
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 应包含通知、导出表格、退出关机、转发设置等
        found_notice = any(
            BotButton.CLOSE_NOTICE in btn.text or BotButton.OPEN_NOTICE in btn.text
            for row in keyboard.inline_keyboard
            for btn in row
        )
        assert found_notice

    def test_build_upload_setting_keyboard(self):
        """build_upload_setting_keyboard 应返回上传设置键盘。"""
        global_config = {"upload": {"download_upload": True, "delete": False}}
        keyboard = KeyboardManager.build_upload_setting_keyboard(global_config)
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 2

    def test_build_download_setting_keyboard(self):
        """build_download_setting_keyboard 应返回下载类型设置键盘。"""
        download_type = [DownloadType.VIDEO, DownloadType.PHOTO]
        keyboard = KeyboardManager.build_download_setting_keyboard(download_type)
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 视频应为 ON 状态
        first_row = keyboard.inline_keyboard[0]
        video_btn = first_row[0]
        assert BotButton.VIDEO_ON in video_btn.text

    def test_build_forward_setting_keyboard(self):
        """build_forward_setting_keyboard 应返回转发类型设置键盘。"""
        forward_type = {"video": True, "photo": False, "audio": True, "voice": False}
        keyboard = KeyboardManager.build_forward_setting_keyboard(forward_type)
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 视频应为 ON，图片应为 OFF
        first_row = keyboard.inline_keyboard[0]
        assert BotButton.VIDEO_ON in first_row[0].text
        assert BotButton.PHOTO_OFF in first_row[1].text

    def test_build_export_table_keyboard(self):
        """build_export_table_keyboard 应返回导出表格键盘。"""
        keyboard = KeyboardManager.build_export_table_keyboard("export_link")
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 应包含导出表格、重新选择、帮助页
        assert len(keyboard.inline_keyboard) >= 2

    def test_build_export_table_toggle_keyboard(self):
        """build_export_table_toggle_keyboard 应返回开关键盘。"""
        config = {"export_table": {"link": True, "count": False, "upload": True}}
        keyboard = KeyboardManager.build_export_table_toggle_keyboard(config)
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 2

    def test_build_download_chat_filter_keyboard(self):
        """build_download_chat_filter_keyboard 应返回下载频道过滤键盘。"""
        keyboard = KeyboardManager.build_download_chat_filter_keyboard(
            include_comment=False
        )
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 3 行：日期/类型过滤，关键词/评论区，执行/取消
        assert len(keyboard.inline_keyboard) == 3

    def test_build_download_chat_dtype_filter_keyboard(self):
        """build_download_chat_dtype_filter_keyboard 应返回类型过滤键盘。"""
        f = {
            "channel_123": {
                "download_type": {
                    DownloadType.VIDEO: True,
                    DownloadType.PHOTO: False,
                    DownloadType.AUDIO: True,
                    DownloadType.VOICE: False,
                    DownloadType.ANIMATION: True,
                    DownloadType.DOCUMENT: False,
                    DownloadType.VIDEO_NOTE: True,
                }
            }
        }
        keyboard = KeyboardManager.build_download_chat_dtype_filter_keyboard(
            f, "channel_123"
        )
        assert isinstance(keyboard, InlineKeyboardMarkup)
        first_row = keyboard.inline_keyboard[0]
        assert BotButton.VIDEO_ON in first_row[0].text
        assert BotButton.PHOTO_OFF in first_row[1].text

    def test_build_date_range_keyboard(self):
        """build_date_range_keyboard 应返回日期范围键盘。"""
        keyboard = KeyboardManager.build_date_range_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 2

    def test_build_restrict_forward_keyboard(self):
        """build_restrict_forward_keyboard 应返回受限转发键盘。"""
        keyboard = KeyboardManager.build_restrict_forward_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 1

    def test_build_single_button_keyboard(self):
        """build_single_button_keyboard 应返回单按钮键盘。"""
        keyboard = KeyboardManager.build_single_button_keyboard("Test", "test_data")
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard[0]) == 1
        assert keyboard.inline_keyboard[0][0].text == "Test"

    def test_build_back_table_keyboard(self):
        """build_back_table_keyboard 应返回返回表格键盘。"""
        keyboard = KeyboardManager.build_back_table_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 1

    def test_build_task_assign_keyboard(self):
        """build_task_assign_keyboard 应返回任务分配键盘。"""
        keyboard = KeyboardManager.build_task_assign_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 1

    def test_build_keyword_filter_keyboard_with_keywords(self):
        """build_keyword_filter_keyboard 有关键词时应显示确认/取消按钮。"""
        keyboard = KeyboardManager.build_keyword_filter_keyboard(["kw1", "kw2"])
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # 应包含确认和取消按钮
        found_cancel = any(
            BotButton.CANCEL in btn.text
            for row in keyboard.inline_keyboard
            for btn in row
        )
        assert found_cancel

    def test_build_keyword_filter_keyboard_no_keywords(self):
        """build_keyword_filter_keyboard 无关键词时应显示返回按钮。"""
        keyboard = KeyboardManager.build_keyword_filter_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_build_calendar_keyboard_start(self):
        """build_calendar_keyboard 起始日期应包含导航和日期。"""
        rows = KeyboardManager.build_calendar_keyboard(
            CalenderKeyboard.START_TIME_BUTTON, 2026, 6
        )
        assert len(rows) >= 4  # 导航行 + 星期行 + 至少4周日历 + 确认行

    def test_build_calendar_keyboard_end(self):
        """build_calendar_keyboard 结束日期应包含导航和日期。"""
        rows = KeyboardManager.build_calendar_keyboard(
            CalenderKeyboard.END_TIME_BUTTON, 2026, 6
        )
        assert len(rows) >= 4

    def test_build_time_keyboard(self):
        """build_time_keyboard 应返回时间选择键盘。"""
        keyboard = KeyboardManager.build_time_keyboard(
            CalenderKeyboard.START_TIME_BUTTON, "2026-06-01 00:00:00", 1
        )
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) >= 5

    def test_build_time_keyboard_with_string_dtype(self):
        """build_time_keyboard 支持字符串 dtype。"""
        keyboard = KeyboardManager.build_time_keyboard(
            "start", "2026-06-01 12:00:00", 2
        )
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert "步进值:2" in keyboard.inline_keyboard[0][0].text


# ==================== KeyboardButtonHandler 测试 ====================


class TestKeyboardButtonHandler:
    """KeyboardButtonHandler 交互处理测试。"""

    @pytest.fixture
    def mock_callback_query(self):
        cq = MagicMock()
        cq.message = MagicMock()
        cq.message.edit_reply_markup = AsyncMock()
        cq.message.reply_text = AsyncMock()
        cq.message.edit_text = AsyncMock()
        return cq

    @pytest.mark.asyncio
    async def test_handle_choice_export_table(self, mock_callback_query):
        """handle_choice_export_table 应更新键盘为导出表格键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_choice_export_table(BotCallbackText.EXPORT_LINK_TABLE)
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_setting(self, mock_callback_query):
        """handle_toggle_setting 应更新键盘为设置键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        global_config = {BotCallbackText.NOTICE: True, "upload": {}}
        user_config = {"is_shutdown": False}
        await handler.handle_toggle_setting(global_config, user_config)
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_upload_setting(self, mock_callback_query):
        """handle_toggle_upload_setting 应更新键盘为上传播放设置键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        global_config = {"upload": {"download_upload": True, "delete": False}}
        await handler.handle_toggle_upload_setting(global_config)
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_download_setting(self, mock_callback_query):
        """handle_toggle_download_setting 应更新键盘为下载设置键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_toggle_download_setting(
            [DownloadType.VIDEO, DownloadType.PHOTO]
        )
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_forward_setting(self, mock_callback_query):
        """handle_toggle_forward_setting 应更新键盘为转发设置键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_toggle_forward_setting({"video": True, "photo": False})
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_download_chat_dtype_filter(self, mock_callback_query):
        """handle_toggle_download_chat_dtype_filter 应更新键盘为频道类型过滤键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        f = {
            "channel_123": {
                "download_type": {
                    DownloadType.VIDEO: True,
                    DownloadType.PHOTO: True,
                    DownloadType.AUDIO: True,
                    DownloadType.VOICE: True,
                    DownloadType.ANIMATION: True,
                    DownloadType.DOCUMENT: True,
                    DownloadType.VIDEO_NOTE: True,
                }
            }
        }
        await handler.handle_toggle_download_chat_dtype_filter(f, "channel_123")
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_table(self, mock_callback_query):
        """handle_toggle_table 应更新键盘为表格开关键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        config = {"export_table": {"link": True, "count": False, "upload": True}}
        await handler.handle_toggle_table(config)
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_back_table(self, mock_callback_query):
        """handle_back_table 应更新键盘为返回表格键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_back_table()
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_task_assign(self, mock_callback_query):
        """handle_task_assign 应更新键盘为任务分配键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_task_assign()
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_calendar_keyboard(self, mock_callback_query):
        """handle_calendar_keyboard 应更新键盘为日历键盘。"""
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_calendar_keyboard(
            CalenderKeyboard.START_TIME_BUTTON, 2026, 6
        )
        mock_callback_query.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_toggle_setting_error(self, mock_callback_query):
        """handle_toggle_setting 异常时应回复错误消息。"""
        mock_callback_query.message.edit_reply_markup.side_effect = Exception(
            "test error"
        )
        handler = KeyboardButtonHandler(mock_callback_query)
        global_config = {BotCallbackText.NOTICE: True, "upload": {}}
        user_config = {"is_shutdown": False}
        await handler.handle_toggle_setting(global_config, user_config)
        mock_callback_query.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_choice_export_table_message_not_modified(
        self, mock_callback_query
    ):
        """handle_choice_export_table 处理 MessageNotModified 不应报错。"""
        mock_callback_query.message.edit_reply_markup.side_effect = MessageNotModified(
            ""
        )
        handler = KeyboardButtonHandler(mock_callback_query)
        await handler.handle_choice_export_table(BotCallbackText.EXPORT_LINK_TABLE)
        # 不应抛出异常
        mock_callback_query.message.edit_reply_markup.assert_called_once()
