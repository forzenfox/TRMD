# coding=UTF-8
"""
CacheManager 模块 - Telegram_Restricted_Media_Downloader 项目缓存层

职责：
- 缓存 Telegram API 调用结果（频道列表、消息列表、消息统计）
- 管理 TTL 过期策略
- 提供强制刷新与自动过期机制
- 支持抽样估算结果缓存
- 单用户场景，使用 SQLite 存储

设计文档：docs/module-design-cache-layer.md
"""

import asyncio
import hashlib
import json
import logging
import os
import pickle
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# 缓存类型常量
CACHE_TYPE_CHAT_LIST = "chat_list"
CACHE_TYPE_MESSAGE_LIST = "message_list"
CACHE_TYPE_MESSAGE_STATS = "message_stats"

# TTL 配置（秒）
TTL_CHAT_LIST = 3600       # 1 小时
TTL_MESSAGE_LIST = 1800    # 30 分钟
TTL_MESSAGE_STATS = 600    # 10 分钟

# 容量控制
DEFAULT_MAX_ENTRIES = 10000  # 默认最大缓存条目数


class CacheError(Exception):
    """缓存操作异常"""
    pass


class CacheManager:
    """
    缓存管理器 - Bot 与 WebUI 共享（单用户）
    
    使用 SQLite 存储缓存数据，支持三种缓存类型：
    - 频道列表（1 小时 TTL）
    - 消息列表（30 分钟 TTL）
    - 消息统计（10 分钟 TTL）
    """

    def __init__(
        self,
        db_path: str,
        serializer: str = "pickle",
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        """
        初始化缓存管理器。

        Args:
            db_path: SQLite 数据库文件路径。
            serializer: 序列化方式，默认 "pickle"，可选 "msgpack" / "json"。
            max_entries: 最大缓存条目数，超过时触发 LRU 淘汰。
        """
        self.db_path = db_path
        self.serializer = serializer
        self.MAX_ENTRIES = max_entries
        self._closed = False
        
        # 单飞请求机制：{cache_key: asyncio.Future}
        self._in_flight: dict[str, asyncio.Future] = {}
        
        # 初始化数据库
        self._init_db()
        
        # 启动时清理过期数据
        self._cleanup_expired_on_start()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key       TEXT PRIMARY KEY,
                    cache_type      TEXT NOT NULL,
                    chat_id         TEXT,
                    payload         BLOB NOT NULL,
                    expires_at      INTEGER NOT NULL,
                    created_at      INTEGER NOT NULL,
                    updated_at      INTEGER NOT NULL,
                    version         INTEGER NOT NULL DEFAULT 1
                );
                
                CREATE TABLE IF NOT EXISTS cache_params (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key       TEXT NOT NULL UNIQUE,
                    param_hash      TEXT NOT NULL,
                    param_json      TEXT NOT NULL,
                    FOREIGN KEY (cache_key) REFERENCES cache_entries(cache_key)
                        ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_cache_entries_type_expires
                    ON cache_entries(cache_type, expires_at);
                
                CREATE INDEX IF NOT EXISTS idx_cache_entries_chat_id
                    ON cache_entries(chat_id);
                
                CREATE INDEX IF NOT EXISTS idx_cache_params_hash
                    ON cache_params(param_hash);
            """)

    def _cleanup_expired_on_start(self) -> None:
        """启动时清理过期数据"""
        try:
            now = int(time.time())
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE expires_at <= ?",
                    (now,),
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(f"启动时清理了 {deleted} 条过期缓存")
        except Exception as e:
            logger.warning(f"启动时清理过期缓存失败: {e}")

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        if self._closed:
            raise CacheError("数据库连接已关闭")
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _make_cache_key(self, prefix: str, chat_id: Optional[str] = None, params: Optional[dict] = None) -> str:
        """
        生成缓存键
        
        Args:
            prefix: 缓存类型前缀
            chat_id: 频道 ID（可选）
            params: 查询参数（可选）
            
        Returns:
            缓存键字符串
        """
        if params:
            # 参数哈希：按 key 排序后的 JSON + SHA-256 前 16 位
            param_str = json.dumps(params, sort_keys=True, default=str)
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            if chat_id:
                return f"{prefix}:{chat_id}:{param_hash}"
            return f"{prefix}:{param_hash}"
        
        if chat_id:
            return f"{prefix}:{chat_id}"
        return prefix

    def _serialize(self, data: Any) -> bytes:
        """序列化数据"""
        if self.serializer == "pickle":
            return pickle.dumps(data)
        elif self.serializer == "json":
            return json.dumps(data, default=str).encode("utf-8")
        else:
            return pickle.dumps(data)

    def _deserialize(self, payload: bytes) -> Any:
        """反序列化数据"""
        if self.serializer == "pickle":
            return pickle.loads(payload)
        elif self.serializer == "json":
            return json.loads(payload.decode("utf-8"))
        else:
            return pickle.loads(payload)

    def _get_ttl(self, cache_type: str) -> int:
        """获取缓存类型的 TTL（秒）"""
        ttl_map = {
            CACHE_TYPE_CHAT_LIST: TTL_CHAT_LIST,
            CACHE_TYPE_MESSAGE_LIST: TTL_MESSAGE_LIST,
            CACHE_TYPE_MESSAGE_STATS: TTL_MESSAGE_STATS,
        }
        return ttl_map.get(cache_type, TTL_CHAT_LIST)

    def _upsert_cache(
        self,
        conn: sqlite3.Connection,
        cache_key: str,
        cache_type: str,
        chat_id: Optional[str],
        data: Any,
        params: Optional[dict] = None,
    ) -> None:
        """
        写入或更新缓存条目
        
        Args:
            conn: 数据库连接
            cache_key: 缓存键
            cache_type: 缓存类型
            chat_id: 频道 ID
            data: 要缓存的数据
            params: 查询参数（可选，用于 cache_params 表）
        """
        now = int(time.time())
        ttl = self._get_ttl(cache_type)
        expires_at = now + ttl
        payload = self._serialize(data)
        
        conn.execute(
            """INSERT OR REPLACE INTO cache_entries 
               (cache_key, cache_type, chat_id, payload, expires_at, created_at, updated_at, version)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (cache_key, cache_type, chat_id, payload, expires_at, now, now),
        )
        
        # 更新参数索引
        if params:
            param_str = json.dumps(params, sort_keys=True, default=str)
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            conn.execute(
                """INSERT OR REPLACE INTO cache_params (cache_key, param_hash, param_json)
                   VALUES (?, ?, ?)""",
                (cache_key, param_hash, param_str),
            )
        
        # 检查是否需要 LRU 淘汰
        cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
        count = cursor.fetchone()[0]
        if count > self.MAX_ENTRIES:
            oversize = count - self.MAX_ENTRIES
            conn.execute(
                """DELETE FROM cache_entries 
                   WHERE cache_key IN (
                       SELECT cache_key FROM cache_entries 
                       ORDER BY updated_at ASC 
                       LIMIT ?
                   )""",
                (oversize,),
            )
            logger.info(f"LRU 淘汰了 {oversize} 条缓存")

    # ---------- 频道/聊天列表 ----------

    async def get_chat_list(
        self,
        fetcher: Callable,
        force_refresh: bool = False,
    ) -> list[dict]:
        """
        获取频道/聊天列表，优先读缓存，未命中或过期时调用 fetcher。

        Args:
            fetcher: 异步可调用对象，返回 Pyrogram Dialog/Chat 列表。
            force_refresh: 是否强制刷新缓存。

        Returns:
            聊天对象列表（已反序列化为可安全使用的 dict）。
        """
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
        """删除所有频道/聊天列表缓存，返回删除条数。"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE cache_type = ?",
                (CACHE_TYPE_CHAT_LIST,),
            )
            deleted = cursor.rowcount
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
        """
        获取消息列表缓存。

        Args:
            chat_id: 频道/聊天 ID。
            params: 查询参数（范围类型、起止 ID、日期、媒体过滤等）。
            fetcher: 异步可调用对象，按 params 从 Telegram 获取消息。
            force_refresh: 是否强制刷新缓存。
        """
        chat_id_str = str(chat_id)
        cache_key = self._make_cache_key(
            "messages", chat_id=chat_id_str, params=params
        )
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_MESSAGE_LIST,
            chat_id=chat_id_str,
            fetcher=fetcher,
            force_refresh=force_refresh,
            params=params,
        )

    async def invalidate_message_list(
        self,
        chat_id: Optional[int | str] = None,
    ) -> int:
        """删除消息列表缓存。若指定 chat_id，仅删除该频道相关缓存。"""
        with self._get_connection() as conn:
            if chat_id is not None:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE cache_type = ? AND chat_id = ?",
                    (CACHE_TYPE_MESSAGE_LIST, str(chat_id)),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE cache_type = ?",
                    (CACHE_TYPE_MESSAGE_LIST,),
                )
            deleted = cursor.rowcount
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
        """
        获取消息统计信息（抽样估算或精确分析）。

        Args:
            chat_id: 频道/聊天 ID。
            params: 统计参数（范围类型、媒体过滤等）。
            estimator: 异步可调用对象，内部决定抽样估算或精确遍历。
            force_refresh: 是否强制刷新缓存。

        Returns:
            统计结果字典，至少包含：
            - total_messages: int
            - total_size_bytes: int
            - estimated: bool（是否为估算值）
            - sample_count: int（抽样消息数）
        """
        chat_id_str = str(chat_id)
        cache_key = self._make_cache_key(
            "estimate", chat_id=chat_id_str, params=params
        )
        return await self._get_or_fetch(
            cache_key=cache_key,
            cache_type=CACHE_TYPE_MESSAGE_STATS,
            chat_id=chat_id_str,
            fetcher=estimator,
            force_refresh=force_refresh,
            params=params,
        )

    async def invalidate_message_stats(
        self,
        chat_id: Optional[int | str] = None,
    ) -> int:
        """删除消息统计缓存。若指定 chat_id，仅删除该频道相关缓存。"""
        with self._get_connection() as conn:
            if chat_id is not None:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE cache_type = ? AND chat_id = ?",
                    (CACHE_TYPE_MESSAGE_STATS, str(chat_id)),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE cache_type = ?",
                    (CACHE_TYPE_MESSAGE_STATS,),
                )
            deleted = cursor.rowcount
            logger.info(f"删除了 {deleted} 条消息统计缓存")
            return deleted

    # ---------- 通用操作 ----------

    async def clear_expired(self) -> int:
        """清理所有过期缓存条目，返回删除条数。"""
        now = int(time.time())
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE expires_at <= ?",
                (now,),
            )
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条过期缓存")
            return deleted

    async def clear_all(self) -> int:
        """清空全部缓存，返回删除条数。"""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache_entries")
            deleted = cursor.rowcount
            logger.info(f"清空了 {deleted} 条缓存")
            return deleted

    async def get_cache_info(self) -> dict:
        """
        返回缓存统计信息（各类型条目数、总大小、最早/最近过期时间）。
        """
        with self._get_connection() as conn:
            # 总数
            cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
            total_entries = cursor.fetchone()[0]
            
            # 各类型计数
            cursor = conn.execute(
                "SELECT cache_type, COUNT(*) FROM cache_entries GROUP BY cache_type"
            )
            type_counts = dict(cursor.fetchall())
            
            # 总大小（估算 payload 大小）
            cursor = conn.execute("SELECT SUM(length(payload)) FROM cache_entries")
            total_size = cursor.fetchone()[0] or 0
            
            # 最早/最近过期时间
            cursor = conn.execute(
                "SELECT MIN(expires_at), MAX(expires_at) FROM cache_entries"
            )
            row = cursor.fetchone()
            earliest_expire = row[0]
            latest_expire = row[1]
            
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
        """关闭数据库连接"""
        self._closed = True
        # 取消所有正在进行的单飞请求
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
        chat_id: Optional[str],
        fetcher: Callable,
        force_refresh: bool = False,
        params: Optional[dict] = None,
    ) -> Any:
        """
        通用的缓存获取/刷新逻辑
        
        流程：
        1. 检查是否已关闭
        2. 如果 force_refresh=True，跳过缓存
        3. 尝试从缓存读取
        4. 缓存命中且未过期 → 返回
        5. 缓存未命中/过期 → 使用单飞机制调用 fetcher
        """
        # 检查连接是否已关闭
        if self._closed:
            raise CacheError("数据库连接已关闭")
        
        now = int(time.time())
        
        # 强制刷新：跳过缓存
        if force_refresh:
            logger.info(f"强制刷新缓存: {cache_key}")
            return await self._execute_and_cache(
                cache_key=cache_key,
                cache_type=cache_type,
                chat_id=chat_id,
                fetcher=fetcher,
                params=params,
            )
        
        # 尝试读取缓存
        try:
            data = await self._read_cache(cache_key, now)
            if data is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return data
        except Exception as e:
            logger.warning(f"缓存读取失败，回退到 fetcher: {e}")
            # 删除损坏的条目
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
            except Exception:
                pass
        
        # 缓存未命中或过期，使用单飞机制
        logger.debug(f"缓存未命中: {cache_key}")
        return await self._execute_and_cache(
            cache_key=cache_key,
            cache_type=cache_type,
            chat_id=chat_id,
            fetcher=fetcher,
            params=params,
        )

    async def _read_cache(self, cache_key: str, now: int) -> Optional[Any]:
        """
        从缓存读取数据
        
        Args:
            cache_key: 缓存键
            now: 当前时间戳
            
        Returns:
            反序列化后的数据，如果缓存不存在或已过期则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT payload, expires_at FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            payload, expires_at = row
            
            # 检查是否过期
            if expires_at <= now:
                # 删除过期条目
                conn.execute(
                    "DELETE FROM cache_entries WHERE cache_key = ?",
                    (cache_key,),
                )
                logger.debug(f"缓存已过期: {cache_key}")
                return None
            
            # 反序列化
            try:
                return self._deserialize(payload)
            except Exception as e:
                raise CacheError(f"反序列化失败: {e}")

    async def _execute_and_cache(
        self,
        cache_key: str,
        cache_type: str,
        chat_id: Optional[str],
        fetcher: Callable,
        params: Optional[dict] = None,
    ) -> Any:
        """
        执行 fetcher 并写入缓存，使用单飞机制避免并发重复调用
        
        Args:
            cache_key: 缓存键
            cache_type: 缓存类型
            chat_id: 频道 ID
            fetcher: 异步可调用对象
            params: 查询参数
            
        Returns:
            fetcher 返回的数据
        """
        # 单飞机制：检查是否有正在进行的请求
        if cache_key in self._in_flight:
            logger.debug(f"等待正在进行的请求: {cache_key}")
            return await self._in_flight[cache_key]
        
        # 创建 Future
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._in_flight[cache_key] = future
        
        try:
            # 执行 fetcher
            data = await fetcher()
            
            # 写入缓存
            try:
                with self._get_connection() as conn:
                    self._upsert_cache(
                        conn=conn,
                        cache_key=cache_key,
                        cache_type=cache_type,
                        chat_id=chat_id,
                        data=data,
                        params=params,
                    )
            except Exception as e:
                logger.warning(f"写入缓存失败: {e}")
                # 缓存写入失败不影响返回数据
            
            # 完成 Future
            if not future.done():
                future.set_result(data)
            return data
            
        except Exception as e:
            # fetcher 失败，不写入缓存
            logger.error(f"fetcher 执行失败: {e}")
            if not future.done():
                future.set_exception(e)
            raise
            
        finally:
            # 清理状态
            self._in_flight.pop(cache_key, None)
