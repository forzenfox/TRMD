# coding=UTF-8
"""日期范围查询时区兼容性测试。

覆盖场景：
- Pyrogram 返回的 message.date 可能是不带时区的 naive datetime
- message.date 可能使用上海时区（Asia/Shanghai，UTC+8）
- 项目默认按上海时区解释用户输入的日期，再统一转为 UTC 进行比较
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# 确保 module.parser.parse_args() 不会消费 pytest 参数
sys.argv = sys.argv[:1]

from module.core import db
from module.core.task_executor import TaskExecutor
from module.core.task_manager import TaskManager, TaskType
from module.utils.timezone import parse_user_date, SHANGHAI_TZ


class AsyncIteratorMock:
    """模拟异步迭代器。"""

    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


@pytest.fixture
def db_path():
    """创建临时数据库路径。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest_asyncio.fixture
async def task_manager(db_path):
    """创建 TaskManager 实例。"""
    await db.init_db(db_path)
    tm = TaskManager(max_concurrent_tasks=2)
    yield tm
    await db.close_db()


@pytest.fixture
def mock_client():
    """Mock Pyrogram Client。"""
    return AsyncMock()


@pytest.fixture
def mock_file_manager():
    """Mock FileManager。"""
    return AsyncMock()


@pytest.fixture
def task_executor(task_manager, mock_client, mock_file_manager):
    """提供带默认参数的 TaskExecutor 实例。"""
    return TaskExecutor(
        task_manager=task_manager,
        file_manager=mock_file_manager,
        client=mock_client,
    )


# 上海时区：UTC+8
SHANGHAI_TZ = timezone(timedelta(hours=8))


class TestParseUserDate:
    """测试 parse_user_date 统一按上海时区解析用户输入日期。"""

    def test_start_date_shanghai_to_utc(self):
        """开始日期按上海 00:00 解释并转为 UTC。"""
        result = parse_user_date("2026-07-15", is_end=False)
        # 上海 2026-07-15 00:00 = UTC 2026-07-14 16:00
        assert result == datetime(2026, 7, 14, 16, 0, 0, tzinfo=timezone.utc)

    def test_end_date_shanghai_to_utc(self):
        """结束日期按上海 23:59:59 解释并转为 UTC。"""
        result = parse_user_date("2026-07-15", is_end=True)
        # 上海 2026-07-15 23:59:59 = UTC 2026-07-15 15:59:59
        assert result == datetime(2026, 7, 15, 15, 59, 59, tzinfo=timezone.utc)

    def test_date_range_covers_shanghai_day(self):
        """用户输入的 2026-07-15 覆盖的是上海当天 00:00-23:59。"""
        start = parse_user_date("2026-07-15", is_end=False)
        end = parse_user_date("2026-07-15", is_end=True)
        # 上海 00:00
        assert start.astimezone(SHANGHAI_TZ) == datetime(
            2026, 7, 15, 0, 0, 0, tzinfo=SHANGHAI_TZ
        )
        # 上海 23:59:59
        assert end.astimezone(SHANGHAI_TZ) == datetime(
            2026, 7, 15, 23, 59, 59, tzinfo=SHANGHAI_TZ
        )


# 用户提供的真实测试配置
USER_TASK_CONFIG = {
    "file_paths": [],
    "delete_after_upload": True,
    "estimated_size": 0,
    "range_mode": "date_range",
    "filter_types": [],
    "start_date": "2026-07-15",
    "end_date": "2026-07-15",
    "message_list": [],
    "chat_id": -1001239249542,
    "enable_repository_backup": False,
}


class TestResolveDateRangeIdsTimezone:
    """测试 _resolve_date_range_ids 在不同时区类型 message.date 下的兼容性。"""

    @pytest.mark.asyncio
    async def test_naive_datetime_does_not_raise(
        self, task_manager, mock_client, mock_file_manager
    ):
        """message.date 为 naive datetime 时不应触发时区比较错误。"""
        # 模拟消息：naive datetime（不带时区）
        msg_in_range = MagicMock()
        msg_in_range.id = 100
        msg_in_range.date = datetime(2026, 7, 15, 10, 30, 0)  # naive，视为 UTC，在上海 18:30

        # naive 2026-07-14 15:59:59 视为 UTC，早于 start_date (UTC 2026-07-14 16:00)
        msg_out_range = MagicMock()
        msg_out_range.id = 99
        msg_out_range.date = datetime(2026, 7, 14, 15, 59, 59)

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg_in_range, msg_out_range])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001239249542,
            params={
                "range_mode": "date_range",
                "start_date": "2026-07-15",
                "end_date": "2026-07-15",
            },
        )

        # 核心断言：不应抛出时区相关异常
        result = await executor._resolve_date_range_ids(task)
        assert 100 in result
        assert 99 not in result

    @pytest.mark.asyncio
    async def test_shanghai_timezone_datetime(
        self, task_manager, mock_client, mock_file_manager
    ):
        """message.date 为上海时区 aware datetime 时应正确比较。"""
        # 上海 2026-07-15 08:30，在日期范围内（上海当天 00:00-23:59）
        msg_shanghai = MagicMock()
        msg_shanghai.id = 101
        msg_shanghai.date = datetime(2026, 7, 15, 8, 30, 0, tzinfo=SHANGHAI_TZ)

        # 上海 2026-07-14 23:00，早于上海 7月15日 00:00，应被排除
        msg_early = MagicMock()
        msg_early.id = 98
        msg_early.date = datetime(2026, 7, 14, 23, 0, 0, tzinfo=SHANGHAI_TZ)

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg_shanghai, msg_early])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001239249542,
            params={
                "range_mode": "date_range",
                "start_date": "2026-07-15",
                "end_date": "2026-07-15",
            },
        )

        result = await executor._resolve_date_range_ids(task)
        assert 101 in result
        assert 98 not in result

    @pytest.mark.asyncio
    async def test_mixed_timezone_datetimes(
        self, task_manager, mock_client, mock_file_manager
    ):
        """混合 naive、UTC、上海时区的 message.date 都能正确比较。"""
        msg_naive = MagicMock()
        msg_naive.id = 100
        msg_naive.date = datetime(2026, 7, 15, 12, 0, 0)  # naive

        msg_utc = MagicMock()
        msg_utc.id = 101
        msg_utc.date = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)

        msg_shanghai = MagicMock()
        msg_shanghai.id = 102
        msg_shanghai.date = datetime(2026, 7, 15, 20, 0, 0, tzinfo=SHANGHAI_TZ)

        msg_early = MagicMock()
        msg_early.id = 99
        msg_early.date = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock(
                [msg_naive, msg_utc, msg_shanghai, msg_early]
            )
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001239249542,
            params={
                "range_mode": "date_range",
                "start_date": "2026-07-15",
                "end_date": "2026-07-15",
            },
        )

        result = await executor._resolve_date_range_ids(task)
        assert 100 in result
        assert 101 in result
        assert 102 in result
        assert 99 not in result

    @pytest.mark.asyncio
    async def test_user_provided_config(
        self, task_manager, mock_client, mock_file_manager
    ):
        """使用用户提供的真实配置数据进行日期范围查询。"""
        msg_naive = MagicMock()
        msg_naive.id = 100
        msg_naive.date = datetime(2026, 7, 15, 10, 0, 0)  # naive，模拟 Pyrogram 行为

        msg_shanghai = MagicMock()
        msg_shanghai.id = 101
        msg_shanghai.date = datetime(2026, 7, 15, 18, 0, 0, tzinfo=SHANGHAI_TZ)

        mock_client.get_chat_history = MagicMock(
            return_value=AsyncIteratorMock([msg_naive, msg_shanghai])
        )

        executor = TaskExecutor(
            task_manager=task_manager,
            file_manager=mock_file_manager,
            client=mock_client,
        )
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=USER_TASK_CONFIG["chat_id"],
            params=USER_TASK_CONFIG,
        )

        # 核心断言：不应触发 "can't compare offset-naive and offset-aware datetimes"
        result = await executor._resolve_date_range_ids(task)
        assert 100 in result
        assert 101 in result
