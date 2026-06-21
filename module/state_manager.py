# coding=UTF-8
"""Bot 状态管理模块。

从 module/bot.py 中提取的状态管理逻辑，包括：
- 监听频道状态（下载/转发）
- 下载过滤器状态
- 关键词管理
- 媒体组处理状态
"""

from typing import Union, Optional

import pyrogram
from pyrogram.handlers import MessageHandler

from module.enums import DownloadType


class StateManager:
    """Bot 状态管理器：集中管理 Bot 运行时的各种状态数据。

    将原本分散在 Bot 类中的多个 dict/list 属性集中管理，
    提供统一的状态读写接口，便于测试和维护。
    """

    def __init__(self):
        # 监听频道状态
        self.listen_download_chat: dict = {}
        self.listen_forward_chat: dict = {}

        # 媒体组处理状态
        self.handle_media_groups: dict = {}

        # 下载频道过滤器状态
        self.download_chat_filter: dict = {}

        # 关键词管理状态
        self.adding_keywords: list = []
        self.keyword_handler: Union[MessageHandler, None] = None

    # ==================== 监听状态管理 ====================

    def add_listen_download(self, chat_id: str, link: str) -> None:
        """添加下载监听。

        :param chat_id: 频道 ID
        :param link: 频道链接
        """
        self.listen_download_chat[chat_id] = link

    def remove_listen_download(self, chat_id: str) -> None:
        """移除下载监听。

        :param chat_id: 频道 ID
        """
        self.listen_download_chat.pop(chat_id, None)

    def has_listen_download(self, chat_id: str) -> bool:
        """检查是否存在下载监听。

        :param chat_id: 频道 ID
        :return: 是否存在
        """
        return chat_id in self.listen_download_chat

    def add_listen_forward(self, meta_key: str) -> None:
        """添加转发监听。

        :param meta_key: 监听+转发链接的组合键
        """
        self.listen_forward_chat[meta_key] = True

    def remove_listen_forward(self, meta_key: str) -> None:
        """移除转发监听。

        :param meta_key: 监听+转发链接的组合键
        """
        self.listen_forward_chat.pop(meta_key, None)

    def has_listen_forward(self, meta_key: str) -> bool:
        """检查是否存在转发监听。

        :param meta_key: 监听+转发链接的组合键
        :return: 是否存在
        """
        return meta_key in self.listen_forward_chat

    def has_any_listen(self) -> bool:
        """检查是否有任何监听。

        :return: 是否有监听
        """
        return bool(self.listen_download_chat or self.listen_forward_chat)

    # ==================== 下载频道过滤器管理 ====================

    def create_download_filter(self, chat_id: str) -> dict:
        """为指定频道创建下载过滤器。

        :param chat_id: 频道 ID
        :return: 创建的过滤器配置字典
        """
        self.download_chat_filter[chat_id] = {
            'date_range': {
                'start_date': None,
                'end_date': None,
                'adjust_step': 1
            },
            'download_type': {
                'video': True,
                'photo': True,
                'document': True,
                'audio': True,
                'voice': True,
                'animation': True,
                'video_note': True
            },
            'keyword': {},
            'title': {},
            'comment': False
        }
        return self.download_chat_filter[chat_id]

    def get_download_filter(self, chat_id: str) -> dict:
        """获取指定频道的下载过滤器。

        :param chat_id: 频道 ID
        :return: 过滤器配置字典，不存在时返回空字典
        """
        return self.download_chat_filter.get(chat_id, {})

    def update_download_filter(self, chat_id: str, key: str, value) -> None:
        """更新下载过滤器的某个字段。

        :param chat_id: 频道 ID
        :param key: 字段名
        :param value: 字段值
        """
        if chat_id in self.download_chat_filter:
            self.download_chat_filter[chat_id][key] = value

    def remove_download_filter(self, chat_id: str) -> None:
        """移除下载过滤器。

        :param chat_id: 频道 ID
        """
        self.download_chat_filter.pop(chat_id, None)

    def has_download_filter(self, chat_id: str) -> bool:
        """检查是否存在下载过滤器。

        :param chat_id: 频道 ID
        :return: 是否存在
        """
        return chat_id in self.download_chat_filter

    def toggle_download_chat_type(self, chat_id: str, dtype: DownloadType) -> bool:
        """切换下载类型过滤器的开关状态。

        :param chat_id: 频道 ID
        :param dtype: 下载类型
        :return: 切换后的状态
        """
        if chat_id in self.download_chat_filter:
            if 'download_type' in self.download_chat_filter[chat_id]:
                current = self.download_chat_filter[chat_id]['download_type']
                current[dtype] = not current.get(dtype, True)
                return current[dtype]
        return False

    def toggle_download_chat_comment(self, chat_id: str) -> bool:
        """切换评论区下载的开关状态。

        :param chat_id: 频道 ID
        :return: 切换后的状态
        """
        if chat_id in self.download_chat_filter:
            current = self.download_chat_filter[chat_id].get('comment', False)
            self.download_chat_filter[chat_id]['comment'] = not current
            return not current
        return False

    # ==================== 关键词管理 ====================

    def add_keyword(self, chat_id: str, keyword: str) -> None:
        """添加关键词到下载过滤器。

        :param chat_id: 频道 ID
        :param keyword: 关键词
        """
        if chat_id in self.download_chat_filter:
            if 'keyword' not in self.download_chat_filter[chat_id]:
                self.download_chat_filter[chat_id]['keyword'] = {}
            self.download_chat_filter[chat_id]['keyword'][keyword] = True
        if keyword not in self.adding_keywords:
            self.adding_keywords.append(keyword)

    def remove_keyword(self, chat_id: str, keyword: str) -> None:
        """从下载过滤器中移除关键词。

        :param chat_id: 频道 ID
        :param keyword: 关键词
        """
        if chat_id in self.download_chat_filter:
            if 'keyword' in self.download_chat_filter[chat_id]:
                self.download_chat_filter[chat_id]['keyword'].pop(keyword, None)
        if keyword in self.adding_keywords:
            self.adding_keywords.remove(keyword)

    def get_keywords(self, chat_id: str) -> dict:
        """获取指定频道的关键词字典。

        :param chat_id: 频道 ID
        :return: 关键词字典
        """
        if chat_id in self.download_chat_filter:
            return self.download_chat_filter[chat_id].get('keyword', {})
        return {}

    def reset_adding_keywords(self) -> None:
        """重置正在添加的关键词列表。"""
        self.adding_keywords.clear()

    def has_added_keyword(self, keyword: str) -> bool:
        """检查关键词是否已在添加列表中。

        :param keyword: 关键词
        :return: 是否已添加
        """
        return keyword in self.adding_keywords

    # ==================== 关键词输入模式管理 ====================

    def set_keyword_handler(self, handler: MessageHandler) -> None:
        """设置关键词输入处理器。

        :param handler: MessageHandler 实例
        """
        self.keyword_handler = handler

    def get_keyword_handler(self) -> Union[MessageHandler, None]:
        """获取关键词输入处理器。

        :return: MessageHandler 实例或 None
        """
        return self.keyword_handler

    def clear_keyword_handler(self) -> None:
        """清除关键词输入处理器。"""
        self.keyword_handler = None

    def has_keyword_handler(self) -> bool:
        """检查是否存在关键词输入处理器。

        :return: 是否存在
        """
        return self.keyword_handler is not None

    # ==================== 媒体组管理 ====================

    def add_media_group(self, group_id: str, messages: list) -> None:
        """添加媒体组消息。

        :param group_id: 媒体组 ID
        :param messages: 消息列表
        """
        self.handle_media_groups[group_id] = messages

    def get_media_group(self, group_id: str) -> Union[list, None]:
        """获取媒体组消息。

        :param group_id: 媒体组 ID
        :return: 消息列表或 None
        """
        return self.handle_media_groups.get(group_id)

    def remove_media_group(self, group_id: str) -> None:
        """移除媒体组。

        :param group_id: 媒体组 ID
        """
        self.handle_media_groups.pop(group_id, None)

    def has_media_group(self, group_id: str) -> bool:
        """检查是否存在媒体组。

        :param group_id: 媒体组 ID
        :return: 是否存在
        """
        return group_id in self.handle_media_groups

    # ==================== 日期范围管理 ====================

    def set_download_date(self, chat_id: str, date_type: str, date_value: str) -> None:
        """设置下载日期范围。

        :param chat_id: 频道 ID
        :param date_type: 'start' 或 'end'
        :param date_value: 日期字符串
        """
        if chat_id in self.download_chat_filter:
            key = f'{date_type}_date'
            if 'date_range' in self.download_chat_filter[chat_id]:
                self.download_chat_filter[chat_id]['date_range'][key] = date_value

    def get_download_date(self, chat_id: str, date_type: str) -> Optional[str]:
        """获取下载日期范围。

        :param chat_id: 频道 ID
        :param date_type: 'start' 或 'end'
        :return: 日期字符串或 None
        """
        if chat_id in self.download_chat_filter:
            key = f'{date_type}_date'
            return self.download_chat_filter[chat_id].get('date_range', {}).get(key)
        return None

    def set_adjust_step(self, chat_id: str, step: int) -> None:
        """设置日期调整步进值。

        :param chat_id: 频道 ID
        :param step: 步进值
        """
        if chat_id in self.download_chat_filter:
            if 'date_range' in self.download_chat_filter[chat_id]:
                self.download_chat_filter[chat_id]['date_range']['adjust_step'] = step

    def get_adjust_step(self, chat_id: str) -> int:
        """获取日期调整步进值。

        :param chat_id: 频道 ID
        :return: 步进值
        """
        if chat_id in self.download_chat_filter:
            return self.download_chat_filter[chat_id].get('date_range', {}).get('adjust_step', 1)
        return 1