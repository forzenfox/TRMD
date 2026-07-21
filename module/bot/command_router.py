# coding=UTF-8
"""命令路由模块。

从 module/bot.py 中提取的命令路由和消息处理逻辑，包括：
- CommandRouter: 命令路由和分发
- 各个命令的处理方法（help/start/table/download/forward/upload/listen/exit）
- 消息处理和关键词输入处理
"""

import copy
import os
import asyncio
from functools import partial
from typing import Any, Callable, Dict, Optional, Union, cast, TYPE_CHECKING

import pyrogram
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.handlers import MessageHandler
from pyrogram.types.bots_and_keyboards import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified

from module import (
    __version__,
    __copyright__,
    __license__,
    log,
    SOFTWARE_FULL_NAME,
    LINK_PREVIEW_OPTIONS,
)
from module.core.language import _t
from module.core.task.legacy import UploadTask
from module.utils.path_tool import safe_scan_directory_file
from module.utils.helpers import (
    safe_index,
    is_allow_upload,
    get_valid_chat_id,
)
from module.core.enums import (
    UploadStatus,
    DownloadType,
    BotCommandText,
    BotCallbackText,
    BotButton,
    KeyWord,
)
from module.bot.utils import MessageHelper, TextFormatter, ValidationHelper
from module.bot.keyboard_manager import KeyboardManager
from module.bot.state_manager import StateManager

from module.core.task.manager import TaskType, TaskStatus

if TYPE_CHECKING:
    from module.core.identifier_service import IdentifierService, IdentifierServiceError


class CommandRouter:
    """命令路由器：负责路由和处理各种 Bot 命令。

    将原本分散在 Bot 类中的命令处理方法集中管理，
    通过依赖注入接收 StateManager 和 KeyboardManager，
    保持与 Bot 类的解耦。
    """

    def __init__(
        self,
        state_manager: StateManager,
        keyboard_manager: Optional[KeyboardManager] = None,
        identifier_service: Optional["IdentifierService"] = None,
        task_manager: Optional[Any] = None,
        task_executor: Optional[Any] = None,
    ):
        """
        :param state_manager: 状态管理器实例
        :param keyboard_manager: 键盘管理器实例（可选，默认创建新实例）
        :param identifier_service: 标识符解析服务（可选，默认从 AppContext 延迟获取）
        :param task_manager: TaskManager 实例（可选，默认从 AppContext 延迟获取）
        :param task_executor: TaskExecutor 实例（可选，默认从 AppContext 延迟获取）
        """
        self.state_manager = state_manager
        self.keyboard_manager = keyboard_manager or KeyboardManager()
        self._identifier_service_cache: Optional["IdentifierService"] = (
            identifier_service
        )
        self._task_manager_cache: Optional[Any] = task_manager
        self._task_executor_cache: Optional[Any] = task_executor
        self._resolved_chat_id_cache: dict[str, str] = {}

    @property
    def _task_manager(self):
        """获取 TaskManager 实例（延迟加载）。"""
        if self._task_manager_cache is not None:
            return self._task_manager_cache
        from module.core.integration import get_context

        ctx = get_context()
        if ctx:
            self._task_manager_cache = getattr(ctx, "task_manager", None)
        return self._task_manager_cache

    @property
    def _task_executor(self):
        """获取 TaskExecutor 实例（延迟加载）。"""
        if self._task_executor_cache is not None:
            return self._task_executor_cache
        from module.core.integration import get_context

        ctx = get_context()
        if ctx:
            self._task_executor_cache = getattr(ctx, "task_executor", None)
        return self._task_executor_cache

    @property
    def _identifier_service(self) -> Optional["IdentifierService"]:
        """获取 IdentifierService 实例。

        优先使用构造函数注入的实例；若未注入，则尝试从 AppContext 单例获取 client 创建。
        """
        if self._identifier_service_cache is not None:
            return self._identifier_service_cache
        from module.core.integration import get_context

        ctx = get_context()
        if ctx and getattr(ctx, "client", None):
            from module.core.identifier_service import IdentifierService

            self._identifier_service_cache = IdentifierService(ctx.client)
        return self._identifier_service_cache

    def _format_resolve_error(self, error: "IdentifierServiceError") -> str:
        """将 IdentifierServiceError 映射为用户友好的 Bot 错误提示。"""
        from module.core.identifier_service import (
            InvalidIdentifierError,
            UserNotFoundError,
            AccessDeniedError,
            RateLimitedError,
            ResolveTimeoutError,
        )

        if isinstance(error, InvalidIdentifierError):
            return "❌❌❌链接格式无效❌❌❌"
        if isinstance(error, UserNotFoundError):
            return "❌❌❌找不到频道❌❌❌"
        if isinstance(error, AccessDeniedError):
            return "❌❌❌无权访问该频道❌❌❌"
        if isinstance(error, RateLimitedError):
            return "❌❌❌请求过于频繁，请稍后重试❌❌❌"
        if isinstance(error, ResolveTimeoutError):
            return "❌❌❌解析超时，请重试❌❌❌"
        return f"❌❌❌解析失败:{error.message}❌❌❌"

    @staticmethod
    def _message_user_id(message: pyrogram.types.Message) -> int:
        """安全获取消息发送者用户 ID。

        Bot 收到的命令消息理论上一定包含 from_user；若不存在则返回 0 避免崩溃。
        """
        user = message.from_user
        return user.id if user is not None else 0

    @staticmethod
    def _message_text(message: pyrogram.types.Message) -> str:
        """安全获取消息文本，None 时返回空字符串。"""
        return message.text or ""

    # ==================== 帮助/开始/表格命令 ====================

    async def help(
        self,
        client: Union[pyrogram.Client, None] = None,
        message: Union[pyrogram.types.Message, None] = None,
    ) -> Union[None, dict]:
        """帮助命令：返回帮助信息和键盘。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: 当 client 和 message 都为 None 时返回 dict
        """
        keyboard = KeyboardManager.build_help_keyboard()

        text = (
            f"`\n💎 {SOFTWARE_FULL_NAME} v{__version__} 💎\n"
            f"©️ {__copyright__.replace(' <https://github.com/Gentlesprite>', '.')}\n"
            f"📖 Licensed under the terms of the {__license__}.`\n\n"
            f"️ 可用命令:\n"
            f"🛎️ {BotCommandText.with_description(BotCommandText.HELP)}\n"
            f"📁 {BotCommandText.with_description(BotCommandText.DOWNLOAD)}\n"
            f" {BotCommandText.with_description(BotCommandText.TABLE)}\n"
            f"↗️ {BotCommandText.with_description(BotCommandText.FORWARD)}\n"
            f"❌ {BotCommandText.with_description(BotCommandText.EXIT)}\n"
            f"🕵️ {BotCommandText.with_description(BotCommandText.LISTEN_DOWNLOAD)}\n"
            f"📲 {BotCommandText.with_description(BotCommandText.LISTEN_FORWARD)}\n"
            f"🔍 {BotCommandText.with_description(BotCommandText.LISTEN_INFO)}\n"
            f" {BotCommandText.with_description(BotCommandText.UPLOAD)}\n"
            f"🌳 {BotCommandText.with_description(BotCommandText.UPLOAD_R)}\n"
            f"💬 {BotCommandText.with_description(BotCommandText.DOWNLOAD_CHAT)}\n\n"
            f"✨ 新功能:\n"
            f"🌐 {BotCommandText.with_description(BotCommandText.WEB)}\n"
            f"🔒 {BotCommandText.with_description(BotCommandText.WEB_REVOKE)}\n"
            f"📦 {BotCommandText.with_description(BotCommandText.BATCH)}\n"
            f"📊 {BotCommandText.with_description(BotCommandText.STATUS)}\n"
            f"❌ {BotCommandText.with_description(BotCommandText.CANCEL)}\n"
            f"🗄️ {BotCommandText.with_description(BotCommandText.SETUP_REPOSITORY)}\n\n"
            f"✨ 其他功能:\n"
            f"📨 转发`视频`、`图片`、`音频`、`语音`、`GIF`、`文档`、`视频笔记`类型的消息给我,即可创建下载任务。\n"
        )

        if client is None or message is None:
            return {"keyboard": keyboard, "text": text}

        await client.send_message(
            chat_id=self._message_user_id(message),
            text=text,
            link_preview_options=LINK_PREVIEW_OPTIONS,
            reply_markup=keyboard,
        )
        return None

    async def start(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> None:
        """开始命令：委托给 help 方法。"""
        await self.help(client, message)

    async def table(
        self,
        client: Union[pyrogram.Client, None] = None,
        message: Union[pyrogram.types.Message, None] = None,
    ) -> Union[None, dict]:
        """表格命令：返回统计表选择键盘。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: 当 client 和 message 都为 None 时返回 dict
        """
        keyboard = KeyboardManager.build_table_keyboard()
        text: str = "🧐🧐🧐请选择输出「统计表」的类型:"
        if client is None or message is None:
            return {"keyboard": keyboard, "text": text}
        await client.send_message(
            chat_id=self._message_user_id(message),
            text=text,
            link_preview_options=LINK_PREVIEW_OPTIONS,
            reply_markup=keyboard,
        )
        return None

    # ==================== 下载命令 ====================

    async def get_download_link_from_bot(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        user_client: Optional[pyrogram.Client] = None,
        bot_client: Optional[pyrogram.Client] = None,
        with_upload: Union[dict, None] = None,
    ) -> Union[Dict[str, Union[set, pyrogram.types.Message]], None]:
        """解析下载链接命令。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :param user_client: 用户客户端（用于发送消息到 bot）
        :param bot_client: Bot 客户端
        :param with_upload: 上传配置
        :return: 解析结果字典或 None
        """
        text = self._message_text(message)
        user_id = self._message_user_id(message)
        if text == "/download":
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="⚠️⚠️⚠️请提供下载链接⚠️⚠️⚠️语法:\n`/download https://t.me/x/x`",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
        elif text.startswith("https://t.me/"):
            if text[len("https://t.me/") :].count("/") >= 1:
                try:
                    await client.delete_messages(
                        chat_id=user_id, message_ids=message.id
                    )
                    if user_client:
                        bot_username = (
                            getattr(await bot_client.get_me(), "username", None)
                            if bot_client
                            else None
                        )
                        if bot_username:
                            await user_client.send_message(
                                chat_id=bot_username,
                                text=f"/download {text}",
                                link_preview_options=LINK_PREVIEW_OPTIONS,
                            )
                except Exception as e:
                    await client.send_message(
                        chat_id=user_id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f"{e}\n⬇️⬇️⬇️请使用以下命令分配下载任务⬇️⬇️⬇️\n`/download {text}`",
                        link_preview_options=LINK_PREVIEW_OPTIONS,
                    )
            else:
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text="⬇️⬇️⬇️请使用以下命令分配下载任务⬇️⬇️⬇️\n`/download https://t.me/x/x`",
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                )
        elif (
            len(text) <= 25
            or text == "/download https://t.me/x/x"
            or text.endswith(".txt")
        ):
            await self.help(client, message)
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌链接错误❌❌❌\n请查看帮助后重试。",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
        else:
            link: list = text.split()
            link.remove("/download") if "/download" in link else None
            link = [_.rstrip("/") for _ in link]
            right_link: set = set()
            invalid_link: set = set()
            if (
                safe_index(link, 0, "").startswith("https://t.me/")
                and not safe_index(link, 1, "https://t.me/").startswith("https://t.me/")
                and len(link) == 3
            ):
                start_id: int = int(safe_index(link, 1, -1))
                end_id: int = int(safe_index(link, 2, -1))
                if not await ValidationHelper.check_download_range(
                    start_id=start_id, end_id=end_id, client=client, message=message
                ):
                    return None
                for i in range(start_id, end_id + 1):
                    right_link.add(f"{link[0]}/{i}?single")
            else:
                right_link = set([_ for _ in link if _.startswith("https://t.me/")])
                invalid_link = set(
                    [_ for _ in link if not _.startswith("https://t.me/")]
                )
            if right_link:
                return {
                    "right_link": right_link,
                    "invalid_link": invalid_link,
                    "last_bot_message": await MessageHelper.safe_process_message(
                        client=client,
                        message=message,
                        text=TextFormatter.update_text(
                            right_link=right_link,
                            invalid_link=invalid_link,
                        ),
                    ),
                }
            else:
                return None
        return None

    # ==================== 下载频道命令 ====================

    async def get_download_chat_link_from_bot(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        user_client: Optional[pyrogram.Client] = None,
    ) -> None:
        """解析下载频道命令。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :param user_client: 用户客户端
        """
        user_id = self._message_user_id(message)
        text = self._message_text(message)
        if BotCallbackText.DOWNLOAD_CHAT_ID != "download_chat_id":
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="⚠️⚠️⚠️请执行或取消上一次频道下载任务设置⚠️⚠️⚠️",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        if text == "/download_chat":
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="⚠️⚠️⚠️请提供下载链接⚠️⚠️⚠️语法:\n`/download_chat https://t.me/x/x`",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        command = text.split()
        if len(command) != 2:
            await self.help(client, message)
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌命令语法错误❌❌❌\n请查看帮助后重试。",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        chat_link = command[1]
        identifier_service = self._identifier_service
        if identifier_service is None:
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌Telegram 客户端未连接❌❌❌",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        try:
            resolved = await identifier_service.resolve(chat_link)
        except Exception as e:
            from module.core.identifier_service import IdentifierServiceError

            if isinstance(e, IdentifierServiceError):
                error_text = self._format_resolve_error(e)
            else:
                error_text = f"❌❌❌解析失败:{e}❌❌❌"
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=error_text,
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        chat_id = resolved.chat_id
        if self.state_manager.has_download_filter(str(chat_id)):
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f"⚠️⚠️⚠️该频道已在下载中⚠️⚠️⚠️\n{chat_link}",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        BotCallbackText.DOWNLOAD_CHAT_ID = str(chat_id)
        self.state_manager.create_download_filter(str(chat_id))
        log.info(
            f'"{BotCallbackText.DOWNLOAD_CHAT_ID}"已添加至{self.state_manager.download_chat_filter}。'
        )
        format_dtype = ",".join([_t(_) for _ in DownloadType()])
        include_comment = self.state_manager.get_download_filter(str(chat_id)).get(
            "comment", False
        )
        comment: str = "开" if include_comment else "关"
        await client.send_message(
            chat_id=user_id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text=f"💬下载频道:`{chat_id}`\n"
            f"⏮️当前选择的起始日期为:未定义\n"
            f"⏭️当前选择的结束日期为:未定义\n"
            f"📝当前选择的下载类型为:{format_dtype}\n"
            f"🔑当前匹配的关键词为:未定义\n"
            f"👥包含评论区:{comment}",
            reply_markup=KeyboardManager.build_download_chat_filter_keyboard(
                include_comment
            ),
            link_preview_options=LINK_PREVIEW_OPTIONS,
        )
        return None

    # ==================== 转发命令 ====================

    async def get_forward_link_from_bot(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> Union[Dict[str, Union[list, str]], None]:
        """解析转发命令。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: 解析结果字典或 None
        """
        text = self._message_text(message)
        user_id = self._message_user_id(message)
        args: list = text.split(maxsplit=5)
        if text == "/forward":
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌命令语法无效❌❌❌\n"
                "⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n"
                "`/forward 原始频道 目标频道 起始ID 结束ID`\n"
                "⬇️⬇️⬇️请使用⬇️⬇️⬇️\n"
                "`/forward https://t.me/A https://t.me/B 1 100`\n",
            )
            return None
        try:
            start_id: int = int(safe_index(args, 3, -1))
            end_id: int = int(safe_index(args, 4, -1))
            if not await ValidationHelper.check_download_range(
                start_id=start_id, end_id=end_id, client=client, message=message
            ):
                return None
        except Exception as e:
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f"❌❌❌命令错误❌❌❌\n{e}\n请使用`/forward https://t.me/A https://t.me/B 1 100`",
            )
            return None
        return {
            "origin_link": args[1],
            "target_link": args[2],
            "message_range": [start_id, end_id],
        }

    # ==================== 上传命令 ====================

    async def get_upload_link_from_bot(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        user_client: Optional[pyrogram.Client] = None,
        bot_client: Optional[pyrogram.Client] = None,
        last_message: Optional[pyrogram.types.Message] = None,
        delete: bool = False,
        save_directory: Optional[str] = None,
        recursion: bool = False,
        valid_link_cache: Optional[dict] = None,
    ) -> Union[Dict, None]:
        """解析上传命令。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :param user_client: 用户客户端
        :param bot_client: Bot 客户端
        :param last_message: 最后一条 bot 消息
        :param delete: 是否上传后删除
        :param save_directory: 保存目录
        :param recursion: 是否递归调用
        :param valid_link_cache: 有效链接缓存
        :return: 解析结果字典或 None
        """
        if not recursion:
            valid_link_cache = {}
        if valid_link_cache is None:
            valid_link_cache = {}

        text = self._message_text(message)
        user_id = self._message_user_id(message)
        if text == "/upload" or text == "/upload_r":
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="⚠️⚠️⚠️请提供参数⚠️⚠️⚠️语法:\n`/upload 本地文件 目标频道`或`/upload_r 本地文件夹 目标频道`",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None

        if text.startswith("/upload "):
            remaining_text = text[len("/upload ") :].strip()
            command = "/upload"
        elif text.startswith("/upload_r "):
            remaining_text = text[len("/upload_r ") :].strip()
            command = "/upload_r"
        else:
            return None

        parts = remaining_text.rsplit(maxsplit=1)

        if len(parts) == 2:
            file_path = parts[0]
            target_link = parts[1]
            if not recursion:
                if user_client is None:
                    return None
                if target_link not in valid_link_cache:
                    valid_link_cache[target_link] = await get_valid_chat_id(
                        link=target_link,
                        user_client=user_client,
                        bot_client=cast(pyrogram.Client, bot_client),
                        bot_message=cast(pyrogram.types.Message, last_message),
                        error_msg=f"⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}",
                    )
                if not valid_link_cache[target_link]:
                    return None
            if os.path.isdir(file_path):
                upload_folder = []
                if command == "/upload_r":
                    upload_files = [
                        os.path.join(root, filename)
                        for root, dirs, files in os.walk(file_path)
                        for filename in files
                    ]
                else:
                    upload_files = safe_scan_directory_file(file_path)
                for file_name in upload_files:
                    new_message = copy.copy(message)
                    new_message.text = (
                        f"/upload {os.path.join(file_path, file_name)} {target_link}"  # type: ignore
                    )
                    upload_folder.append(
                        self.get_upload_link_from_bot(
                            client=client,
                            message=new_message,
                            user_client=user_client,
                            bot_client=bot_client,
                            last_message=last_message,
                            delete=delete,
                            save_directory=save_directory,
                            recursion=True,
                            valid_link_cache=valid_link_cache,
                        )
                    )
                if upload_folder:
                    await client.send_message(
                        chat_id=user_id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f"📤📤📤上传任务已创建,请耐心等待📤📤📤\n`{file_path}`",
                        link_preview_options=LINK_PREVIEW_OPTIONS,
                    )
                    await asyncio.gather(*upload_folder)
                else:
                    await client.send_message(
                        chat_id=user_id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f"⚠️⚠️⚠️文件夹为空⚠️⚠️⚠️\n`{file_path}`",
                        link_preview_options=LINK_PREVIEW_OPTIONS,
                    )
                return None
            if not os.path.isfile(file_path):
                log.error(f'上传出错,{_t(KeyWord.REASON)}:"{file_path}"不存在。')
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f"⚠️⚠️⚠️上传文件不存在⚠️⚠️⚠️\n`{file_path}`",
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                )
                return None
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f"⚠️⚠️⚠️上传文件大小为0⚠️⚠️⚠️\n`{file_path}`",
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                )

            is_premium = (
                getattr(user_client.me, "is_premium", False) if user_client else False
            )
            if not is_allow_upload(file_size=file_size, is_premium=is_premium):
                from module.utils.stdio import (
                    MetaData,
                )  # lazy import to avoid parser side effects

                format_file_size: str = MetaData.suitable_unit_display(  # type: ignore[attr-defined]
                    file_size, unit="MiB", mebibyte=True
                )
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f"⚠️⚠️⚠️上传大小超过限制({format_file_size})⚠️⚠️⚠️\n"
                    f"`{file_path}`\n"
                    f"(普通用户2000MiB,会员用户4000MiB)",
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                )
            if not recursion:
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f"📤📤📤上传任务已创建,请耐心等待📤📤📤\n`{file_path}`",
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                )
            log.info(f'上传文件:"{file_path}",上传频道:"{target_link}"。')
            if target_link.startswith("https://t.me/") or target_link in ("me", "self"):
                return {
                    "target_link": target_link,
                    "valid_link_cache": valid_link_cache,
                    "upload_task": UploadTask(
                        chat_id=None,
                        file_path=file_path,
                        file_id=cast(int, user_client.rnd_id()) if user_client else 0,
                        file_size=os.path.getsize(file_path),
                        file_part=[],
                        status=UploadStatus.PENDING,
                    ),
                }
        if not recursion:
            await self.help(client, message)
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌命令错误❌❌❌\n请查看帮助后重试。",
                link_preview_options=LINK_PREVIEW_OPTIONS,
            )
            return None
        return None

    # ==================== 退出命令 ====================

    async def exit_bot(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> None:
        """退出命令：停止 Bot 并退出程序。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        """
        last_message = await client.send_message(
            chat_id=self._message_user_id(message),
            text="🚧已收到退出命令。",
            reply_parameters=ReplyParameters(message_id=message.id),
            link_preview_options=LINK_PREVIEW_OPTIONS,
        )
        await MessageHelper.safe_edit_message_text(
            client=client,
            message=message,
            last_message_id=last_message.id,
            text="✅退出成功。",
        )
        raise SystemExit(0)

    # ==================== 监听命令 ====================

    async def _resolve_link_to_chat_id(self, link: str) -> Optional[str]:
        """解析 link 为 chat_id 字符串，使用内部缓存避免重复请求。"""
        if link in self._resolved_chat_id_cache:
            return self._resolved_chat_id_cache[link]
        identifier_service = self._identifier_service
        if identifier_service is None:
            return None
        try:
            resolved = await identifier_service.resolve(link)
            chat_id = str(resolved.chat_id)
            self._resolved_chat_id_cache[link] = chat_id
            return chat_id
        except Exception:
            return None

    async def on_listen(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> None:
        """处理监听命令（/listen_download 和 /listen_forward）。

        新架构：直接调用 TaskManager.create_task() 创建 LISTEN_* 任务，
        不再返回 dict 给 downloader.py 处理后续注册。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        """
        text = self._message_text(message)
        user_id = self._message_user_id(message)
        args: list = text.split()
        if not args:
            return
        links: list = args[1:]

        # 获取 TaskManager
        task_manager = self._task_manager
        if task_manager is None:
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌任务管理器未初始化❌❌❌",
            )
            return

        if text.startswith("/listen_download"):
            if len(args) == 1:
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text="❌❌❌命令语法错误❌❌❌\n"
                    "⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n"
                    "`/listen_download 监听频道1 监听频道2 监听频道n`\n"
                    "⬇️⬇️⬇️请使用⬇️⬇️⬇️\n"
                    "`/listen_download https://t.me/A https://t.me/B https://t.me/n`\n",
                )
                return

            links = list(dict.fromkeys(links))  # 去重
            created_tasks: list[str] = []
            failed_links: list[tuple[str, str]] = []  # (link, reason)

            for link in links:
                try:
                    task = await task_manager.create_task(
                        task_type=TaskType.LISTEN_DOWNLOAD,
                        params={"source_identifier": link},
                    )
                    created_tasks.append(task.task_id)
                except Exception as exc:
                    from module.core.task.manager import TaskConflictError

                    if isinstance(exc, TaskConflictError):
                        failed_links.append((link, "该频道已有监听任务"))
                    else:
                        failed_links.append((link, str(exc)))

            # 发送结果消息
            if created_tasks:
                success_text = "✅ 监听下载任务已创建:\n"
                for task_id in created_tasks:
                    task_obj = await task_manager.get_task(task_id)
                    chat_info = f"chat_id={task_obj.chat_id}" if task_obj else ""
                    success_text += f"📥 `{task_id[:8]}...` ({chat_info})\n"

                if failed_links:
                    success_text += "\n❌ 以下链接创建失败:\n"
                    for link, reason in failed_links:
                        success_text += f"• {link}: {reason}\n"

                # 发送取消按钮
                from pyrogram.types.bots_and_keyboards import (
                    InlineKeyboardButton,
                    InlineKeyboardMarkup,
                )

                buttons = []
                for task_id in created_tasks:
                    buttons.append(
                        [
                            InlineKeyboardButton(
                                f"❌ 取消 {task_id[:8]}...",
                                callback_data=f"{BotCallbackText.REMOVE_LISTEN_DOWNLOAD}_{task_id}",
                            )
                        ]
                    )

                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=success_text,
                    reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
                )
            elif failed_links:
                error_text = "❌❌❌所有链接创建失败❌❌❌\n"
                for link, reason in failed_links:
                    error_text += f"• {link}: {reason}\n"
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=error_text,
                )

        elif text.startswith("/listen_forward"):
            e: str = ""
            len_args: int = len(args)
            if len_args != 3:
                if len_args == 1:
                    e = "命令缺少监听频道与转发频道"
                elif len_args == 2:
                    e = "命令缺少转发频道"
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f"❌❌❌{e}❌❌❌\n"
                    "⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n"
                    f"`/listen_forward 监听频道 转发频道`\n"
                    "⬇️⬇️⬇️请使用⬇️⬇️⬇️\n"
                    f"`/listen_forward https://t.me/A https://t.me/B`\n",
                )
                return
            listen_link: str = args[1]
            target_link: str = args[2]

            try:
                # 解析目标频道
                identifier_service = self._identifier_service
                if identifier_service is None:
                    await client.send_message(
                        chat_id=user_id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text="❌❌❌Telegram 客户端未连接❌❌❌",
                    )
                    return
                target_resolved = await identifier_service.resolve(target_link)
                target_chat_id = target_resolved.chat_id

                task = await task_manager.create_task(
                    task_type=TaskType.LISTEN_FORWARD,
                    params={
                        "source_identifier": listen_link,
                        "target_identifier": target_link,
                        "target_chat_id": target_chat_id,
                    },
                )

                from pyrogram.types.bots_and_keyboards import (
                    InlineKeyboardButton,
                    InlineKeyboardMarkup,
                )

                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f"✅ 监听转发任务已创建:\n"
                    f"📥 `{task.task_id[:8]}...`\n"
                    f"📤 {listen_link} ➡️ {target_link}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ 取消",
                                    callback_data=f"{BotCallbackText.REMOVE_LISTEN_FORWARD}_{task.task_id}",
                                )
                            ]
                        ]
                    ),
                )
            except Exception as exc:
                from module.core.task.manager import TaskConflictError
                from module.core.identifier_service import IdentifierServiceError

                if isinstance(exc, TaskConflictError):
                    error_text = f"❌ 该频道已有监听任务: {listen_link}"
                elif isinstance(exc, IdentifierServiceError):
                    error_text = self._format_resolve_error(exc)
                else:
                    error_text = f"❌❌❌创建监听转发任务失败:{exc}❌❌❌"
                await client.send_message(
                    chat_id=user_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=error_text,
                )

    async def listen_info(
        self, client: pyrogram.Client, message: pyrogram.types.Message
    ) -> None:
        """监听信息命令：显示当前监听状态。

        新架构：从 TaskManager 查询 LISTEN_* 任务替代遍历 StateManager 内存字典。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        """
        user_id = self._message_user_id(message)

        # 获取 TaskManager
        task_manager = self._task_manager
        if task_manager is None:
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text="❌❌❌任务管理器未初始化❌❌❌",
            )
            return

        # 查询监听下载任务
        listen_download_tasks, _ = await task_manager.list_tasks(
            task_type=TaskType.LISTEN_DOWNLOAD, status=TaskStatus.RUNNING
        )
        # 查询监听转发任务
        listen_forward_tasks, _ = await task_manager.list_tasks(
            task_type=TaskType.LISTEN_FORWARD, status=TaskStatus.RUNNING
        )

        if not listen_download_tasks and not listen_forward_tasks:
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=LINK_PREVIEW_OPTIONS,
                text="😲目前没有正在监听的频道。",
            )
            return

        if listen_download_tasks:
            text = "🕵️以下为正在监听下载的任务:\n"
            for task in listen_download_tasks:
                source_identifier = task.params.get("source_identifier", "未知")
                text += f"• {source_identifier} (task_id: `{task.task_id[:8]}...`)\n"
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=LINK_PREVIEW_OPTIONS,
                text=text,
            )

        if listen_forward_tasks:
            text = "📲以下为正在监听转发的任务:\n"
            for task in listen_forward_tasks:
                source = task.params.get("source_identifier", "未知")
                target = task.params.get("target_identifier", "未知")
                text += f"• {source} ➡️ {target} (task_id: `{task.task_id[:8]}...`)\n"
            await client.send_message(
                chat_id=user_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=LINK_PREVIEW_OPTIONS,
                text=text,
            )

    # ==================== 关键词输入处理 ====================

    async def handle_keyword_input(
        self,
        chat_id: Union[str, int],
        callback_query: CallbackQuery,
        callback_prompt: Callable,
        _client: pyrogram.Client,
        message: pyrogram.types.Message,
    ) -> None:
        """处理用户输入的关键词。

        :param chat_id: 频道 ID
        :param callback_query: 回调查询
        :param callback_prompt: 回调提示函数
        :param _client: Pyrogram 客户端
        :param message: 用户消息
        """
        text = self._message_text(message).strip()

        if not text:
            return None

        query_message = callback_query.message
        if query_message is None:
            return None

        keywords = [kw.strip() for kw in text.split() if kw.strip()]
        for keyword in keywords:
            if self.state_manager.has_added_keyword(keyword):
                try:
                    await query_message.edit_text(
                        text=f"🚛`{keyword}`已被添加,选择处理方式后继续。",
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        BotButton.DROP,
                                        callback_data=f"{BotCallbackText.DROP_KEYWORD}_{keyword}",
                                    ),
                                    InlineKeyboardButton(
                                        BotButton.IGNORE,
                                        callback_data=f"{BotCallbackText.IGNORE_KEYWORD}_{keyword}",
                                    ),
                                ]
                            ]
                        ),
                    )
                    return None
                except MessageNotModified:
                    pass
            else:
                self.state_manager.add_keyword(str(chat_id), keyword)
                try:
                    await query_message.edit_text(
                        text=callback_prompt(),
                        reply_markup=KeyboardManager.build_keyword_filter_keyboard(
                            self.state_manager.adding_keywords
                        ),
                    )
                except MessageNotModified:
                    pass

    async def process_error_message(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        keyword_handler: Union[MessageHandler, None] = None,
    ) -> None:
        """处理未知命令/错误消息。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :param keyword_handler: 关键词输入处理器（如果存在则跳过）
        """
        if keyword_handler:
            return

        # 记录未知命令日志
        user = message.from_user
        user_id = self._message_user_id(message)
        user_name = user.username if user is not None else user_id
        command_text = message.text[:50] if message.text else "None"
        log.warning(f"未知命令 - 用户: {user_name}, 命令: {command_text}")

        await self.help(client, message)
        await client.send_message(
            chat_id=user_id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text="⚠️⚠️⚠️未知命令⚠️⚠️⚠️\n请查看帮助后重试。",
            link_preview_options=LINK_PREVIEW_OPTIONS,
        )

    # ==================== 关键词模式管理 ====================

    @staticmethod
    def add_keyword_mode_handler(
        add_handler_fn: Callable,
        remove_handler_fn: Callable,
        root: list,
        chat_id,
        callback_query: CallbackQuery,
        callback_prompt: Callable,
        handle_keyword_fn: Callable,
        enable: bool,
    ) -> Union[MessageHandler, None]:
        """添加或移除关键词输入模式的 handler。

        :param add_handler_fn: 添加 handler 的函数
        :param remove_handler_fn: 移除 handler 的函数
        :param root: 根用户 ID 列表
        :param chat_id: 频道 ID
        :param callback_query: 回调查询
        :param callback_prompt: 回调提示函数
        :param handle_keyword_fn: 关键词处理函数
        :param enable: 是否启用
        :return: 创建的 handler 或 None
        """
        if enable:
            keyword_handler = MessageHandler(
                partial(handle_keyword_fn, chat_id, callback_query, callback_prompt),
                filters=pyrogram.filters.user(root)
                & pyrogram.filters.text
                & (
                    lambda client, m: (
                        isinstance(m, pyrogram.types.Message)
                        and m.text
                        and m.text.strip()
                        and not m.text.startswith("/")
                        and not m.text.startswith("http")
                    )
                ),
            )
            add_handler_fn(keyword_handler, group=-1)
            log.info(f'用户输入模式已打开,Handler:"{keyword_handler}"。')
            return keyword_handler
        else:
            remove_handler_fn(None, group=-1)
            log.info("用户输入模式已关闭,Handler已清空。")
            return None

    # ==================== 回调数据处理 ====================

    @staticmethod
    async def callback_data(
        client: pyrogram.Client, callback_query: CallbackQuery
    ) -> Union[str, None]:
        """处理回调数据。

        :param client: Pyrogram 客户端
        :param callback_query: 回调查询
        :return: 回调数据字符串或 None
        """
        await callback_query.answer()
        data = callback_query.data
        if not data:
            return None
        if isinstance(data, str):
            return data
        return None

    async def handle_remove_listen_callback(
        self,
        client: pyrogram.Client,
        callback_query: CallbackQuery,
    ) -> bool:
        """处理 REMOVE_LISTEN_* 回调：取消监听任务。

        解析 callback_data 中的 task_id（格式: rld_{task_id} 或 rlf_{task_id}），
        调用 TaskExecutor.cancel_listen_task() 取消监听。

        :param client: Pyrogram 客户端
        :param callback_query: 回调查询
        :return: 是否成功处理（True=已处理，False=不匹配的回调格式）
        """
        await callback_query.answer()
        data = callback_query.data
        if not isinstance(data, str):
            return False

        # 解析新格式: rld_{task_id} 或 rlf_{task_id}
        task_id: str | None = None
        if data.startswith(BotCallbackText.REMOVE_LISTEN_DOWNLOAD + "_"):
            task_id = data[len(BotCallbackText.REMOVE_LISTEN_DOWNLOAD) + 1 :]
        elif data.startswith(BotCallbackText.REMOVE_LISTEN_FORWARD + "_"):
            task_id = data[len(BotCallbackText.REMOVE_LISTEN_FORWARD) + 1 :]

        if not task_id:
            return False

        # 调用 TaskExecutor 取消监听
        executor = self._task_executor
        if executor:
            try:
                await executor.cancel_listen_task(task_id)
            except Exception as e:
                log.error(f"取消监听任务 {task_id} 失败: {e}")

        # 编辑消息显示已取消
        if callback_query.message:
            try:
                await callback_query.message.edit_text("❌ 监听任务已取消")
            except MessageNotModified:
                pass

        return True
