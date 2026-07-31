# coding=UTF-8
"""时区工具 - 统一用户输入日期的时区处理。"""

from datetime import datetime, timedelta, timezone

SHANGHAI_TZ = timezone(timedelta(hours=8))


def parse_user_date(date_str: str, is_end: bool = False) -> datetime:
    """将用户输入的 YYYY-MM-DD 日期按上海时区解析为 UTC datetime。

    前端日期选择器只提供日期部分，需要补齐时间并按项目默认时区（上海）
    解释，再统一转换为 UTC 与 Telegram 消息日期比较。

    Args:
        date_str: 日期字符串，格式 YYYY-MM-DD
        is_end: 是否为日期结束时间（23:59:59），否则为开始时间（00:00:00）

    Returns:
        UTC 时区的 datetime
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if is_end:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(tzinfo=SHANGHAI_TZ).astimezone(timezone.utc)
