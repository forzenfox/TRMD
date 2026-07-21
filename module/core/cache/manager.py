# coding=UTF-8
"""
CacheManager 模块 - Telegram_Restricted_Media_Downloader 项目缓存层

职责：
- 缓存 Telegram API 调用结果（频道列表、消息列表、消息统计）
- 管理 TTL 过期策略
- 提供强制刷新与自动过期机制
- 支持抽样估算结果缓存
- 单用户场景，使用 SQLite 存储
"""

import asyncio
import hashlib
import json
import logging
import pickle
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from module.core.db import get_session
from module.core.cache.models import CacheEntryRecord, CacheParamRecord

logger = logging.getLogger(__name__)

# 缓存类型常量
CACHE_TYPE_CHAT_LIST = "chat_list"
CACHE_TYPE_MESSAGE_LIST = "message_list"
CACHE_TYPE_MESSAGE_STATS = "message_stats"

# 仓库模式缓存类型常量
CACHE_TYPE_REPOSITORY_FILES = "repository_files"
CACHE_TYPE_REPOSITORY_SOURCESS = "repository_sources"
CACHE_TYPE_FILE_DISTRIBUTIONS = "file_distributions"

# TTL 配置（秒）
TTL_CHAT_LIST = 3600  # 1 小时
TTL_MESSAGE_LIST = 1800  # 30 分钟
TTL_MESSAGE_STATS = 600  # 10 分钟

# 仓库缓存TTL配置
TTL_REPOSITORY_FILES = 600  # 10 分钟
TTL_REPOSITORY_SOURCES = 3600  # 1 小时
TTL_FILE_DISTRIBUTIONS = 600  # 10 分钟

# 容量控制
DEFAULT_MAX_ENTRIES = 10000


class CacheError(Exception):
    """缓存操作异常"""

    pass


class CacheManager:
    """缓存管理器 - Bot 与 WebUI 共享（单用户）。

    使用 SQLModel + 异步会话存储缓存数据。
    """

    def __init__(
        self,
        serializer: str = "pickle",
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        self.serializer = serializer
        self.MAX_ENTRIES = max_entries
        self._closed = False
        self._in_flight: dict[str, asyncio.Future] = {}

    def _make_cache_key(
        self, prefix: str, chat_id: Optional[int] = None, params: Optional[dict] = None
    ) -> str:
        if params:
            param_str = json.dumps(params, sort_keys=True, default=str)
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            if chat_id is not None:
                return f"{prefix}:{chat_id}:{param_hash}"
            return f"{prefix}:{param_hash}"
        if chat_id is not None:
            return f"{prefix}:{chat_id}"
        return prefix

    def _serialize(self, data: Any) -> bytes:
        if self.serializer == "pickle":
            return pickle.dumps(data)
        elif self.serializer == "json":
            return json.dumps(data, default=str).encode("utf-8")
        else:
            return pickle.dumps(data)

    def _deserialize(self, payload: bytes) -> Any:
        if self.serializer == "pickle":
            return pickle.loads(payload)
        elif self.serializer == "json":
            return json.loads(payload.decode("utf-8"))
        else:
            return pickle.loads(payload)

    def _get_ttl(self, cache_type: str) -> int:
        ttl_map = {
            CACHE_TYPE_CHAT_LIST: TTL_CHAT_LIST,
            CACHE_TYPE_MESSAGE_LIST: TTL_MESSAGE_LIST,
            CACHE_TYPE_MESSAGE_STATS: TTL_MESSAGE_STATS,
            CACHE_TYPE_REPOSITORY_FILES: TTL_REPOSITORY_FILES,
            CACHE_TYPE_REPOSITORY_SOURCESS: TTL_REPOSITORY_SOURCES,
            CACHE_TYPE_FILE_DISTRIBUTIONS: TTL_FILE_DISTRIBUTIONS,
        }
        return ttl_map.get(cache_type, TTL_CHAT_LIST)

    async def _upsert_cache(
        self,
        session,
        cache_key: str,
        cache_type: str,
        chat_id: Optional[int],
        data: Any,
        params: Optional[dict] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        ttl = self._get_ttl(cache_type)
        expires_at = now + timedelta(seconds=ttl)
        payload = self._serialize(data)

        # INSERT OR REPLACE
        stmt = sqlite_insert(CacheEntryRecord).values(
            cache_key=cache_key,
            cache_type=cache_type,
            chat_id=chat_id,
            payload=payload,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
            version=1,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={
                "cache_type": stmt.excluded.cache_type,
                "chat_id": stmt.excluded.chat_id,
                "payload": stmt.excluded.payload,
                "expires_at": stmt.excluded.expires_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)

        if params:
            param_str = json.dumps(params, sort_keys=True, default=str)
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            param_stmt = sqlite_insert(CacheParamRecord).values(
                cache_key=cache_key,
                param_hash=param_hash,
                param_json=param_str,
            )
            param_stmt = param_stmt.on_conflict_do_update(
                index_elements=["cache_key"],
                set_={
                    "param_hash": param_stmt.excluded.param_hash,
                    "param_json": param_stmt.excluded.param_json,
                },
            )
            await session.execute(param_stmt)

        await session.commit()

        # LRU 淘汰
        count_stmt = select(func.count()).select_from(CacheEntryRecord)
        result = await session.execute(count_stmt)
        count = result.scalar() or 0
        if count > self.MAX_ENTRIES:
            oversize = count - self.MAX_ENTRIES
            old_stmt = (
                select(CacheEntryRecord.cache_key)
                .order_by(CacheEntryRecord.updated_at.asc())
                .limit(oversize)
            )
            old_result = await session.execute(old_stmt)
            old_keys = [row[0] for row in old_result.all()]
            if old_keys:
                del_stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key.in_(old_keys)
                )
                await session.execute(del_stmt)
                await session.commit()
                logger.info(f"LRU 淘汰了 {oversize} 条缓存")

    # ---------- 频道/聊天列表 ----------

    async def get_chat_list(
        self,
        fetcher: Callable,
        force_refresh: bool = False,
    ) -> list[dict]:
        cache_key = self._make_cache_key(CACHE_TYPE_CHAT_LIST)
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_CHAT_LIST,
            chat_id=None,
            fetcher=fetcher,
            force_refresh=force_refresh,
            params=None,
        )

    async def invalidate_chat_list(self) -> int:
        async with get_session() as session:
            stmt = delete(CacheEntryRecord).where(
                CacheEntryRecord.cache_type == CACHE_TYPE_CHAT_LIST
            )
            result = await session.execute(stmt)
            await session.commit()
            deleted = max(result.rowcount, 0)
            logger.info(f"删除了 {deleted} 条频道列表缓存")
            return deleted

    # ---------- 消息列表 ----------

    async def get_message_list(
        self,
        chat_id: int | str,
        params: dict,
        fetcher: Callable,
        force_refresh: bool = False,
    ) -> list[dict]:
        chat_id_int = int(chat_id)
        cache_key = self._make_cache_key("messages", chat_id=chat_id_int, params=params)
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_MESSAGE_LIST,
            chat_id=chat_id_int,
            fetcher=fetcher,
            force_refresh=force_refresh,
            params=params,
        )

    async def invalidate_message_list(self, chat_id: Optional[int | str] = None) -> int:
        async with get_session() as session:
            if chat_id is not None:
                stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type == CACHE_TYPE_MESSAGE_LIST,
                    CacheEntryRecord.chat_id == int(chat_id),
                )
            else:
                stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type == CACHE_TYPE_MESSAGE_LIST
                )
            result = await session.execute(stmt)
            await session.commit()
            deleted = max(result.rowcount, 0)
            logger.info(f"删除了 {deleted} 条消息列表缓存")
            return deleted

    # ---------- 消息统计 ----------

    async def get_message_stats(
        self,
        chat_id: int | str,
        params: dict,
        estimator: Callable,
        force_refresh: bool = False,
    ) -> dict:
        chat_id_int = int(chat_id)
        cache_key = self._make_cache_key("estimate", chat_id=chat_id_int, params=params)
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_MESSAGE_STATS,
            chat_id=chat_id_int,
            fetcher=estimator,
            force_refresh=force_refresh,
            params=params,
        )

    async def invalidate_message_stats(
        self, chat_id: Optional[int | str] = None
    ) -> int:
        async with get_session() as session:
            if chat_id is not None:
                stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type == CACHE_TYPE_MESSAGE_STATS,
                    CacheEntryRecord.chat_id == int(chat_id),
                )
            else:
                stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type == CACHE_TYPE_MESSAGE_STATS
                )
            result = await session.execute(stmt)
            await session.commit()
            deleted = max(result.rowcount, 0)
            logger.info(f"删除了 {deleted} 条消息统计缓存")
            return deleted

    # ---------- 仓库模式缓存 ----------

    async def get_repository_files(
        self,
        chat_id: int,
        params: dict,
        fetcher: Callable | None = None,
        force_refresh: bool = False,
    ) -> dict:
        cache_key = self._make_cache_key(
            CACHE_TYPE_REPOSITORY_FILES, chat_id=chat_id, params=params
        )
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_REPOSITORY_FILES,
            chat_id=chat_id,
            fetcher=fetcher,
            force_refresh=force_refresh,
            params=params,
        )

    async def get_repository_sources(
        self,
        chat_id: int,
        file_unique_id: str,
        fetcher: Callable | None = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        params = {"file_unique_id": file_unique_id}
        cache_key = self._make_cache_key(
            CACHE_TYPE_REPOSITORY_SOURCESS, chat_id=chat_id, params=params
        )
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_REPOSITORY_SOURCESS,
            chat_id=chat_id,
            fetcher=fetcher,
            force_refresh=force_refresh,
            params=params,
        )

    async def get_file_distributions(
        self,
        chat_id: int,
        params: dict,
        fetcher: Callable | None = None,
        force_refresh: bool = False,
    ) -> dict:
        cache_key = self._make_cache_key(
            CACHE_TYPE_FILE_DISTRIBUTIONS, chat_id=chat_id, params=params
        )
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_FILE_DISTRIBUTIONS,
            chat_id=chat_id,
            fetcher=fetcher,
            force_refresh=force_refresh,
            params=params,
        )

    async def clear_repository_cache(self, chat_id: int | None = None) -> int:
        repo_types = (
            CACHE_TYPE_REPOSITORY_FILES,
            CACHE_TYPE_REPOSITORY_SOURCESS,
            CACHE_TYPE_FILE_DISTRIBUTIONS,
        )
        async with get_session() as session:
            if chat_id is not None:
                stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type.in_(repo_types),
                    CacheEntryRecord.chat_id == chat_id,
                )
            else:
                stmt = delete(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type.in_(repo_types)
                )
            result = await session.execute(stmt)
            await session.commit()
            deleted = max(result.rowcount, 0)
            logger.info(f"删除了 {deleted} 条仓库缓存")
            return deleted

    async def clear_all_repository_cache(self) -> int:
        return await self.clear_repository_cache(chat_id=None)

    # ---------- 通用操作 ----------

    async def clear_expired(self) -> int:
        now = datetime.now(timezone.utc)
        # SQLite 存储的 datetime 不带时区，与 aware `now` 在 SQL 层比较时
        # 序列化字符串可能不一致，因此比较前统一为 naive UTC。
        now_naive = now.replace(tzinfo=None)
        async with get_session() as session:
            stmt = delete(CacheEntryRecord).where(
                CacheEntryRecord.expires_at <= now_naive
            )
            result = await session.execute(stmt)
            await session.commit()
            deleted = max(result.rowcount, 0)
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条过期缓存")
            return deleted

    async def clear_all(self) -> int:
        async with get_session() as session:
            stmt = delete(CacheEntryRecord)
            result = await session.execute(stmt)
            await session.commit()
            deleted = max(result.rowcount, 0)
            logger.info(f"清空了 {deleted} 条缓存")
            return deleted

    async def get_cache_info(self) -> dict:
        async with get_session() as session:
            count_stmt = select(func.count()).select_from(CacheEntryRecord)
            total_entries = (await session.execute(count_stmt)).scalar() or 0

            type_stmt = select(CacheEntryRecord.cache_type, func.count()).group_by(
                CacheEntryRecord.cache_type
            )
            type_result = await session.execute(type_stmt)
            type_counts = dict(type_result.all())

            size_stmt = select(func.sum(func.length(CacheEntryRecord.payload)))
            total_size = (await session.execute(size_stmt)).scalar() or 0

            expire_stmt = select(
                func.min(CacheEntryRecord.expires_at),
                func.max(CacheEntryRecord.expires_at),
            )
            expire_result = await session.execute(expire_stmt)
            row = expire_result.one_or_none()
            earliest_expire = row[0].isoformat() if row and row[0] else None
            latest_expire = row[1].isoformat() if row and row[1] else None

            return {
                "total_entries": total_entries,
                "chat_list_count": type_counts.get(CACHE_TYPE_CHAT_LIST, 0),
                "message_list_count": type_counts.get(CACHE_TYPE_MESSAGE_LIST, 0),
                "message_stats_count": type_counts.get(CACHE_TYPE_MESSAGE_STATS, 0),
                "total_size_bytes": total_size,
                "earliest_expires_at": earliest_expire,
                "latest_expires_at": latest_expire,
            }

    async def close(self) -> None:
        self._closed = True
        for future in self._in_flight.values():
            if not future.done():
                future.cancel()
        self._in_flight.clear()
        logger.info("缓存管理器已关闭")

    # ---------- 内部方法 ----------

    async def _get_or_fetch(
        self,
        cache_key: str,
        cache_type: str,
        chat_id: Optional[int],
        fetcher: Callable,
        force_refresh: bool = False,
        params: Optional[dict] = None,
    ) -> Any:
        if self._closed:
            raise CacheError("数据库连接已关闭")

        now = datetime.now(timezone.utc)

        if force_refresh:
            logger.info(f"强制刷新缓存: {cache_key}")
            return await self._execute_and_cache(
                cache_key=cache_key,
                cache_type=cache_type,
                chat_id=chat_id,
                fetcher=fetcher,
                params=params,
            )

        try:
            data = await self._read_cache(cache_key, now)
            if data is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return data
        except Exception as e:
            logger.warning(f"缓存读取失败，回退到 fetcher: {e}")
            try:
                async with get_session() as session:
                    await session.execute(
                        delete(CacheEntryRecord).where(
                            CacheEntryRecord.cache_key == cache_key
                        )
                    )
                    await session.commit()
            except Exception:
                pass

        logger.debug(f"缓存未命中: {cache_key}")
        return await self._execute_and_cache(
            cache_key=cache_key,
            cache_type=cache_type,
            chat_id=chat_id,
            fetcher=fetcher,
            params=params,
        )

    async def _read_cache(self, cache_key: str, now: datetime) -> Optional[Any]:
        async with get_session() as session:
            stmt = select(CacheEntryRecord).where(
                CacheEntryRecord.cache_key == cache_key
            )
            result = await session.execute(stmt)
            record = result.scalars().first()

            if record is None:
                return None

            # SQLite 不保留 datetime 时区信息，读出为 naive datetime；
            # 与 aware `now` 比较前需统一为 UTC aware。
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                await session.execute(
                    delete(CacheEntryRecord).where(
                        CacheEntryRecord.cache_key == cache_key
                    )
                )
                await session.commit()
                logger.debug(f"缓存已过期: {cache_key}")
                return None

            try:
                return self._deserialize(record.payload)
            except Exception as e:
                raise CacheError(f"反序列化失败: {e}")

    async def _execute_and_cache(
        self,
        cache_key: str,
        cache_type: str,
        chat_id: Optional[int],
        fetcher: Callable,
        params: Optional[dict] = None,
    ) -> Any:
        if cache_key in self._in_flight:
            logger.debug(f"等待正在进行的请求: {cache_key}")
            return await self._in_flight[cache_key]

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._in_flight[cache_key] = future

        try:
            data = await fetcher()

            try:
                async with get_session() as session:
                    await self._upsert_cache(
                        session=session,
                        cache_key=cache_key,
                        cache_type=cache_type,
                        chat_id=chat_id,
                        data=data,
                        params=params,
                    )
            except Exception as e:
                logger.warning(f"写入缓存失败: {e}")

            if not future.done():
                future.set_result(data)
            return data

        except Exception as e:
            logger.error(f"fetcher 执行失败: {e}")
            if not future.done():
                future.set_exception(e)
            raise

        finally:
            self._in_flight.pop(cache_key, None)
