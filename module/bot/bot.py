# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/1/24 21:27
# File:bot.py
import os
import copy
import asyncio
import datetime
import calendar
from functools import partial
from typing import List, Dict, Union, Optional, Callable

import pyrogram
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors import FloodWait, FloodPremiumWait
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageNotModified,
    AccessTokenInvalid,
)
from pyrogram.types.bots_and_keyboards import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

from module import (
    __version__,
    __copyright__,
    __license__,
    console,
    log,
    SOFTWARE_FULL_NAME,
    LINK_PREVIEW_OPTIONS,
)
from module.language import _t
from module.utils.stdio import MetaData
from module.task import UploadTask
from module.config import GlobalConfig
from module.utils.path_tool import safe_scan_directory_file
from module.utils.helpers import (
    parse_link,
    safe_index,
    safe_message,
    is_allow_upload,
    get_valid_chat_id,
)
from module.enums import (
    CalenderKeyboard,
    UploadStatus,
    DownloadType,
    BotCommandText,
    BotMessage,
    BotCallbackText,
    BotButton,
    KeyWord,
)
from module.core.token_manager import TokenManager
from module.interaction_manager import InteractionManager
from module.bot.commands import BotCommands

# 新增模块：重构后的职责分离组件
from module.bot.state_manager import StateManager
from module.bot.keyboard_manager import KeyboardManager, KeyboardButtonHandler
from module.bot.utils import MessageHelper, TextFormatter, ValidationHelper
from module.bot.command_router import CommandRouter


class Bot:
    BOT_NAME: str = "TRMD_BOT"
    COMMANDS: List[BotCommand] = [
        BotCommand(BotCommandText.HELP[0], BotCommandText.HELP[1]),
        BotCommand(
            BotCommandText.DOWNLOAD[0], BotCommandText.DOWNLOAD[1].replace("`", "")
        ),
        BotCommand(BotCommandText.TABLE[0], BotCommandText.TABLE[1]),
        BotCommand(
            BotCommandText.FORWARD[0], BotCommandText.FORWARD[1].replace("`", "")
        ),
        BotCommand(BotCommandText.EXIT[0], BotCommandText.EXIT[1]),
        BotCommand(
            BotCommandText.LISTEN_DOWNLOAD[0],
            BotCommandText.LISTEN_DOWNLOAD[1].replace("`", ""),
        ),
        BotCommand(
            BotCommandText.LISTEN_FORWARD[0],
            BotCommandText.LISTEN_FORWARD[1].replace("`", ""),
        ),
        BotCommand(BotCommandText.LISTEN_INFO[0], BotCommandText.LISTEN_INFO[1]),
        BotCommand(BotCommandText.UPLOAD[0], BotCommandText.UPLOAD[1].replace("`", "")),
        BotCommand(
            BotCommandText.UPLOAD_R[0], BotCommandText.UPLOAD_R[1].replace("`", "")
        ),
        BotCommand(
            BotCommandText.DOWNLOAD_CHAT[0],
            BotCommandText.DOWNLOAD_CHAT[1].replace("`", ""),
        ),
    ]

    def __init__(self):
        self.application = None
        self.user: Union[pyrogram.Client, None] = None
        self.bot: Union[pyrogram.Client, None] = None
        self.is_bot_running: bool = False
        self.bot_task_link: set = set()
        self.gc: Union[GlobalConfig, None] = (
            None  # 延迟初始化，在 _init_global_config 中设置
        )
        self.root: list = []
        self.last_client: Union[pyrogram.Client, None] = None
        self.last_message: Union[pyrogram.types.Message, None] = None
        self.bot_commands: Union[BotCommands, None] = None  # 新命令处理器

        # 重构后的职责分离组件
        self._state = StateManager()
        self._commands = CommandRouter(self._state)
        self._keyboards = KeyboardManager()

    def _init_global_config(self, user_config=None) -> None:
        """初始化 GlobalConfig，从 UserConfig 读取合并后的配置。

        Args:
            user_config: UserConfig 实例（Application）。如果提供，
                         GlobalConfig 将从 UserConfig 的分组结构读取配置；
                         否则回退到独立的 .CONFIG.yaml 文件。
        """
        self.gc = GlobalConfig(user_config=user_config)

    # ==================== 向后兼容的状态属性 ====================

    @property
    def listen_download_chat(self) -> dict:
        return self._state.listen_download_chat

    @listen_download_chat.setter
    def listen_download_chat(self, value: dict):
        self._state.listen_download_chat = value

    @property
    def listen_forward_chat(self) -> dict:
        return self._state.listen_forward_chat

    @listen_forward_chat.setter
    def listen_forward_chat(self, value: dict):
        self._state.listen_forward_chat = value

    @property
    def handle_media_groups(self) -> dict:
        return self._state.handle_media_groups

    @handle_media_groups.setter
    def handle_media_groups(self, value: dict):
        self._state.handle_media_groups = value

    @property
    def download_chat_filter(self) -> dict:
        return self._state.download_chat_filter

    @download_chat_filter.setter
    def download_chat_filter(self, value: dict):
        self._state.download_chat_filter = value

    @property
    def adding_keywords(self) -> list:
        return self._state.adding_keywords

    @adding_keywords.setter
    def adding_keywords(self, value: list):
        self._state.adding_keywords = value

    @property
    def keyword_handler(self) -> Union[MessageHandler, None]:
        return self._state.keyword_handler

    @keyword_handler.setter
    def keyword_handler(self, value: Union[MessageHandler, None]):
        self._state.keyword_handler = value

    def add_handler(self, handler, group: int = 0):
        """添加handler到指定的group。直接操作dispatcher.groups以确保正确添加。"""
        if group not in self.bot.dispatcher.groups:
            self.bot.dispatcher.groups[group] = []
        self.bot.dispatcher.groups[group].append(handler)
        log.info(
            f"添加handler到group={group},当前handler数量:{len(self.bot.dispatcher.groups[group])}"
        )

    def remove_handler(self, handler, group: int = 0):
        """从指定的group中移除handler。直接操作dispatcher.groups以确保正确移除。"""
        if (
            group in self.bot.dispatcher.groups
            and handler in self.bot.dispatcher.groups[group]
        ):
            self.bot.dispatcher.groups[group].remove(handler)
            log.info(
                f"从group={group}移除handler,剩余handler数量:{len(self.bot.dispatcher.groups[group])}"
            )

    def add_keyword_mode_handler(
        self,
        chat_id,
        callback_query: CallbackQuery,
        callback_prompt: Callable,
        enable: bool,
    ):
        """添加或移除关键词输入模式的handler。（委托给 CommandRouter）"""
        self.keyword_handler = CommandRouter.add_keyword_mode_handler(
            add_handler_fn=self.add_handler,
            remove_handler_fn=self.remove_handler,
            root=self.root,
            chat_id=chat_id,
            callback_query=callback_query,
            callback_prompt=callback_prompt,
            handle_keyword_fn=self._commands.handle_keyword_input,
            enable=enable,
        )

    async def process_error_message(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> None:
        """处理未知命令/错误消息。（委托给 CommandRouter）"""
        await self._commands.process_error_message(
            client, message, self.keyword_handler
        )

    async def handle_keyword_input(
        self,
        chat_id: Union[str, int],
        callback_query: CallbackQuery,
        callback_prompt: Callable,
        _client: pyrogram.Client,
        message: pyrogram.types.Message,
    ) -> None:
        """处理用户输入的关键词。（委托给 CommandRouter）"""
        await self._commands.handle_keyword_input(
            chat_id, callback_query, callback_prompt, _client, message
        )

    @staticmethod
    async def check_download_range(
        start_id: int,
        end_id: int,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
    ) -> bool:
        """验证下载范围。（委托给 ValidationHelper）"""
        return await ValidationHelper.check_download_range(
            start_id, end_id, client, message
        )

    def get_download_link_from_bot(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        with_upload: Union[dict, None] = None,
    ) -> Union[Dict[str, Union[set, pyrogram.types.Message]], None]:
        """解析下载链接命令。（委托给 CommandRouter）"""
        return self._commands.get_download_link_from_bot(
            client, message, self.user, self.bot, with_upload
        )

    def get_download_chat_link_from_bot(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
    ):
        """解析下载频道命令。（委托给 CommandRouter）"""
        return self._commands.get_download_chat_link_from_bot(
            client, message, self.user
        )

    @staticmethod
    async def safe_process_message(
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        text: list,
        last_message_id: int = -1,
        reply_markup: Union[pyrogram.types.InlineKeyboardMarkup, None] = None,
    ) -> pyrogram.types.Message:
        """安全发送消息。（委托给 MessageHelper）"""
        return await MessageHelper.safe_process_message(
            client, message, text, last_message_id, reply_markup
        )

    @staticmethod
    async def help(
        client: Union[pyrogram.Client, None] = None,
        message: Union[pyrogram.types.Message, None] = None,
    ) -> Union[None, dict]:
        """帮助命令。（委托给 CommandRouter）"""
        # 使用类级别的静态方法
        return await CommandRouter(StateManager()).help(client, message)

    async def start(self, client: pyrogram.Client, message: pyrogram.types.Message):
        """开始命令。（委托给 CommandRouter）"""
        await self._commands.start(client, message)

    @staticmethod
    async def callback_data(
        client: pyrogram.Client, callback_query: CallbackQuery
    ) -> Union[str, None]:
        """处理回调数据。（委托给 CommandRouter）"""
        return await CommandRouter.callback_data(client, callback_query)

    @staticmethod
    async def table(
        client: Union[pyrogram.Client, None] = None,
        message: Union[pyrogram.types.Message, None] = None,
    ) -> Union[None, dict]:
        """表格命令。（委托给 CommandRouter）"""
        return await CommandRouter(StateManager()).table(client, message)

    def get_forward_link_from_bot(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> Union[Dict[str, Union[list, str]], None]:
        """解析转发命令。（委托给 CommandRouter）"""
        return self._commands.get_forward_link_from_bot(client, message)

    def get_upload_link_from_bot(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        delete: bool = False,
        save_directory: str = None,
        recursion: bool = False,
        valid_link_cache: dict = None,
    ):
        """解析上传命令。（委托给 CommandRouter）"""
        return self._commands.get_upload_link_from_bot(
            client,
            message,
            self.user,
            self.bot,
            self.last_message,
            delete,
            save_directory,
            recursion,
            valid_link_cache,
        )

    async def exit(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> None:
        """退出命令。（委托给 CommandRouter）"""
        self.is_bot_running = False
        await self._commands.exit_bot(client, message)

    async def on_listen(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> Union[Dict[str, list], None]:
        """处理监听命令。（委托给 CommandRouter）"""
        return self._commands.on_listen(client, message)

    @staticmethod
    async def listen_download(client: pyrogram.Client, message: pyrogram.types.Message):
        pass

    @staticmethod
    async def listen_forward(client: pyrogram.Client, message: pyrogram.types.Message):
        pass

    async def cancel_listen(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        link: str,
        command: str,
    ):
        pass

    async def handle_batch_message(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ):
        """处理批量操作流程中的用户输入。"""
        if self.bot_commands is None:
            return
        user_id = message.from_user.id
        # 仅在有活跃流程时处理
        if not self.bot_commands._interaction_manager.has_active_flow(user_id):
            return
        await self.bot_commands.handle_batch_input(client, message)

    def _register_new_command_handlers(self, bot_username: str = None):
        """注册新命令 handlers (/web, /batch, /status, /cancel)。"""
        from pyrogram.handlers import MessageHandler
        from pyrogram import filters

        # 初始化 BotCommands 实例
        if self.bot_commands is None:
            token_mgr = TokenManager(storage_type="sqlite")
            interaction_mgr = InteractionManager()
            self.bot_commands = BotCommands(
                token_manager=token_mgr,
                interaction_manager=interaction_mgr,
                webui_base_url=f"http://localhost:8000",
            )

        # 注册 /web 命令
        self.bot.add_handler(
            MessageHandler(
                self.bot_commands.cmd_web,
                filters=filters.command(["web"]) & filters.user(self.root),
            )
        )
        # 注册 /web_revoke 命令
        self.bot.add_handler(
            MessageHandler(
                self.bot_commands.cmd_web_revoke,
                filters=filters.command(["web_revoke"]) & filters.user(self.root),
            )
        )
        # 注册 /batch 命令
        self.bot.add_handler(
            MessageHandler(
                self.bot_commands.cmd_batch,
                filters=filters.command(["batch"]) & filters.user(self.root),
            )
        )
        # 注册 /status 命令
        self.bot.add_handler(
            MessageHandler(
                self.bot_commands.cmd_status,
                filters=filters.command(["status"]) & filters.user(self.root),
            )
        )
        # 注册 /cancel 命令
        self.bot.add_handler(
            MessageHandler(
                self.bot_commands.cmd_cancel,
                filters=filters.command(["cancel"]) & filters.user(self.root),
            )
        )
        # 注册批量输入消息处理器 (非命令文本，当有活跃流程时处理)
        self.bot.add_handler(
            MessageHandler(
                self.handle_batch_message,
                filters=filters.text & ~filters.command & filters.user(self.root),
                group=1,
            )
        )

        # 更新 COMMANDS 列表
        new_commands = [
            BotCommand(cmd, desc) for cmd, desc in self.bot_commands.get_commands()
        ]
        self.COMMANDS.extend(new_commands)
        log.info(f"已注册 {len(new_commands)} 个新命令")

    async def listen_info(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ):
        """监听信息命令。（委托给 CommandRouter）"""
        await self._commands.listen_info(client, message)

    async def handle_forwarded_media(
        self, user_client: pyrogram.Client, user_message: pyrogram.types.Message
    ):
        pass

    async def done_notice(self, text):
        if self.gc.get_config(BotCallbackText.NOTICE):
            if all([self.last_client, self.last_message]):
                while True:
                    try:
                        await self.last_client.send_message(
                            chat_id=self.last_message.from_user.id,
                            text=f"📢通知:\n{text}",
                            link_preview_options=LINK_PREVIEW_OPTIONS,
                        )
                        break
                    except (FloodWait, FloodPremiumWait) as e:
                        amount = e.value
                        console.log(
                            f"[{self.bot.name}]发送消息请求频繁,要求等待{amount}秒后继续运行。",
                            style="#FF4689",
                        )
                        await asyncio.sleep(amount)
                    except Exception as e:
                        log.error(f'无法发送通知,{_t(KeyWord.REASON)}:"{e}"')

    async def start_bot(
        self,
        application,
        user_client_obj: pyrogram.Client,
        bot_client_obj: pyrogram.Client,
    ) -> str:
        """启动机器人。"""
        try:
            self.application = application
            self.bot = bot_client_obj
            self.user = user_client_obj
            root = await self.user.get_me()
            self.root.append(root.id)
            await bot_client_obj.start()
            await self.bot.set_bot_commands(self.COMMANDS)
            bot = await self.bot.get_me()
            bot_username = getattr(bot, "username", None)

            self.bot.add_handler(
                MessageHandler(
                    self.start,
                    filters=pyrogram.filters.command(["start"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.help,
                    filters=pyrogram.filters.command(["help"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_link_from_bot,
                    filters=pyrogram.filters.command(["download"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_chat_link_from_bot,
                    filters=pyrogram.filters.command(["download_chat"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_upload_link_from_bot,
                    filters=pyrogram.filters.command(["upload"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_upload_link_from_bot,
                    filters=pyrogram.filters.command(["upload_r"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.table,
                    filters=pyrogram.filters.command(["table"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_forward_link_from_bot,
                    filters=pyrogram.filters.command(["forward"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.exit,
                    filters=pyrogram.filters.command(["exit"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.on_listen,
                    filters=pyrogram.filters.command(
                        ["listen_download", "listen_forward"]
                    )
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.listen_info,
                    filters=pyrogram.filters.command(["listen_info"])
                    & pyrogram.filters.user(self.root),
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_link_from_bot,
                    filters=pyrogram.filters.regex(r"^https://t.me.*")
                    & pyrogram.filters.user(self.root),
                )
            )
            self.user.add_handler(
                MessageHandler(
                    self.handle_forwarded_media,
                    filters=pyrogram.filters.user(self.root)
                    & pyrogram.filters.forwarded
                    & pyrogram.filters.chat(bot_username)
                    & (
                        pyrogram.filters.video
                        | pyrogram.filters.photo
                        | pyrogram.filters.audio
                        | pyrogram.filters.voice
                        | pyrogram.filters.animation
                        | pyrogram.filters.document
                        | pyrogram.filters.video_note
                    ),
                )
            )
            self.bot.add_handler(
                CallbackQueryHandler(
                    self.callback_data, filters=pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.process_error_message,
                    filters=pyrogram.filters.user(self.root)
                    & ~(
                        pyrogram.filters.video
                        | pyrogram.filters.photo
                        | pyrogram.filters.audio
                        | pyrogram.filters.voice
                        | pyrogram.filters.animation
                        | pyrogram.filters.document
                        | pyrogram.filters.video_note
                    ),
                )
            )
            # 注册新命令 handlers (/web, /batch, /status, /cancel)
            self._register_new_command_handlers(bot_username=bot_username)
            self.is_bot_running: bool = True
            await self.send_message_to_bot(text="/start")
            return f"🤖「机器人」启动成功。({BotButton.OPEN_NOTICE if self.gc.config.get(BotCallbackText.NOTICE) else BotButton.CLOSE_NOTICE})"
        except AccessTokenInvalid as e:
            self.is_bot_running: bool = False
            return f'🤖「机器人」启动失败,「bot_token」错误,{_t(KeyWord.REASON)}:"{e}"'
        except Exception as e:
            self.is_bot_running: bool = False
            return f'🤖「机器人」启动失败,{_t(KeyWord.REASON)}:"{e}"'

    async def send_message_to_bot(self, text: str, catch: bool = False):
        try:
            bot_username = getattr(await self.bot.get_me(), "username", None)
            if bot_username:
                return await self.user.send_message(
                    chat_id=bot_username,
                    text=text,
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                )
        except Exception as e:
            if catch:
                raise Exception(str(e))
            else:
                return e

    @staticmethod
    def update_text(
        right_link: set, invalid_link: set, exist_link: Union[set, None] = None
    ) -> list:
        """格式化下载结果文本。（委托给 TextFormatter）"""
        return TextFormatter.update_text(right_link, invalid_link, exist_link)

    async def safe_edit_message(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        last_message_id: int,
        text: Union[str, List[str]],
        reply_markup: Union[pyrogram.types.InlineKeyboardMarkup, None] = None,
    ) -> Union[pyrogram.types.Message, None]:
        """安全编辑消息。（委托给 MessageHelper）"""
        return await MessageHelper.safe_edit_message(
            client, message, last_message_id, text, reply_markup
        )


class KeyboardButton:
    """键盘按钮管理器（向后兼容包装）。

    委托给 KeyboardButtonHandler 和 KeyboardManager 实现。
    """

    def __init__(self, callback_query: pyrogram.types.CallbackQuery):
        self.callback_query = callback_query
        self._handler = KeyboardButtonHandler(callback_query)

    async def choice_export_table_button(
        self, choice: Union[BotCallbackText, str]
    ) -> None:
        """处理导出表格选择按钮。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_choice_export_table(choice)

    async def toggle_setting_button(
        self, global_config: dict, user_config: dict
    ) -> None:
        """处理设置按钮切换。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_toggle_setting(global_config, user_config)

    async def toggle_upload_setting_button(self, global_config: dict):
        """处理上传设置按钮切换。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_toggle_upload_setting(global_config)

    async def toggle_download_setting_button(self, user_config: dict):
        """处理下载设置按钮切换。（委托给 KeyboardButtonHandler）"""
        download_type = user_config.get("download_type", [])
        await self._handler.handle_toggle_download_setting(download_type)

    async def toggle_forward_setting_button(self, global_config: dict):
        """处理转发设置按钮切换。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_toggle_forward_setting(
            global_config.get("forward_type", {})
        )

    @staticmethod
    def toggle_download_chat_type_filter_button(download_chat_filter: dict):
        """切换下载频道类型过滤按钮。（委托给 KeyboardManager）"""
        chat_id = BotCallbackText.DOWNLOAD_CHAT_ID
        return KeyboardManager.build_download_chat_dtype_filter_keyboard(
            download_chat_filter, chat_id
        )

    async def toggle_table_button(
        self, config: dict, choice: Union[str, None] = None
    ) -> None:
        """处理表格开关按钮切换。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_toggle_table(config, choice)

    async def back_table_button(self):
        """处理返回表格选择按钮。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_back_table()

    async def task_assign_button(self):
        """处理任务分配按钮。（委托给 KeyboardButtonHandler）"""
        await self._handler.handle_task_assign()

    @staticmethod
    def restrict_forward_button():
        """构建受限转发键盘。（委托给 KeyboardManager）"""
        return KeyboardManager.build_restrict_forward_keyboard()

    @staticmethod
    def single_button(text: str, callback_data: str):
        """构建单按钮键盘。（委托给 KeyboardManager）"""
        return KeyboardManager.build_single_button_keyboard(text, callback_data)

    @staticmethod
    def download_chat_filter_button(include_comment: bool):
        """构建下载频道过滤键盘。（委托给 KeyboardManager）"""
        return KeyboardManager.build_download_chat_filter_keyboard(include_comment)

    @staticmethod
    def filter_date_range_button():
        """构建日期范围键盘。（委托给 KeyboardManager）"""
        return KeyboardManager.build_date_range_keyboard()

    async def calendar_keyboard(
        self,
        dtype: Union[CalenderKeyboard, str],
        year: Optional[int] = None,
        month: Optional[int] = None,
    ):
        """构建日历键盘。（委托给 KeyboardButtonHandler）"""
        if year is None:
            year = datetime.datetime.now().year
        if month is None:
            month = datetime.datetime.now().month
        await self._handler.handle_calendar_keyboard(dtype, year, month)

    @staticmethod
    def time_keyboard(
        dtype: Union[CalenderKeyboard, str], date: str, adjust_step: Optional[int] = 1
    ):
        """构建时间键盘。（委托给 KeyboardManager）"""
        return KeyboardManager.build_time_keyboard(dtype, date, adjust_step)

    @staticmethod
    def keyword_filter_button(adding_keywords: Optional[list] = None):
        """构建关键词过滤键盘。（委托给 KeyboardManager）"""
        return KeyboardManager.build_keyword_filter_keyboard(adding_keywords)


class CallbackData:
    def __init__(self, data: Union[dict, None] = None):
        self.data: Union[dict, None] = data
