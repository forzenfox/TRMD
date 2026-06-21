# coding=UTF-8
"""键盘管理模块。

从 module/bot.py 中提取的键盘按钮管理逻辑，包括：
- KeyboardManager: 静态键盘构建方法
- KeyboardButtonHandler: 键盘按钮交互处理器
"""

import datetime
import calendar
from typing import Union, Optional

import pyrogram
from pyrogram.types.bots_and_keyboards import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified

from module import log
from module.language import _t
from module.enums import (
    CalenderKeyboard,
    DownloadType,
    BotCallbackText,
    BotButton,
    KeyWord,
)


class KeyboardManager:
    """键盘管理器：提供静态键盘构建方法。

    将原本分散在 Bot 类和 KeyboardButton 类中的静态键盘构建方法
    集中管理，便于复用和测试。
    """

    # ==================== 帮助/表格键盘 ====================

    @staticmethod
    def build_help_keyboard() -> InlineKeyboardMarkup:
        """构建帮助键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        BotButton.GITHUB,
                        url="https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases",
                    ),
                    InlineKeyboardButton(
                        BotButton.SUBSCRIBE_CHANNEL,
                        url="https://t.me/RestrictedMediaDownloader",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        BotButton.VIDEO_TUTORIAL,
                        url="https://www.youtube.com/watch?v=ucwKJu-MrBw",
                    )
                ],
                [
                    InlineKeyboardButton(
                        BotButton.SETTING, callback_data=BotCallbackText.SETTING
                    )
                ],
            ]
        )

    @staticmethod
    def build_table_keyboard() -> InlineKeyboardMarkup:
        """构建统计表选择键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        BotButton.LINK_TABLE, callback_data=BotCallbackText.LINK_TABLE
                    ),
                    InlineKeyboardButton(
                        BotButton.COUNT_TABLE, callback_data=BotCallbackText.COUNT_TABLE
                    ),
                ],
                [
                    InlineKeyboardButton(
                        BotButton.UPLOAD_TABLE,
                        callback_data=BotCallbackText.UPLOAD_TABLE,
                    )
                ],
                [
                    InlineKeyboardButton(
                        BotButton.HELP_PAGE, callback_data=BotCallbackText.BACK_HELP
                    )
                ],
            ]
        )

    # ==================== 设置键盘 ====================

    @staticmethod
    def build_setting_keyboard(
        global_config: dict, user_config: dict
    ) -> InlineKeyboardMarkup:
        """构建设置页面键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_NOTICE
                        if global_config.get(BotCallbackText.NOTICE)
                        else BotButton.OPEN_NOTICE,
                        callback_data=BotCallbackText.NOTICE,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.EXPORT_TABLE,
                        callback_data=BotCallbackText.EXPORT_TABLE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_EXIT_SHUTDOWN
                        if user_config.get("is_shutdown")
                        else BotButton.OPEN_EXIT_SHUTDOWN,
                        callback_data=BotCallbackText.SHUTDOWN,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.FORWARD_SETTING,
                        callback_data=BotCallbackText.FORWARD_SETTING,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.DOWNLOAD_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_SETTING,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.UPLOAD_SETTING,
                        callback_data=BotCallbackText.UPLOAD_SETTING,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.HELP_PAGE,
                        callback_data=BotCallbackText.BACK_HELP,
                    )
                ],
            ]
        )

    @staticmethod
    def build_upload_setting_keyboard(global_config: dict) -> InlineKeyboardMarkup:
        """构建上传设置键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_UPLOAD_DOWNLOAD
                        if global_config.get("upload").get("download_upload")
                        else BotButton.OPEN_UPLOAD_DOWNLOAD,
                        callback_data=BotCallbackText.UPLOAD_DOWNLOAD,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_UPLOAD_DOWNLOAD_DELETE
                        if global_config.get("upload").get("delete")
                        else BotButton.OPEN_UPLOAD_DOWNLOAD_DELETE,
                        callback_data=BotCallbackText.UPLOAD_DOWNLOAD_DELETE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN, callback_data=BotCallbackText.SETTING
                    )
                ],
            ]
        )

    @staticmethod
    def build_download_setting_keyboard(download_type: list) -> InlineKeyboardMarkup:
        """构建下载类型设置键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_ON
                        if DownloadType.VIDEO in download_type
                        else BotButton.VIDEO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_VIDEO,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.PHOTO_ON
                        if DownloadType.PHOTO in download_type
                        else BotButton.PHOTO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_PHOTO,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.AUDIO_ON
                        if DownloadType.AUDIO in download_type
                        else BotButton.AUDIO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_AUDIO,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.VOICE_ON
                        if DownloadType.VOICE in download_type
                        else BotButton.VOICE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_VOICE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.ANIMATION_ON
                        if DownloadType.ANIMATION in download_type
                        else BotButton.ANIMATION_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_ANIMATION,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOCUMENT_ON
                        if DownloadType.DOCUMENT in download_type
                        else BotButton.DOCUMENT_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_DOCUMENT,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_NOTE_ON
                        if DownloadType.VIDEO_NOTE in download_type
                        else BotButton.VIDEO_NOTE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_VIDEO_NOTE,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN, callback_data=BotCallbackText.SETTING
                    )
                ],
            ]
        )

    @staticmethod
    def build_forward_setting_keyboard(forward_type: dict) -> InlineKeyboardMarkup:
        """构建转发设置键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_ON
                        if forward_type.get("video")
                        else BotButton.VIDEO_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_VIDEO,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.PHOTO_ON
                        if forward_type.get("photo")
                        else BotButton.PHOTO_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_PHOTO,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.AUDIO_ON
                        if forward_type.get("audio")
                        else BotButton.AUDIO_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_AUDIO,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.VOICE_ON
                        if forward_type.get("voice")
                        else BotButton.VOICE_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_VOICE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.ANIMATION_ON
                        if forward_type.get("animation")
                        else BotButton.ANIMATION_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_ANIMATION,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOCUMENT_ON
                        if forward_type.get("document")
                        else BotButton.DOCUMENT_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_DOCUMENT,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.TEXT_ON
                        if forward_type.get("text")
                        else BotButton.TEXT_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_TEXT,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_NOTE_ON
                        if forward_type.get("video_note")
                        else BotButton.VIDEO_NOTE_OFF,
                        callback_data=BotCallbackText.TOGGLE_FORWARD_VIDEO_NOTE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN, callback_data=BotCallbackText.SETTING
                    )
                ],
            ]
        )

    # ==================== 导出表格键盘 ====================

    @staticmethod
    def build_export_table_keyboard(export_callback_data: str) -> InlineKeyboardMarkup:
        """构建导出表格选择后的键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.EXPORT_TABLE, callback_data=export_callback_data
                    ),
                    InlineKeyboardButton(
                        text=BotButton.RESELECT,
                        callback_data=BotCallbackText.BACK_TABLE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.HELP_PAGE,
                        callback_data=BotCallbackText.BACK_HELP,
                    )
                ],
            ]
        )

    @staticmethod
    def build_export_table_toggle_keyboard(
        config: dict, choice: Union[str, None] = None
    ) -> InlineKeyboardMarkup:
        """构建导出表格开关键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_LINK_TABLE
                        if config.get("export_table").get("link")
                        else BotButton.OPEN_LINK_TABLE,
                        callback_data=BotCallbackText.TOGGLE_LINK_TABLE,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_COUNT_TABLE
                        if config.get("export_table").get("count")
                        else BotButton.OPEN_COUNT_TABLE,
                        callback_data=BotCallbackText.TOGGLE_COUNT_TABLE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.CLOSE_UPLOAD_TABLE
                        if config.get("export_table").get("upload")
                        else BotButton.OPEN_UPLOAD_TABLE,
                        callback_data=BotCallbackText.TOGGLE_UPLOAD_TABLE,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN, callback_data=BotCallbackText.SETTING
                    )
                ],
            ]
        )

    # ==================== 下载频道过滤键盘 ====================

    @staticmethod
    def build_download_chat_filter_keyboard(
        include_comment: bool,
    ) -> InlineKeyboardMarkup:
        """构建下载频道过滤设置键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.DATE_RANGE_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOWNLOAD_DTYPE_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_DTYPE_FILTER,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.KEYWORD_FILTER_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.INCLUDE_COMMENT
                        if include_comment
                        else BotButton.IGNORE_COMMENT,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_COMMENT,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.EXECUTE_TASK,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_ID,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CANCEL_TASK,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL,
                    ),
                ],
            ]
        )

    @staticmethod
    def build_download_chat_dtype_filter_keyboard(
        download_chat_filter: dict, chat_id: str
    ) -> InlineKeyboardMarkup:
        """构建下载频道类型过滤键盘。"""
        dtype = download_chat_filter[chat_id]["download_type"]
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_ON
                        if dtype[DownloadType.VIDEO]
                        else BotButton.VIDEO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.PHOTO_ON
                        if dtype[DownloadType.PHOTO]
                        else BotButton.PHOTO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.AUDIO_ON
                        if dtype[DownloadType.AUDIO]
                        else BotButton.AUDIO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.VOICE_ON
                        if dtype[DownloadType.VOICE]
                        else BotButton.VOICE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.ANIMATION_ON
                        if dtype[DownloadType.ANIMATION]
                        else BotButton.ANIMATION_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOCUMENT_ON
                        if dtype[DownloadType.DOCUMENT]
                        else BotButton.DOCUMENT_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_NOTE_ON
                        if dtype[DownloadType.VIDEO_NOTE]
                        else BotButton.VIDEO_NOTE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_FILTER,
                    )
                ],
            ]
        )

    @staticmethod
    def build_date_range_keyboard() -> InlineKeyboardMarkup:
        """构建日期范围选择键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.SELECT_START_DATE,
                        callback_data=BotCallbackText.FILTER_START_DATE,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.SELECT_END_DATE,
                        callback_data=BotCallbackText.FILTER_END_DATE,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_FILTER,
                    )
                ],
            ]
        )

    # ==================== 日历/时间键盘 ====================

    @staticmethod
    def build_calendar_keyboard(
        dtype: Union[CalenderKeyboard, str],
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> list:
        """构建日历键盘的行列表（不含 InlineKeyboardMarkup 包装）。

        :param dtype: 日期类型（CalenderKeyboard.START_TIME_BUTTON 或 END_TIME_BUTTON）
        :param year: 年份，默认当前年份
        :param month: 月份，默认当前月份
        :return: 键盘行列表
        """
        if year is None:
            year = datetime.datetime.now().year
        if month is None:
            month = datetime.datetime.now().month

        keyboard: list = []
        prev_month: int = month - 1 if month > 1 else 12
        prev_year: int = year if month > 1 else year - 1
        next_month: int = month + 1 if month < 12 else 1
        next_year: int = year if month < 12 else year + 1

        if dtype == CalenderKeyboard.START_TIME_BUTTON:
            _dtype = "start"
        elif dtype == CalenderKeyboard.END_TIME_BUTTON:
            _dtype = "end"
        else:
            _dtype = str(dtype)

        nav_row = [
            InlineKeyboardButton(
                "◀️", callback_data=f"time_dec_month_{_dtype}_{prev_year}_{prev_month}"
            ),
            InlineKeyboardButton(
                f"{year}-{month:02d}", callback_data=BotCallbackText.NULL
            ),
            InlineKeyboardButton(
                "▶️", callback_data=f"time_inc_month_{_dtype}_{next_year}_{next_month}"
            ),
        ]
        keyboard.append(nav_row)

        week_days = ["一", "二", "三", "四", "五", "六", "日"]
        week_row = [
            InlineKeyboardButton(day, callback_data=BotCallbackText.NULL)
            for day in week_days
        ]
        keyboard.append(week_row)

        cal = calendar.monthcalendar(year, month)
        for week in cal:
            row = []
            for day in week:
                if day == 0:
                    row.append(
                        InlineKeyboardButton(" ", callback_data=BotCallbackText.NULL)
                    )
                else:
                    date_str = f"{year}-{month:02d}-{day:02d} 00:00:00"
                    row.append(
                        InlineKeyboardButton(
                            str(day),
                            callback_data=f"set_specific_time_{_dtype}_{date_str}",
                        )
                    )
            keyboard.append(row)

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=BotButton.CONFIRM_AND_RETURN,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER,
                ),
                InlineKeyboardButton(
                    text=BotButton.CANCEL_TASK,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL,
                ),
            ]
        )
        return keyboard

    @staticmethod
    def build_time_keyboard(
        dtype: Union[CalenderKeyboard, str], date: str, adjust_step: Optional[int] = 1
    ) -> InlineKeyboardMarkup:
        """构建时间选择键盘。

        :param dtype: 日期类型
        :param date: 日期字符串
        :param adjust_step: 步进值
        :return: InlineKeyboardMarkup
        """
        dt = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        _dtype = (
            dtype
            if isinstance(dtype, str)
            else "start"
            if dtype == CalenderKeyboard.START_TIME_BUTTON
            else "end"
        )
        hour, minute, second = "hour", "minute", "second"

        def _get_updated_time(field: str, delta: int) -> str:
            new_dt = dt.replace(
                hour=(dt.hour + delta) % 24 if field == hour else dt.hour,
                minute=(dt.minute + delta) % 60 if field == minute else dt.minute,
                second=(dt.second + delta) % 60 if field == second else dt.second,
            )
            return new_dt.strftime("%Y-%m-%d %H:%M:%S")

        time_keyboard = [
            [
                InlineKeyboardButton(
                    text=f"步进值:{adjust_step}",
                    callback_data=f"adjust_step_{dtype}_{adjust_step}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"set_time_{_dtype}_{_get_updated_time(hour, -adjust_step)}",
                ),
                InlineKeyboardButton(text="时", callback_data=BotCallbackText.NULL),
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"set_time_{_dtype}_{_get_updated_time(hour, adjust_step)}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"set_time_{_dtype}_{_get_updated_time(minute, -adjust_step)}",
                ),
                InlineKeyboardButton(text="分", callback_data=BotCallbackText.NULL),
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"set_time_{_dtype}_{_get_updated_time(minute, adjust_step)}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"set_time_{_dtype}_{_get_updated_time(second, -adjust_step)}",
                ),
                InlineKeyboardButton(text="秒", callback_data=BotCallbackText.NULL),
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"set_time_{_dtype}_{_get_updated_time(second, adjust_step)}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BotButton.CONFIRM_AND_RETURN,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER,
                ),
                InlineKeyboardButton(
                    text=BotButton.CANCEL_TASK,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL,
                ),
            ],
        ]

        return InlineKeyboardMarkup(time_keyboard)

    # ==================== 关键词键盘 ====================

    @staticmethod
    def build_keyword_filter_keyboard(
        adding_keywords: Optional[list] = None,
    ) -> InlineKeyboardMarkup:
        """构建关键词过滤设置键盘。"""
        if adding_keywords:
            keyword_buttons = [
                [
                    InlineKeyboardButton(
                        text=BotButton.INPUT_KEYWORD, callback_data=BotCallbackText.NULL
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.CONFIRM_KEYWORD,
                        callback_data=BotCallbackText.CONFIRM_KEYWORD,
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CANCEL,
                        callback_data=BotCallbackText.CANCEL_KEYWORD_INPUT,
                    ),
                ],
            ]
        else:
            keyword_buttons = [
                [
                    InlineKeyboardButton(
                        text=BotButton.INPUT_KEYWORD, callback_data=BotCallbackText.NULL
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN,
                        callback_data=BotCallbackText.CANCEL_KEYWORD_INPUT,
                    )
                ],
            ]
        return InlineKeyboardMarkup(keyword_buttons)

    # ==================== 通用键盘 ====================

    @staticmethod
    def build_restrict_forward_keyboard() -> InlineKeyboardMarkup:
        """构建受限转发提示键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        BotButton.DOWNLOAD, callback_data=BotCallbackText.DOWNLOAD
                    ),
                    InlineKeyboardButton(
                        BotButton.DOWNLOAD_UPLOAD,
                        callback_data=BotCallbackText.DOWNLOAD_UPLOAD,
                    ),
                ]
            ]
        )

    @staticmethod
    def build_single_button_keyboard(
        text: str, callback_data: str
    ) -> InlineKeyboardMarkup:
        """构建单按钮键盘。"""
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=text, callback_data=callback_data)]]
        )

    @staticmethod
    def build_back_table_keyboard() -> InlineKeyboardMarkup:
        """构建返回表格选择键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.RESELECT,
                        callback_data=BotCallbackText.BACK_TABLE,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.HELP_PAGE,
                        callback_data=BotCallbackText.BACK_HELP,
                    )
                ],
            ]
        )

    @staticmethod
    def build_task_assign_keyboard() -> InlineKeyboardMarkup:
        """构建任务分配键盘。"""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.TASK_ASSIGN, callback_data=BotCallbackText.NULL
                    )
                ]
            ]
        )


class KeyboardButtonHandler:
    """键盘按钮交互处理器：处理键盘按钮点击事件。

    将原本 KeyboardButton 类中的异步交互方法提取出来，
    与静态键盘构建方法分离，保持职责清晰。
    """

    def __init__(self, callback_query: CallbackQuery):
        self.callback_query = callback_query

    # ==================== 导出表格按钮处理 ====================

    async def handle_choice_export_table(
        self, choice: Union[BotCallbackText, str]
    ) -> None:
        """处理导出表格选择按钮点击。"""
        export_callback_data: str = ""
        if choice == BotCallbackText.EXPORT_LINK_TABLE:
            export_callback_data = BotCallbackText.EXPORT_LINK_TABLE
        elif choice == BotCallbackText.EXPORT_COUNT_TABLE:
            export_callback_data = BotCallbackText.EXPORT_COUNT_TABLE
        elif choice == BotCallbackText.EXPORT_UPLOAD_TABLE:
            export_callback_data = BotCallbackText.EXPORT_UPLOAD_TABLE
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_export_table_keyboard(export_callback_data)
            )
        except MessageNotModified:
            pass

    # ==================== 设置按钮处理 ====================

    async def handle_toggle_setting(
        self, global_config: dict, user_config: dict
    ) -> None:
        """处理设置按钮切换。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_setting_keyboard(global_config, user_config)
            )
        except MessageNotModified:
            pass
        except Exception as e:
            await self.callback_query.message.reply_text(
                "切换按钮状态失败\n(具体原因请前往终端查看报错信息)"
            )
            log.error(f'切换按钮状态失败,{_t(KeyWord.REASON)}:"{e}"')

    async def handle_toggle_upload_setting(self, global_config: dict) -> None:
        """处理上传设置按钮切换。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_upload_setting_keyboard(global_config)
            )
        except MessageNotModified:
            pass

    async def handle_toggle_download_setting(self, download_type: list) -> None:
        """处理下载设置按钮切换。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_download_setting_keyboard(download_type)
            )
        except MessageNotModified:
            pass

    async def handle_toggle_forward_setting(self, forward_type: dict) -> None:
        """处理转发设置按钮切换。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_forward_setting_keyboard(forward_type)
            )
        except MessageNotModified:
            pass

    async def handle_toggle_download_chat_dtype_filter(
        self, download_chat_filter: dict, chat_id: str
    ) -> None:
        """处理下载频道类型过滤按钮切换。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_download_chat_dtype_filter_keyboard(
                    download_chat_filter, chat_id
                )
            )
        except MessageNotModified:
            pass

    # ==================== 表格按钮处理 ====================

    async def handle_toggle_table(
        self, config: dict, choice: Union[str, None] = None
    ) -> None:
        """处理表格导出开关按钮切换。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_export_table_toggle_keyboard(config, choice)
            )
        except MessageNotModified:
            pass
        except Exception as _e:
            if choice:
                prompt_map = {"link": "链接", "count": "计数", "upload": "上传"}
                prompt = prompt_map.get(choice, "")
                await self.callback_query.message.reply_text(
                    f"设置启用或禁用导出{prompt}统计表失败\n(具体原因请前往终端查看报错信息)"
                )
                log.error(
                    f'设置启用或禁用导出{prompt}统计表失败,{_t(KeyWord.REASON)}:"{_e}"'
                )
            else:
                log.error(f'设置启用或禁用导出统计表失败,{_t(KeyWord.REASON)}:"{_e}"')

    async def handle_back_table(self) -> None:
        """处理返回表格选择按钮。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_back_table_keyboard()
            )
        except MessageNotModified:
            pass

    async def handle_task_assign(self) -> None:
        """处理任务分配按钮。"""
        try:
            await self.callback_query.message.edit_reply_markup(
                KeyboardManager.build_task_assign_keyboard()
            )
        except MessageNotModified:
            pass

    # ==================== 日历键盘处理 ====================

    async def handle_calendar_keyboard(
        self,
        dtype: Union[CalenderKeyboard, str],
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> None:
        """处理日历键盘显示。"""
        if year is None:
            year = datetime.datetime.now().year
        if month is None:
            month = datetime.datetime.now().month
        keyboard = KeyboardManager.build_calendar_keyboard(dtype, year, month)
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(keyboard)
            )
        except MessageNotModified:
            pass
