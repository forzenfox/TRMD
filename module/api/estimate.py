# coding=UTF-8
"""消息估算核心函数。

提供不同 range_mode 下的消息统计估算能力：
- id_range: 小范围精确遍历，大范围头尾抽样
- multiple_ids: 精确遍历（消息列表已知）
- date_range: 小范围精确遍历，大范围头尾抽样
- all: 头尾各10条抽样估算

设计文档参考: docs/模块设计-缓存层.md 第7节
"""

import logging
from datetime import datetime, timezone

from module.utils.timezone import parse_user_date

logger = logging.getLogger(__name__)

# 抽样参数常量
EXACT_THRESHOLD = 500  # 小于此值可直接精确遍历
SAMPLE_SIZE = 10  # 头尾各10条样本


async def estimate_message_stats(
    client,
    chat_id: int,
    range_mode: str,
    params: dict,
    precise: bool = False,
) -> dict:
    """估算消息范围的统计信息。

    Args:
        client: Pyrogram Client 实例
        chat_id: 频道数字 ID
        range_mode: 范围模式（id_range/date_range/multiple_ids/all）
        params: 范围参数（min_id/max_id/start_date/end_date/message_list/type_filters）
        precise: 是否精确遍历（True=analyze，False=estimate）

    Returns:
        估算结果字典，包含 message_count/total_size_bytes/sample_count 等
    """
    type_filters = params.get("type_filters") or params.get("download_type") or []

    if range_mode == "id_range":
        return await _estimate_id_range(client, chat_id, params, type_filters, precise)
    elif range_mode == "multiple_ids":
        return await _estimate_multiple_ids(
            client, chat_id, params, type_filters, precise
        )
    elif range_mode == "date_range":
        return await _estimate_date_range(
            client, chat_id, params, type_filters, precise
        )
    elif range_mode == "all":
        return await _estimate_all(client, chat_id, params, type_filters, precise)
    else:
        return _empty_estimate(range_mode)


# ==================== 各模式估算实现 ====================


async def _estimate_id_range(client, chat_id, params, type_filters, precise):
    """ID范围估算：小范围精确，大范围抽样。"""
    min_id = params.get("min_id")
    max_id = params.get("max_id")
    if min_id is None or max_id is None:
        return _empty_estimate("id_range")

    min_id = int(min_id)
    max_id = int(max_id)
    total_count = max_id - min_id + 1

    if precise and total_count <= EXACT_THRESHOLD:
        return await _exact_traverse_by_id_range(
            client, chat_id, min_id, max_id, type_filters, "id_range"
        )
    else:
        return await _sample_head_tail_by_id(
            client, chat_id, min_id, max_id, total_count, type_filters
        )


async def _estimate_multiple_ids(client, chat_id, params, type_filters, precise):
    """消息列表估算：直接遍历指定消息（通常数量较少）。"""
    from module.core.task.executor import TaskExecutor

    message_list = params.get("message_list") or []
    if not message_list:
        return _empty_estimate("multiple_ids")

    parsed_ids = TaskExecutor._parse_message_id_list(message_list)
    if not parsed_ids:
        return _empty_estimate("multiple_ids")

    return await _exact_traverse_ids(
        client, chat_id, parsed_ids, type_filters, "multiple_ids"
    )


async def _estimate_date_range(client, chat_id, params, type_filters, precise):
    """日期范围估算：先计数，再决定精确或抽样。"""
    total_count = await _count_date_range_messages(client, chat_id, params)
    if total_count == 0:
        return _empty_estimate("date_range")

    if precise and total_count <= EXACT_THRESHOLD:
        return await _exact_traverse_by_date_range(
            client, chat_id, params, type_filters, "date_range"
        )
    else:
        return await _sample_head_tail_by_date(
            client, chat_id, params, total_count, type_filters
        )


async def _estimate_all(client, chat_id, params, type_filters, precise):
    """全部消息估算：头尾抽样。"""
    total_count = await _get_chat_message_count(client, chat_id)
    if total_count == 0:
        return _empty_estimate("all")

    # 头部样本（最新消息）
    head_messages = []
    try:
        async for msg in client.get_chat_history(chat_id, limit=SAMPLE_SIZE):
            head_messages.append(msg)
    except Exception as e:
        logger.warning("获取头部样本失败: %s", e)

    # 尾部样本（最旧消息）
    tail_messages = await _fetch_tail_messages(client, chat_id, SAMPLE_SIZE)

    samples = head_messages + tail_messages
    return _compute_estimate(samples, total_count, type_filters, "all")


# ==================== 精确遍历实现 ====================


async def _exact_traverse_by_id_range(
    client, chat_id, min_id, max_id, type_filters, range_mode
):
    """精确遍历ID范围内的所有消息。"""
    total_count = max_id - min_id + 1
    messages = []
    try:
        async for message in client.get_chat_history(chat_id):
            if message.id < min_id:
                break
            if message.id > max_id:
                continue
            messages.append(message)
    except Exception as e:
        logger.warning("精确遍历ID范围失败: %s", e)
        return _empty_estimate(range_mode)

    return _compute_exact(messages, total_count, type_filters, range_mode)


async def _exact_traverse_ids(client, chat_id, parsed_ids, type_filters, range_mode):
    """精确遍历指定消息ID列表。"""
    total_count = len(parsed_ids)
    messages = []
    try:
        # 批量获取消息（Pyrogram 的 get_messages 支持列表）
        for msg_id in parsed_ids:
            try:
                msg = await client.get_messages(chat_id, msg_id)
                if msg:
                    messages.append(msg)
            except Exception:
                pass
    except Exception as e:
        logger.warning("精确遍历消息列表失败: %s", e)
        return _empty_estimate(range_mode)

    return _compute_exact(messages, total_count, type_filters, range_mode)


async def _exact_traverse_by_date_range(
    client, chat_id, params, type_filters, range_mode
):
    """精确遍历日期范围内的所有消息。"""
    start_date_str = params.get("start_date")
    end_date_str = params.get("end_date")
    if not start_date_str or not end_date_str:
        return _empty_estimate(range_mode)

    try:
        start_date = parse_user_date(start_date_str, is_end=False)
        end_date = parse_user_date(end_date_str, is_end=True)
    except ValueError:
        return _empty_estimate(range_mode)

    messages = []
    try:
        async for message in client.get_chat_history(chat_id, offset_date=end_date):
            if message.date and message.date < start_date:
                break
            messages.append(message)
    except Exception as e:
        logger.warning("精确遍历日期范围失败: %s", e)
        return _empty_estimate(range_mode)

    total_count = len(messages)
    return _compute_exact(messages, total_count, type_filters, range_mode)


# ==================== 抽样实现 ====================


async def _sample_head_tail_by_id(
    client, chat_id, min_id, max_id, total_count, type_filters
):
    """ID范围头尾抽样：获取min_id附近和max_id附近各SAMPLE_SIZE条。"""
    head_messages = []
    tail_messages = []

    try:
        # 头部样本：从min_id开始向后取SAMPLE_SIZE条
        async for message in client.get_chat_history(chat_id, limit=SAMPLE_SIZE * 2):
            if min_id <= message.id <= max_id:
                head_messages.append(message)
            if len(head_messages) >= SAMPLE_SIZE:
                break
    except Exception as e:
        logger.warning("获取ID范围头部样本失败: %s", e)

    try:
        # 尾部样本：从max_id附近向后取SAMPLE_SIZE条
        async for message in client.get_chat_history(
            chat_id, limit=SAMPLE_SIZE * 2, offset=max_id - min_id
        ):
            if min_id <= message.id <= max_id:
                tail_messages.append(message)
            if len(tail_messages) >= SAMPLE_SIZE:
                break
    except Exception as e:
        logger.warning("获取ID范围尾部样本失败: %s", e)

    samples = head_messages + tail_messages
    return _compute_estimate(samples, total_count, type_filters, "id_range")


async def _sample_head_tail_by_date(client, chat_id, params, total_count, type_filters):
    """日期范围头尾抽样。"""
    start_date_str = params.get("start_date")
    end_date_str = params.get("end_date")
    if not start_date_str or not end_date_str:
        return _empty_estimate("date_range")

    try:
        start_date = parse_user_date(start_date_str, is_end=False)
        end_date = parse_user_date(end_date_str, is_end=True)
    except ValueError:
        return _empty_estimate("date_range")

    head_messages = []
    tail_messages = []

    try:
        # 头部样本（日期范围内最新的消息）
        async for message in client.get_chat_history(
            chat_id, limit=SAMPLE_SIZE, offset_date=end_date
        ):
            if message.date and message.date < start_date:
                break
            head_messages.append(message)
    except Exception as e:
        logger.warning("获取日期范围头部样本失败: %s", e)

    try:
        # 尾部样本（日期范围内最旧的消息）
        # 使用 offset 偏移到接近 start_date 的位置
        offset = max(0, total_count - SAMPLE_SIZE)
        async for message in client.get_chat_history(
            chat_id, limit=SAMPLE_SIZE, offset=offset
        ):
            if message.date and message.date >= start_date:
                tail_messages.append(message)
    except Exception as e:
        logger.warning("获取日期范围尾部样本失败: %s", e)

    samples = head_messages + tail_messages
    return _compute_estimate(samples, total_count, type_filters, "date_range")


# ==================== 通用辅助函数 ====================


def _compute_estimate(samples, total_count, type_filters, range_mode):
    """根据样本计算估算结果。"""
    if type_filters:
        filtered = [m for m in samples if _matches_type_filter(m, type_filters)]
    else:
        filtered = list(samples)

    sample_valid_count = len(filtered)
    sample_total_size = sum(_get_message_size(m) for m in filtered)
    avg_size = sample_total_size / sample_valid_count if sample_valid_count else 0
    estimated_size = int(avg_size * total_count)

    return {
        "message_count": total_count,
        "total_size_bytes": estimated_size,
        "total_size_human": _format_size(estimated_size),
        "estimated_duration_seconds": _estimate_duration(total_count, range_mode),
        "sampled": True,
        "sample_count": len(samples),
        "sample_valid_count": sample_valid_count,
        "avg_size_bytes": avg_size,
        "range_mode": range_mode,
    }


def _compute_exact(messages, total_count, type_filters, range_mode):
    """根据精确遍历结果计算统计。"""
    if type_filters:
        filtered = [m for m in messages if _matches_type_filter(m, type_filters)]
    else:
        filtered = list(messages)

    valid_count = len(filtered)
    total_size = sum(_get_message_size(m) for m in filtered)
    avg_size = total_size / valid_count if valid_count else 0

    return {
        "message_count": total_count,
        "total_size_bytes": total_size,
        "total_size_human": _format_size(total_size),
        "estimated_duration_seconds": _estimate_duration(total_count, range_mode),
        "sampled": False,
        "sample_count": len(messages),
        "sample_valid_count": valid_count,
        "avg_size_bytes": avg_size,
        "range_mode": range_mode,
    }


def _empty_estimate(range_mode: str) -> dict:
    """返回空估算结果。"""
    return {
        "message_count": 0,
        "total_size_bytes": 0,
        "total_size_human": "0 B",
        "estimated_duration_seconds": 0,
        "sampled": False,
        "sample_count": 0,
        "sample_valid_count": 0,
        "avg_size_bytes": 0.0,
        "range_mode": range_mode,
    }


def _matches_type_filter(message, type_filters: list[str]) -> bool:
    """检查消息是否匹配类型过滤。"""
    if not type_filters:
        return True
    media_type = _get_media_type(message)
    if media_type is None:
        return False
    return media_type in type_filters


def _get_message_size(message) -> int:
    """获取消息媒体文件大小。"""
    if not message or not message.media:
        return 0
    for attr in (
        "video",
        "photo",
        "document",
        "audio",
        "animation",
        "voice",
        "video_note",
    ):
        obj = getattr(message, attr, None)
        if obj:
            return getattr(obj, "file_size", 0) or 0
    return 0


def _get_media_type(message) -> str | None:
    """获取消息的媒体类型。"""
    if not message or not message.media:
        return None
    if message.video:
        return "video"
    if message.photo:
        return "photo"
    if message.document:
        return "document"
    if message.audio:
        return "audio"
    if message.animation:
        return "animation"
    if message.voice:
        return "voice"
    if message.video_note:
        return "video_note"
    return None


def _format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读大小。"""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _estimate_duration(message_count: int, range_mode: str) -> int:
    """估算执行耗时（秒）。

    不同模式的单条消息耗时估算：
    - id_range: 约2秒/条（连续下载，较少API开销）
    - multiple_ids: 约2秒/条（离散下载，略慢）
    - date_range: 约3秒/条（需要日期匹配）
    - all: 约3秒/条（遍历+下载）
    """
    seconds_per_message = {
        "id_range": 2,
        "multiple_ids": 2,
        "date_range": 3,
        "all": 3,
    }
    rate = seconds_per_message.get(range_mode, 3)
    return message_count * rate


async def _fetch_tail_messages(client, chat_id, limit):
    """获取频道最旧的N条消息。

    使用 get_chat_history 的 offset 参数逼近最旧消息。
    """
    try:
        chat = await client.get_chat(chat_id)
        total = getattr(chat, "messages_count", 0) or 0
    except Exception:
        total = 0

    if total <= limit:
        # 频道消息很少，直接从头取
        messages = []
        try:
            async for msg in client.get_chat_history(chat_id, limit=limit):
                messages.append(msg)
        except Exception:
            pass
        return messages

    # 偏移到接近最旧消息的位置
    messages = []
    try:
        async for msg in client.get_chat_history(
            chat_id, limit=limit, offset=total - limit
        ):
            messages.append(msg)
    except Exception:
        pass
    return messages


async def _get_chat_message_count(client, chat_id) -> int:
    """获取频道消息总数。"""
    try:
        chat = await client.get_chat(chat_id)
        return getattr(chat, "messages_count", 0) or 0
    except Exception:
        return 0


async def _count_date_range_messages(client, chat_id, params) -> int:
    """按日期范围统计消息数量（不获取文件大小，只计数）。"""
    start_date_str = params.get("start_date")
    end_date_str = params.get("end_date")
    if not start_date_str or not end_date_str:
        return 0

    try:
        start_date = parse_user_date(start_date_str, is_end=False)
        end_date = parse_user_date(end_date_str, is_end=True)
    except ValueError:
        return 0

    count = 0
    try:
        async for message in client.get_chat_history(chat_id, offset_date=end_date):
            if message.date and message.date < start_date:
                break
            count += 1
    except Exception:
        pass

    return count
