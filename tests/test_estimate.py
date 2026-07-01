# coding=UTF-8
"""estimate.py 单元测试。

覆盖场景：
- 各 range_mode 的估算策略（精确/抽样）
- 抽样结果计算
- 类型过滤匹配
- 消息文件大小获取
- 大小格式化和耗时估算
- 空范围返回默认值
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.api.estimate import (
    estimate_message_stats,
    _compute_estimate,
    _compute_exact,
    _empty_estimate,
    _matches_type_filter,
    _get_message_size,
    _get_media_type,
    _format_size,
    _estimate_duration,
    _count_date_range_messages,
)


# ==================== Mock 辅助 ====================


def _make_mock_message(
    msg_id: int,
    media_type: str | None = None,
    file_size: int = 0,
    date: datetime | None = None,
):
    """创建 mock 消息对象。"""
    msg = MagicMock()
    msg.id = msg_id
    msg.date = date or datetime(2026, 1, 1, tzinfo=timezone.utc)
    msg.media = media_type is not None

    # 设置媒体属性
    for attr in (
        "video",
        "photo",
        "document",
        "audio",
        "animation",
        "voice",
        "video_note",
    ):
        obj = MagicMock() if attr == media_type else None
        if obj:
            obj.file_size = file_size
        setattr(msg, attr, obj)

    return msg


def _make_async_history(messages: list):
    """创建异步迭代器 mock，模拟 get_chat_history 返回值。"""

    async def _aiter():
        for msg in messages:
            yield msg

    return _aiter()


# ==================== 测试：_format_size ====================


class TestFormatSize:
    """测试 _format_size 大小格式化。"""

    def test_zero(self):
        assert _format_size(0) == "0 B"

    def test_bytes(self):
        assert _format_size(512) == "512.0 B"

    def test_kilobytes(self):
        assert _format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert _format_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert _format_size(1024**3) == "1.0 GB"

    def test_terabytes(self):
        assert _format_size(1024**4) == "1.0 TB"

    def test_large_value(self):
        result = _format_size(1024**5)
        # 1024 TB = 1024.0 TB（units 列表到 TB 为止，不包含 PB）
        assert "TB" in result


# ==================== 测试：_estimate_duration ====================


class TestEstimateDuration:
    """测试 _estimate_duration 耗时估算。"""

    def test_id_range(self):
        assert _estimate_duration(100, "id_range") == 200

    def test_multiple_ids(self):
        assert _estimate_duration(100, "multiple_ids") == 200

    def test_date_range(self):
        assert _estimate_duration(100, "date_range") == 300

    def test_all(self):
        assert _estimate_duration(100, "all") == 300

    def test_unknown_mode(self):
        assert _estimate_duration(100, "unknown") == 300

    def test_zero_count(self):
        assert _estimate_duration(0, "id_range") == 0


# ==================== 测试：_get_media_type ====================


class TestGetMediaType:
    """测试 _get_media_type 媒体类型识别。"""

    def test_video(self):
        msg = _make_mock_message(1, "video")
        assert _get_media_type(msg) == "video"

    def test_photo(self):
        msg = _make_mock_message(2, "photo")
        assert _get_media_type(msg) == "photo"

    def test_document(self):
        msg = _make_mock_message(3, "document")
        assert _get_media_type(msg) == "document"

    def test_audio(self):
        msg = _make_mock_message(4, "audio")
        assert _get_media_type(msg) == "audio"

    def test_animation(self):
        msg = _make_mock_message(5, "animation")
        assert _get_media_type(msg) == "animation"

    def test_voice(self):
        msg = _make_mock_message(6, "voice")
        assert _get_media_type(msg) == "voice"

    def test_video_note(self):
        msg = _make_mock_message(7, "video_note")
        assert _get_media_type(msg) == "video_note"

    def test_no_media(self):
        msg = _make_mock_message(8, None)
        assert _get_media_type(msg) is None

    def test_none_message(self):
        assert _get_media_type(None) is None


# ==================== 测试：_get_message_size ====================


class TestGetMessageSize:
    """测试 _get_message_size 消息文件大小获取。"""

    def test_video_size(self):
        msg = _make_mock_message(1, "video", file_size=10 * 1024 * 1024)
        assert _get_message_size(msg) == 10 * 1024 * 1024

    def test_photo_size(self):
        msg = _make_mock_message(2, "photo", file_size=500 * 1024)
        assert _get_message_size(msg) == 500 * 1024

    def test_no_media(self):
        msg = _make_mock_message(3, None)
        assert _get_message_size(msg) == 0

    def test_none_message(self):
        assert _get_message_size(None) == 0


# ==================== 测试：_matches_type_filter ====================


class TestMatchesTypeFilter:
    """测试 _matches_type_filter 类型过滤匹配。"""

    def test_empty_filters(self):
        msg = _make_mock_message(1, "video")
        assert _matches_type_filter(msg, []) is True

    def test_matching_filter(self):
        msg = _make_mock_message(1, "video")
        assert _matches_type_filter(msg, ["video", "photo"]) is True

    def test_non_matching_filter(self):
        msg = _make_mock_message(1, "video")
        assert _matches_type_filter(msg, ["photo", "audio"]) is False

    def test_no_media_with_filter(self):
        msg = _make_mock_message(1, None)
        assert _matches_type_filter(msg, ["video"]) is False


# ==================== 测试：_empty_estimate ====================


class TestEmptyEstimate:
    """测试 _empty_estimate 空估算结果。"""

    def test_returns_zero_values(self):
        result = _empty_estimate("id_range")
        assert result["message_count"] == 0
        assert result["total_size_bytes"] == 0
        assert result["total_size_human"] == "0 B"
        assert result["estimated_duration_seconds"] == 0
        assert result["sampled"] is False
        assert result["sample_count"] == 0
        assert result["sample_valid_count"] == 0
        assert result["avg_size_bytes"] == 0.0
        assert result["range_mode"] == "id_range"


# ==================== 测试：_compute_estimate ====================


class TestComputeEstimate:
    """测试 _compute_estimate 抽样估算结果计算。"""

    def test_basic_estimate(self):
        msgs = [
            _make_mock_message(1, "video", file_size=10 * 1024 * 1024),
            _make_mock_message(2, "video", file_size=20 * 1024 * 1024),
        ]
        result = _compute_estimate(msgs, 100, [], "id_range")
        assert result["message_count"] == 100
        assert result["sample_count"] == 2
        assert result["sample_valid_count"] == 2
        assert result["avg_size_bytes"] == 15 * 1024 * 1024
        assert result["total_size_bytes"] == int(15 * 1024 * 1024 * 100)
        assert result["sampled"] is True
        assert result["range_mode"] == "id_range"

    def test_with_type_filters(self):
        msgs = [
            _make_mock_message(1, "video", file_size=10 * 1024 * 1024),
            _make_mock_message(2, "photo", file_size=500 * 1024),
        ]
        result = _compute_estimate(msgs, 100, ["video"], "all")
        assert result["sample_valid_count"] == 1
        assert result["avg_size_bytes"] == 10 * 1024 * 1024
        assert result["total_size_bytes"] == int(10 * 1024 * 1024 * 100)

    def test_no_valid_samples(self):
        msgs = [
            _make_mock_message(1, "video", file_size=10 * 1024 * 1024),
        ]
        result = _compute_estimate(msgs, 100, ["photo"], "id_range")
        assert result["sample_valid_count"] == 0
        assert result["avg_size_bytes"] == 0
        assert result["total_size_bytes"] == 0


# ==================== 测试：_compute_exact ====================


class TestComputeExact:
    """测试 _compute_exact 精确统计结果计算。"""

    def test_basic_exact(self):
        msgs = [
            _make_mock_message(1, "video", file_size=10 * 1024 * 1024),
            _make_mock_message(2, "video", file_size=20 * 1024 * 1024),
        ]
        result = _compute_exact(msgs, 2, [], "id_range")
        assert result["message_count"] == 2
        assert result["total_size_bytes"] == 30 * 1024 * 1024
        assert result["sampled"] is False

    def test_with_type_filters(self):
        msgs = [
            _make_mock_message(1, "video", file_size=10 * 1024 * 1024),
            _make_mock_message(2, "photo", file_size=500 * 1024),
        ]
        result = _compute_exact(msgs, 2, ["video"], "multiple_ids")
        assert result["sample_valid_count"] == 1
        assert result["total_size_bytes"] == 10 * 1024 * 1024


# ==================== 测试：estimate_message_stats 集成 ====================


class TestEstimateIdRange:
    """测试 id_range 模式估算。"""

    @pytest.mark.asyncio
    async def test_missing_params(self):
        """缺少 min_id/max_id 时返回空估算。"""
        client = AsyncMock()
        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="id_range",
            params={},
            precise=False,
        )
        assert result["message_count"] == 0

    @pytest.mark.asyncio
    async def test_small_range_exact(self):
        """小范围 + precise=True 应精确遍历。"""
        messages = [
            _make_mock_message(1, "video", file_size=10 * 1024 * 1024),
            _make_mock_message(2, "video", file_size=20 * 1024 * 1024),
        ]
        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=_make_async_history(messages))

        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="id_range",
            params={"min_id": 1, "max_id": 2},
            precise=True,
        )
        assert result["sampled"] is False
        assert result["total_size_bytes"] == 30 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_large_range_sampled(self):
        """大范围（>500）+ precise=False 应抽样估算。"""
        client = AsyncMock()
        # mock get_chat_history 返回空迭代器
        client.get_chat_history = MagicMock(return_value=_make_async_history([]))

        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="id_range",
            params={"min_id": 1, "max_id": 1000},
            precise=False,
        )
        # 大范围应走抽样
        assert result["range_mode"] == "id_range"
        assert result["message_count"] == 1000  # max_id - min_id + 1


class TestEstimateMultipleIds:
    """测试 multiple_ids 模式估算。"""

    @pytest.mark.asyncio
    async def test_empty_message_list(self):
        """空消息列表返回空估算。"""
        client = AsyncMock()
        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="multiple_ids",
            params={"message_list": []},
            precise=True,
        )
        assert result["message_count"] == 0

    @pytest.mark.asyncio
    async def test_exact_traverse(self):
        """消息列表精确遍历。"""
        msg1 = _make_mock_message(100, "video", file_size=10 * 1024 * 1024)
        msg2 = _make_mock_message(200, "photo", file_size=500 * 1024)
        client = AsyncMock()
        client.get_messages = AsyncMock(side_effect=[msg1, msg2])

        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="multiple_ids",
            params={"message_list": [100, 200]},
            precise=True,
        )
        assert result["sampled"] is False
        assert result["message_count"] == 2
        assert result["total_size_bytes"] == 10 * 1024 * 1024 + 500 * 1024

    @pytest.mark.asyncio
    async def test_with_type_filters(self):
        """消息列表 + 类型过滤。"""
        msg1 = _make_mock_message(100, "video", file_size=10 * 1024 * 1024)
        msg2 = _make_mock_message(200, "photo", file_size=500 * 1024)
        client = AsyncMock()
        client.get_messages = AsyncMock(side_effect=[msg1, msg2])

        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="multiple_ids",
            params={"message_list": [100, 200], "type_filters": ["video"]},
            precise=True,
        )
        assert result["sample_valid_count"] == 1
        assert result["total_size_bytes"] == 10 * 1024 * 1024


class TestEstimateDateRange:
    """测试 date_range 模式估算。"""

    @pytest.mark.asyncio
    async def test_missing_params(self):
        """缺少 start_date/end_date 时返回空估算。"""
        client = AsyncMock()
        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="date_range",
            params={},
            precise=False,
        )
        assert result["message_count"] == 0


class TestEstimateAll:
    """测试 all 模式估算。"""

    @pytest.mark.asyncio
    async def test_empty_channel(self):
        """空频道返回空估算。"""
        client = AsyncMock()
        mock_chat = MagicMock()
        mock_chat.messages_count = 0
        client.get_chat = AsyncMock(return_value=mock_chat)

        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="all",
            params={},
            precise=False,
        )
        assert result["message_count"] == 0

    @pytest.mark.asyncio
    async def test_sampled_estimate(self):
        """all 模式使用头尾抽样估算。"""
        head_msgs = [
            _make_mock_message(i, "video", file_size=10 * 1024 * 1024)
            for i in range(1, 11)
        ]
        tail_msgs = [
            _make_mock_message(i, "video", file_size=5 * 1024 * 1024)
            for i in range(91, 101)
        ]
        mock_chat = MagicMock()
        mock_chat.messages_count = 100

        call_count = 0

        def mock_get_history(chat_id, limit=None, offset=None):
            nonlocal call_count
            call_count += 1
            if offset is not None:
                return _make_async_history(tail_msgs)
            return _make_async_history(head_msgs)

        client = AsyncMock()
        client.get_chat = AsyncMock(return_value=mock_chat)
        client.get_chat_history = MagicMock(side_effect=mock_get_history)

        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="all",
            params={},
            precise=False,
        )
        assert result["message_count"] == 100
        assert result["sampled"] is True
        assert result["sample_count"] == 20  # 10 head + 10 tail
        assert result["avg_size_bytes"] > 0
        assert result["total_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_unknown_range_mode(self):
        """未知 range_mode 返回空估算。"""
        client = AsyncMock()
        result = await estimate_message_stats(
            client=client,
            chat_id=-1001234567890,
            range_mode="invalid_mode",
            params={},
            precise=False,
        )
        assert result["message_count"] == 0
        assert result["range_mode"] == "invalid_mode"


# ==================== 测试：_count_date_range_messages ====================


class TestCountDateRangeMessages:
    """测试 _count_date_range_messages 日期范围消息计数。"""

    @pytest.mark.asyncio
    async def test_missing_params(self):
        """缺少日期参数返回0。"""
        client = AsyncMock()
        count = await _count_date_range_messages(client, -1001234567890, {})
        assert count == 0

    @pytest.mark.asyncio
    async def test_invalid_date_format(self):
        """无效日期格式返回0。"""
        client = AsyncMock()
        count = await _count_date_range_messages(
            client,
            -1001234567890,
            {"start_date": "invalid", "end_date": "2026-01-31"},
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_messages(self):
        """正确计数日期范围内的消息。"""
        messages = [
            _make_mock_message(
                i,
                "video",
                date=datetime(2026, 1, i, tzinfo=timezone.utc),
            )
            for i in range(1, 31)
        ]
        client = AsyncMock()
        client.get_chat_history = MagicMock(return_value=_make_async_history(messages))

        count = await _count_date_range_messages(
            client,
            -1001234567890,
            {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )
        assert count == 30
