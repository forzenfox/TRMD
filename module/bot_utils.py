# coding=UTF-8
"""Bot 工具方法模块。

从 module/bot.py 中提取的通用工具方法，包括：
- MessageHelper: 消息发送和编辑的安全包装
- TextFormatter: 文本格式化工具
- ValidationHelper: 输入验证工具
- LinkHelper: 链接解析工具
"""

import asyncio
from typing import Union, List, Optional

import pyrogram
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.errors import FloodWait, FloodPremiumWait
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified
from pyrogram.types.bots_and_keyboards import InlineKeyboardMarkup

from module import console, log, LINK_PREVIEW_OPTIONS
from module.language import _t
from module.enums import KeyWord, BotMessage


class MessageHelper:
    """消息助手：提供消息发送和编辑的安全包装方法。"""

    @staticmethod
    async def safe_process_message(
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            text: Union[str, List[str]],
            last_message_id: int = -1,
            reply_markup: Union[InlineKeyboardMarkup, None] = None
    ) -> pyrogram.types.Message:
        """安全发送消息。如果只有一条文本且有 last_message_id，则编辑消息而非发送新消息。

        :param client: Pyrogram 客户端
        :param message: 原始消息
        :param text: 要发送的文本，可以是字符串或字符串列表
        :param last_message_id: 上一次消息的 ID，用于编辑而不是发送新消息
        :param reply_markup: 内联键盘标记
        :return: 发送或编辑后的消息对象
        """
        if isinstance(text, list) and len(text) == 1 and last_message_id != -1:
            return await client.edit_message_text(
                chat_id=message.from_user.id,
                message_id=last_message_id,
                text=text[0],
                link_preview_options=LINK_PREVIEW_OPTIONS,
                reply_markup=reply_markup
            )

        last_bot_messages: list = []
        texts = text if isinstance(text, list) else [text]
        for t in texts:
            last_bot_message: pyrogram.types.Message = await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=t, link_preview_options=LINK_PREVIEW_OPTIONS
            )
            if last_bot_message not in last_bot_messages:
                last_bot_messages.append(last_bot_message)
        return last_bot_messages[-1]

    @staticmethod
    async def safe_edit_message_text(
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            last_message_id: int,
            text: str,
            reply_markup: Union[InlineKeyboardMarkup, None] = None
    ) -> Union[pyrogram.types.Message, None]:
        """安全编辑消息，处理 FloodWait 等异常。

        :param client: Pyrogram 客户端
        :param message: 原始消息
        :param last_message_id: 要编辑的消息 ID
        :param text: 新的文本内容
        :param reply_markup: 内联键盘标记
        :return: 编辑后的消息，或 None（未修改时）
        """
        while True:
            try:
                await client.edit_message_text(
                    chat_id=message.from_user.id,
                    message_id=last_message_id,
                    text=text,
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                    reply_markup=reply_markup
                )
                return None
            except MessageNotModified:
                return None
            except (FloodWait, FloodPremiumWait) as e:
                amount = e.value
                console.log(
                    f'[{client.name}]编辑消息请求频繁,要求等待{amount}秒后继续运行。',
                    style='#FF4689'
                )
                await asyncio.sleep(amount)
            except Exception:
                raise

    @staticmethod
    async def safe_edit_message(
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            last_message_id: int,
            text: Union[str, List[str]],
            reply_markup: Union[InlineKeyboardMarkup, None] = None
    ) -> Union[pyrogram.types.Message, None]:
        """安全编辑消息，支持字符串列表。

        :param client: Pyrogram 客户端
        :param message: 原始消息
        :param last_message_id: 要编辑的消息 ID
        :param text: 新的文本内容（字符串或字符串列表）
        :param reply_markup: 内联键盘标记
        :return: 消息对象或 None
        """
        if isinstance(text, list):
            return await MessageHelper.safe_process_message(
                client=client,
                message=message,
                last_message_id=last_message_id,
                text=text,
                reply_markup=reply_markup
            )
        elif isinstance(text, str):
            return await MessageHelper.safe_edit_message_text(
                client=client,
                message=message,
                last_message_id=last_message_id,
                text=text,
                reply_markup=reply_markup
            )


class TextFormatter:
    """文本格式化器：提供文本格式化的工具方法。"""

    @staticmethod
    def update_text(
            right_link: set,
            invalid_link: set,
            exist_link: Union[set, None] = None
    ) -> list:
        """格式化下载结果文本。

        :param right_link: 有效的链接集合
        :param invalid_link: 无效的链接集合
        :param exist_link: 已存在的链接集合
        :return: 格式化后的文本列表
        """
        from module.util import safe_message  # lazy import to avoid parser side effects
        n = '\n'
        right_msg = f'{BotMessage.RIGHT}{n.join(sorted(right_link))}' if right_link else ''
        invalid_msg = (
            f'{BotMessage.INVALID}{n.join(sorted(invalid_link))}'
            f'{n}(具体原因请前往终端查看报错信息)'
        ) if invalid_link else ''
        if exist_link:
            exist_msg = f'{BotMessage.EXIST}{n.join(sorted(exist_link))}' if exist_link else ''
            text: str = right_msg + n + exist_msg + n + invalid_msg
        else:
            text = right_msg + n + invalid_msg
        return safe_message(text)


class ValidationHelper:
    """验证助手：提供各种输入验证的工具方法。"""

    @staticmethod
    async def check_download_range(
            start_id: int,
            end_id: int,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> bool:
        """验证下载范围是否有效。

        :param start_id: 起始 ID
        :param end_id: 结束 ID
        :param client: Pyrogram 客户端
        :param message: 原始消息
        :return: 验证是否通过
        """
        if end_id != -1:
            if start_id > end_id:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='❌❌❌起始ID>结束ID❌❌❌'
                )
                return False
        if start_id == -1 or end_id == -1:
            text: str = '未知错误'
            if start_id == -1:
                text: str = '没有指定起始ID'
            if end_id == -1:
                text: str = '没有指定结束ID'
            if start_id == end_id:
                text: str = '没有指定起始ID和结束ID'
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f'❌❌❌{text}❌❌❌'
            )
            return False
        return True


class LinkHelper:
    """链接助手：提供链接解析和处理的工具方法。"""

    @staticmethod
    def parse_download_links(text: str) -> dict:
        """解析下载命令中的链接。

        :param text: 命令文本
        :return: 解析结果字典，包含 links、is_range、start_id、end_id
        """
        link: list = text.split()
        link.remove('/download') if '/download' in link else None
        link = [_.rstrip('/') for _ in link]
        return {
            'links': link,
            'is_range': (
                    len(link) == 3
                    and link[0].startswith('https://t.me/')
                    and not link[1].startswith('https://t.me/')
            )
        }

    @staticmethod
    def extract_range_links(base_link: str, start_id: int, end_id: int) -> set:
        """提取范围下载链接。

        :param base_link: 基础链接
        :param start_id: 起始 ID
        :param end_id: 结束 ID
        :return: 链接集合
        """
        right_link: set = set()
        for i in range(start_id, end_id + 1):
            right_link.add(f'{base_link}/{i}?single')
        return right_link