# coding=UTF-8
"""状态管理器单元测试。

测试 module/state_manager.py 中的 StateManager 类：
- 监听频道状态管理
- 下载过滤器管理
- 关键词管理
- 关键词输入模式管理
- 媒体组管理
- 日期范围管理
"""

import pytest
from unittest.mock import MagicMock

from module.bot.state_manager import StateManager
from module.core.enums import DownloadType


# ==================== Fixtures ====================


@pytest.fixture
def state():
    """提供 StateManager 实例。"""
    return StateManager()


@pytest.fixture
def state_with_filter(state):
    """提供已创建过滤器的 StateManager 实例。"""
    state.create_download_filter("channel_123")
    return state


# ==================== 下载过滤器管理测试 ====================


class TestDownloadFilter:
    """下载过滤器管理测试。"""

    def test_create_download_filter(self, state):
        """应能创建下载过滤器。"""
        result = state.create_download_filter("channel_123")
        assert isinstance(result, dict)
        assert "date_range" in result
        assert "download_type" in result
        assert "keyword" in result
        assert "title" in result
        assert "comment" in result

    def test_get_download_filter_exists(self, state_with_filter):
        """应能获取存在的过滤器。"""
        result = state_with_filter.get_download_filter("channel_123")
        assert result is not None
        assert result["comment"] is False

    def test_get_download_filter_not_exists(self, state):
        """不存在的过滤器应返回空字典。"""
        result = state.get_download_filter("nonexistent")
        assert result == {}

    def test_update_download_filter(self, state_with_filter):
        """应能更新过滤器字段。"""
        state_with_filter.update_download_filter("channel_123", "comment", True)
        result = state_with_filter.get_download_filter("channel_123")
        assert result["comment"] is True

    def test_remove_download_filter(self, state_with_filter):
        """应能移除过滤器。"""
        state_with_filter.remove_download_filter("channel_123")
        assert state_with_filter.has_download_filter("channel_123") is False

    def test_has_download_filter(self, state_with_filter):
        """存在的过滤器应返回 True。"""
        assert state_with_filter.has_download_filter("channel_123") is True

    def test_has_download_filter_not_exists(self, state):
        """不存在的过滤器应返回 False。"""
        assert state.has_download_filter("nonexistent") is False

    def test_toggle_download_chat_type(self, state_with_filter):
        """应能切换下载类型开关。"""
        result = state_with_filter.toggle_download_chat_type(
            "channel_123", DownloadType.VIDEO
        )
        assert result is False  # 从 True 切换到 False
        dtype = state_with_filter.get_download_filter("channel_123")["download_type"]
        assert dtype["video"] is False

    def test_toggle_download_chat_comment(self, state_with_filter):
        """应能切换评论区下载开关。"""
        result = state_with_filter.toggle_download_chat_comment("channel_123")
        assert result is True  # 从 False 切换到 True
        assert state_with_filter.get_download_filter("channel_123")["comment"] is True

    def test_toggle_download_chat_comment_twice(self, state_with_filter):
        """重复切换应恢复原值。"""
        state_with_filter.toggle_download_chat_comment("channel_123")  # False -> True
        result = state_with_filter.toggle_download_chat_comment(
            "channel_123"
        )  # True -> False
        assert result is False

    def test_update_download_filter_nonexistent(self, state):
        """更新不存在的过滤器不应报错。"""
        state.update_download_filter("nonexistent", "comment", True)  # should not raise


# ==================== 关键词管理测试 ====================


class TestKeywordManagement:
    """关键词管理测试。"""

    def test_add_keyword(self, state_with_filter):
        """应能添加关键词。"""
        state_with_filter.add_keyword("channel_123", "test_keyword")
        keywords = state_with_filter.get_keywords("channel_123")
        assert "test_keyword" in keywords

    def test_add_keyword_tracks_in_list(self, state_with_filter):
        """添加关键词时应同步添加到 adding_keywords 列表。"""
        state_with_filter.add_keyword("channel_123", "kw1")
        assert "kw1" in state_with_filter.adding_keywords

    def test_remove_keyword(self, state_with_filter):
        """应能移除关键词。"""
        state_with_filter.add_keyword("channel_123", "test_keyword")
        state_with_filter.remove_keyword("channel_123", "test_keyword")
        keywords = state_with_filter.get_keywords("channel_123")
        assert "test_keyword" not in keywords

    def test_remove_keyword_removes_from_list(self, state_with_filter):
        """移除关键词时应同步移除 adding_keywords 中的记录。"""
        state_with_filter.add_keyword("channel_123", "kw1")
        state_with_filter.remove_keyword("channel_123", "kw1")
        assert "kw1" not in state_with_filter.adding_keywords

    def test_get_keywords_empty(self, state_with_filter):
        """未添加关键词时返回空字典。"""
        assert state_with_filter.get_keywords("channel_123") == {}

    def test_get_keywords_nonexistent(self, state):
        """不存在的频道返回空字典。"""
        assert state.get_keywords("nonexistent") == {}

    def test_add_multiple_keywords(self, state_with_filter):
        """应能添加多个关键词。"""
        state_with_filter.add_keyword("channel_123", "kw1")
        state_with_filter.add_keyword("channel_123", "kw2")
        keywords = state_with_filter.get_keywords("channel_123")
        assert len(keywords) == 2

    def test_has_added_keyword(self, state_with_filter):
        """检查关键词是否在添加列表。"""
        state_with_filter.add_keyword("channel_123", "kw1")
        assert state_with_filter.has_added_keyword("kw1") is True
        assert state_with_filter.has_added_keyword("not_added") is False

    def test_reset_adding_keywords(self, state_with_filter):
        """应能重置正在添加的关键词列表。"""
        state_with_filter.add_keyword("channel_123", "kw1")
        state_with_filter.add_keyword("channel_123", "kw2")
        state_with_filter.reset_adding_keywords()
        assert len(state_with_filter.adding_keywords) == 0


# ==================== 关键词输入模式测试 ====================


class TestKeywordHandler:
    """关键词输入模式管理测试。"""

    def test_set_and_get_keyword_handler(self, state):
        """应能设置和获取关键词输入处理器。"""
        handler = object()  # 模拟 handler
        state.set_keyword_handler(handler)
        assert state.get_keyword_handler() is handler

    def test_clear_keyword_handler(self, state):
        """应能清除关键词输入处理器。"""
        state.set_keyword_handler(object())
        state.clear_keyword_handler()
        assert state.get_keyword_handler() is None

    def test_has_keyword_handler(self, state):
        """存在处理器时应返回 True。"""
        state.set_keyword_handler(object())
        assert state.has_keyword_handler() is True
        state.clear_keyword_handler()
        assert state.has_keyword_handler() is False


# ==================== 媒体组管理测试 ====================


class TestMediaGroup:
    """媒体组管理测试。"""

    def test_add_media_group(self, state):
        """应能添加媒体组。"""
        messages = [MagicMock(id=1), MagicMock(id=2)]
        state.add_media_group("group_1", messages)
        assert state.has_media_group("group_1") is True

    def test_get_media_group(self, state):
        """应能获取媒体组消息。"""
        messages = [MagicMock(id=1)]
        state.add_media_group("group_1", messages)
        result = state.get_media_group("group_1")
        assert result == messages

    def test_get_media_group_not_found(self, state):
        """不存在的媒体组应返回 None。"""
        assert state.get_media_group("nonexistent") is None

    def test_remove_media_group(self, state):
        """应能移除媒体组。"""
        state.add_media_group("group_1", [MagicMock(id=1)])
        state.remove_media_group("group_1")
        assert state.has_media_group("group_1") is False


# ==================== 日期范围管理测试 ====================


class TestDateRange:
    """日期范围管理测试。"""

    def test_set_download_date_start(self, state_with_filter):
        """应能设置起始日期。"""
        state_with_filter.set_download_date(
            "channel_123", "start", "2024-01-01 00:00:00"
        )
        result = state_with_filter.get_download_date("channel_123", "start")
        assert result == "2024-01-01 00:00:00"

    def test_set_download_date_end(self, state_with_filter):
        """应能设置结束日期。"""
        state_with_filter.set_download_date("channel_123", "end", "2024-12-31 00:00:00")
        result = state_with_filter.get_download_date("channel_123", "end")
        assert result == "2024-12-31 00:00:00"

    def test_get_download_date_not_set(self, state_with_filter):
        """未设置日期应返回 None。"""
        result = state_with_filter.get_download_date("channel_123", "start")
        assert result is None

    def test_get_download_date_no_filter(self, state):
        """不存在过滤器时返回 None。"""
        assert state.get_download_date("nobody", "start") is None

    def test_set_adjust_step(self, state_with_filter):
        """应能设置日期步进值。"""
        state_with_filter.set_adjust_step("channel_123", 7)
        assert state_with_filter.get_adjust_step("channel_123") == 7

    def test_get_adjust_step_default(self, state_with_filter):
        """未设置步进值时返回默认值 1。"""
        assert state_with_filter.get_adjust_step("channel_123") == 1

    def test_get_adjust_step_no_filter(self, state):
        """不存在过滤器时返回默认值 1。"""
        assert state.get_adjust_step("nobody") == 1
