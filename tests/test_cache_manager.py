# coding=UTF-8
"""CacheManager 模块测试用例 - 遵循设计文档 TC-001 至 TC-015"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from module.core import db
from module.core.cache_manager import CacheManager, CacheError
from sqlalchemy import select, text


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_temp_db():
    """创建临时 SQLite 数据库路径"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _mock_chat_list():
    """模拟频道列表数据"""
    return [
        {"id": -1001111, "title": "Channel A", "type": "channel"},
        {"id": -1002222, "title": "Channel B", "type": "group"},
    ]


def _mock_message_list():
    """模拟消息列表数据"""
    return [
        {"id": 1, "date": "2026-01-01", "file_size": 1024},
        {"id": 2, "date": "2026-01-02", "file_size": 2048},
    ]


def _mock_message_stats():
    """模拟消息统计结果"""
    return {
        "total_messages": 1000,
        "total_size_bytes": 500_000_000,
        "estimated": True,
        "sample_count": 20,
    }


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cache():
    """每次测试使用独立的临时数据库"""
    from module.core import db

    db_path = _make_temp_db()
    await db.init_db(db_path)
    mgr = CacheManager()
    yield mgr
    await mgr.close()
    await db.close_db()
    # 清理临时文件
    if os.path.exists(db_path):
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# TC-001: 首次获取频道列表时未命中，调用 fetcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_list_first_miss_calls_fetcher(cache: CacheManager):
    """首次获取频道列表，缓存未命中，应调用 fetcher 并写入缓存"""
    fetcher = AsyncMock(return_value=_mock_chat_list())

    result = await cache.get_chat_list(fetcher=fetcher)

    fetcher.assert_awaited_once()
    assert len(result) == 2
    assert result[0]["title"] == "Channel A"


# ---------------------------------------------------------------------------
# TC-002: 缓存未过期时再次获取命中缓存
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_list_cache_hit(cache: CacheManager):
    """缓存未过期时再次获取，应命中缓存且不调用 fetcher"""
    fetcher = AsyncMock(return_value=_mock_chat_list())

    # 第一次调用
    result1 = await cache.get_chat_list(fetcher=fetcher)
    assert len(result1) == 2

    # 第二次调用 - fetcher 不应再被调用
    result2 = await cache.get_chat_list(fetcher=fetcher)
    assert result2 == result1
    assert fetcher.await_count == 1


# ---------------------------------------------------------------------------
# TC-003: 缓存过期后自动调用 fetcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_list_expired_calls_fetcher(cache: CacheManager):
    """缓存过期后获取，应重新调用 fetcher"""
    fetcher1 = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher1)

    # 手动将过期时间设置为过去
    now = datetime.now(timezone.utc)
    async with db.get_session() as session:
        await session.execute(
            text("UPDATE cache_entries SET expires_at = :exp"),
            {"exp": now - timedelta(seconds=1)},
        )
        await session.commit()

    # 过期后再次获取，应调用 fetcher
    new_data = [{"id": -1003333, "title": "Channel C", "type": "channel"}]
    fetcher2 = AsyncMock(return_value=new_data)
    result = await cache.get_chat_list(fetcher=fetcher2)

    assert fetcher2.await_count == 1
    assert result[0]["title"] == "Channel C"


# ---------------------------------------------------------------------------
# TC-004: force_refresh=True 时跳过缓存
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_list_force_refresh(cache: CacheManager):
    """force_refresh=True 时，即使缓存未过期也应调用 fetcher"""
    fetcher1 = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher1)

    new_data = [{"id": -1009999, "title": "Refreshed", "type": "channel"}]
    fetcher2 = AsyncMock(return_value=new_data)
    result = await cache.get_chat_list(fetcher=fetcher2, force_refresh=True)

    assert fetcher2.await_count == 1
    assert result[0]["title"] == "Refreshed"


# ---------------------------------------------------------------------------
# TC-005: 消息列表按参数生成不同缓存键
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_list_different_params(cache: CacheManager):
    """不同查询参数应生成不同缓存键，互不覆盖"""
    params_a = {"range_type": "id", "min_id": 1, "max_id": 100}
    params_b = {"range_type": "id", "min_id": 101, "max_id": 200}

    fetcher_a = AsyncMock(return_value=_mock_message_list())
    fetcher_b = AsyncMock(return_value=[{"id": 101, "date": "2026-02-01"}])

    result_a = await cache.get_message_list(
        chat_id=-1001111, params=params_a, fetcher=fetcher_a
    )
    result_b = await cache.get_message_list(
        chat_id=-1001111, params=params_b, fetcher=fetcher_b
    )

    assert fetcher_a.await_count == 1
    assert fetcher_b.await_count == 1
    assert len(result_a) == 2
    assert len(result_b) == 1
    assert result_a[0]["id"] == 1
    assert result_b[0]["id"] == 101


# ---------------------------------------------------------------------------
# TC-006: invalidate_chat_list 删除全部频道缓存
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_chat_list(cache: CacheManager):
    """删除频道列表缓存后，下次获取应未命中"""
    fetcher = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher)
    assert fetcher.await_count == 1

    deleted = await cache.invalidate_chat_list()
    assert deleted >= 1

    # 再次获取应重新调用 fetcher
    await cache.get_chat_list(fetcher=fetcher)
    assert fetcher.await_count == 2


# ---------------------------------------------------------------------------
# TC-007: invalidate_message_list 按 chat_id 删除
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_message_list_by_chat_id(cache: CacheManager):
    """指定 chat_id 时仅删除该频道相关的消息列表缓存"""
    chat_a = -1001111
    chat_b = -1002222
    params = {"range_type": "all"}

    fetcher_a = AsyncMock(return_value=_mock_message_list())
    fetcher_b = AsyncMock(return_value=_mock_message_list())

    await cache.get_message_list(chat_id=chat_a, params=params, fetcher=fetcher_a)
    await cache.get_message_list(chat_id=chat_b, params=params, fetcher=fetcher_b)

    # 仅清理 chat_a
    deleted = await cache.invalidate_message_list(chat_id=chat_a)
    assert deleted >= 1

    # chat_a 应未命中，chat_b 应命中
    new_fetcher_a = AsyncMock(return_value=[])
    await cache.get_message_list(chat_id=chat_a, params=params, fetcher=new_fetcher_a)
    await cache.get_message_list(chat_id=chat_b, params=params, fetcher=new_fetcher_a)

    assert new_fetcher_a.await_count == 1  # 仅 chat_a 调用


# ---------------------------------------------------------------------------
# TC-008: clear_expired 删除过期条目
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_expired(cache: CacheManager):
    """清理过期条目，保留未过期条目"""
    fetcher = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher)

    # 手动设置过期
    now = datetime.now(timezone.utc)
    async with db.get_session() as session:
        await session.execute(
            text("UPDATE cache_entries SET expires_at = :exp"),
            {"exp": now - timedelta(seconds=1)},
        )
        await session.commit()

    deleted = await cache.clear_expired()
    assert deleted >= 1

    # 再次获取应重新调用 fetcher
    await cache.get_chat_list(fetcher=fetcher)
    assert fetcher.await_count == 2


# ---------------------------------------------------------------------------
# TC-009: 数据库损坏时读取回退到 fetcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_corruption_fallback(cache: CacheManager):
    """缓存数据损坏时，应回退到 fetcher 而不崩溃"""
    fetcher1 = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher1)

    # 损坏 payload 数据
    async with db.get_session() as session:
        await session.execute(
            text("UPDATE cache_entries SET payload = CAST('broken' AS BLOB)")
        )
        await session.commit()

    # 再次获取应回退到 fetcher
    fetcher2 = AsyncMock(return_value=[{"id": -1009999, "title": "Recovered"}])
    result = await cache.get_chat_list(fetcher=fetcher2)

    assert result[0]["title"] == "Recovered"
    assert fetcher2.await_count == 1


# ---------------------------------------------------------------------------
# TC-010: fetcher 抛出异常时不写入缓存
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetcher_exception_no_cache_write(cache: CacheManager):
    """fetcher 抛出异常时，异常应传播且不写入缓存"""
    from pyrogram.errors import FloodWait

    fetcher = AsyncMock(side_effect=FloodWait(value=30))

    with pytest.raises(FloodWait):
        await cache.get_chat_list(fetcher=fetcher)

    # 缓存中不应有条目
    async with db.get_session() as session:
        from sqlalchemy import func

        from module.core.models.cache import CacheEntryRecord

        count = await session.scalar(select(func.count()).select_from(CacheEntryRecord))
    assert count == 0


# ---------------------------------------------------------------------------
# TC-011: 消息统计抽样估算
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_stats_estimated(cache: CacheManager):
    """消息统计使用抽样估算，返回 estimated=True"""
    estimator = AsyncMock(return_value=_mock_message_stats())

    result = await cache.get_message_stats(
        chat_id=-1001111,
        params={"range_type": "all", "media_filter": "video"},
        estimator=estimator,
    )

    estimator.assert_awaited_once()
    assert result["estimated"] is True
    assert result["total_messages"] == 1000
    assert result["sample_count"] == 20


# ---------------------------------------------------------------------------
# TC-012: 精确分析小范围消息
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_stats_exact(cache: CacheManager):
    """精确分析时 estimated=False"""
    exact_result = {
        "total_messages": 50,
        "total_size_bytes": 25_000_000,
        "estimated": False,
        "sample_count": 50,
    }
    estimator = AsyncMock(return_value=exact_result)

    result = await cache.get_message_stats(
        chat_id=-1001111,
        params={"range_type": "id", "min_id": 1, "max_id": 50},
        estimator=estimator,
    )

    assert result["estimated"] is False
    assert result["total_messages"] == 50


# ---------------------------------------------------------------------------
# TC-013: 缓存条目数超限触发 LRU 淘汰
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_eviction_on_max_entries(cache: CacheManager):
    """缓存条目超过上限时，最旧条目被淘汰"""
    # 使用较小的 MAX_ENTRIES 进行测试
    cache.MAX_ENTRIES = 3

    for i in range(5):
        chat_id = -1000000 - i
        fetcher = AsyncMock(return_value=[{"id": chat_id}])
        await cache.get_chat_list(fetcher=fetcher)

    async with db.get_session() as session:
        from sqlalchemy import func

        from module.core.models.cache import CacheEntryRecord

        count = await session.scalar(select(func.count()).select_from(CacheEntryRecord))

    assert count <= cache.MAX_ENTRIES


# ---------------------------------------------------------------------------
# TC-014: 并发强制刷新单飞请求
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_flight_concurrent_refresh(cache: CacheManager):
    """并发强制刷新同一缓存键时，fetcher 只应被调用一次"""
    call_count = 0
    asyncio.Event()

    async def slow_fetcher():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return _mock_chat_list()

    # 同时发起多个强制刷新请求
    tasks = [
        cache.get_chat_list(fetcher=slow_fetcher, force_refresh=True) for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)

    assert call_count == 1
    assert all(len(r) == 2 for r in results)


# ---------------------------------------------------------------------------
# TC-015: close 后再次访问抛出 CacheError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_then_access_raises_error(cache: CacheManager):
    """关闭数据库连接后再次访问应抛出 CacheError"""
    await cache.close()

    with pytest.raises(CacheError):
        await cache.get_chat_list(fetcher=AsyncMock())


# ---------------------------------------------------------------------------
# 额外测试：get_cache_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cache_info(cache: CacheManager):
    """get_cache_info 返回正确的统计信息"""
    fetcher = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher)

    info = await cache.get_cache_info()

    assert "total_entries" in info
    assert info["total_entries"] >= 1
    assert "total_size_bytes" in info
    assert "chat_list_count" in info


# ---------------------------------------------------------------------------
# 额外测试：clear_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_all(cache: CacheManager):
    """清空全部缓存"""
    fetcher = AsyncMock(return_value=_mock_chat_list())
    await cache.get_chat_list(fetcher=fetcher)

    deleted = await cache.clear_all()
    assert deleted >= 1

    async with db.get_session() as session:
        from sqlalchemy import func

        from module.core.models.cache import CacheEntryRecord

        count = await session.scalar(select(func.count()).select_from(CacheEntryRecord))
    assert count == 0


# ---------------------------------------------------------------------------
# 额外测试：消息统计 TTL 正确
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_stats_ttl(cache: CacheManager):
    """消息统计 TTL 为 10 分钟"""
    estimator = AsyncMock(return_value=_mock_message_stats())

    await cache.get_message_stats(
        chat_id=-1001111,
        params={"range_type": "all"},
        estimator=estimator,
    )

    async with db.get_session() as session:
        from module.core.models.cache import CacheEntryRecord

        # SQLite 不支持 datetime 列直接相减；改为分别读取后在 Python 中相减。
        result = await session.execute(
            select(CacheEntryRecord.expires_at, CacheEntryRecord.created_at).where(
                CacheEntryRecord.cache_type == "message_stats"
            )
        )
        row = result.first()

    assert row is not None
    expires_at, created_at = row
    delta = expires_at - created_at
    assert delta.total_seconds() == 600  # 10 分钟 = 600 秒


# ---------------------------------------------------------------------------
# 额外测试：消息列表 TTL 正确
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_list_ttl(cache: CacheManager):
    """消息列表 TTL 为 30 分钟"""
    fetcher = AsyncMock(return_value=_mock_message_list())

    await cache.get_message_list(
        chat_id=-1001111,
        params={"range_type": "all"},
        fetcher=fetcher,
    )

    async with db.get_session() as session:
        from module.core.models.cache import CacheEntryRecord

        # SQLite 不支持 datetime 列直接相减；改为分别读取后在 Python 中相减。
        result = await session.execute(
            select(CacheEntryRecord.expires_at, CacheEntryRecord.created_at).where(
                CacheEntryRecord.cache_type == "message_list"
            )
        )
        row = result.first()

    assert row is not None
    expires_at, created_at = row
    delta = expires_at - created_at
    assert delta.total_seconds() == 1800  # 30 分钟 = 1800 秒


# ---------------------------------------------------------------------------
# 额外测试：频道列表 TTL 正确
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_list_ttl(cache: CacheManager):
    """频道列表 TTL 为 1 小时"""
    fetcher = AsyncMock(return_value=_mock_chat_list())

    await cache.get_chat_list(fetcher=fetcher)

    async with db.get_session() as session:
        from module.core.models.cache import CacheEntryRecord

        # SQLite 不支持 datetime 列直接相减；改为分别读取后在 Python 中相减。
        result = await session.execute(
            select(CacheEntryRecord.expires_at, CacheEntryRecord.created_at).where(
                CacheEntryRecord.cache_type == "chat_list"
            )
        )
        row = result.first()

    assert row is not None
    expires_at, created_at = row
    delta = expires_at - created_at
    assert delta.total_seconds() == 3600  # 1 小时 = 3600 秒


# ---------------------------------------------------------------------------
# 额外测试：invalidate_message_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_message_stats(cache: CacheManager):
    """删除消息统计缓存"""
    estimator = AsyncMock(return_value=_mock_message_stats())
    await cache.get_message_stats(
        chat_id=-1001111,
        params={"range_type": "all"},
        estimator=estimator,
    )

    deleted = await cache.invalidate_message_stats(chat_id=-1001111)
    assert deleted >= 1

    # 再次获取应未命中
    new_estimator = AsyncMock(return_value=_mock_message_stats())
    await cache.get_message_stats(
        chat_id=-1001111,
        params={"range_type": "all"},
        estimator=new_estimator,
    )
    assert new_estimator.await_count == 1
