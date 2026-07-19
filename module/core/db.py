# coding=UTF-8
"""数据库引擎管理模块。

提供基于 SQLModel + SQLAlchemy 的统一数据库访问，同时支持异步与同步引擎：

- 异步引擎（AsyncEngine / AsyncSession）：供 FastAPI / async 代码使用。
- 同步引擎（Engine / Session）：供同步代码（如 TokenManager）使用。

两个引擎可独立初始化，指向同一数据库文件（trmd.db）。所有表合并到单一
数据库文件，支持跨表关联查询。表结构由 ``SQLModel.metadata`` 统一管理，
通过 ``init_db`` / ``init_sync_db`` 触发 ``create_all`` 一次性建表。
"""

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# 全局唯一异步引擎（单数据库）
_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None

# 全局唯一同步引擎（供同步代码使用）
_sync_engine: Optional[Engine] = None
_sync_session_maker: Optional[sessionmaker] = None


# ==================== 异步引擎 ====================


def get_engine(db_path: Optional[str] = None) -> AsyncEngine:
    """获取或创建异步引擎（单例）。

    Args:
        db_path: 数据库文件路径。仅在引擎未初始化时需要；
                 引擎已初始化后调用可省略。

    Returns:
        AsyncEngine 实例

    Raises:
        ValueError: 引擎未初始化且未提供 db_path
    """
    global _engine
    if _engine is None:
        if db_path is None:
            raise ValueError("数据库引擎未初始化，需提供 db_path")
        url = f"sqlite+aiosqlite:///{db_path}"
        _engine = create_async_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        logger.info(f"数据库引擎已创建: {db_path}")
    return _engine


async def init_db(db_path: str) -> None:
    """初始化数据库（建表 + 配置 PRAGMA）。

    初始化异步引擎与异步会话工厂，并同时初始化同步引擎（供 TokenManager
    等同步代码使用）。必须在使用任何数据库操作前调用一次。

    Args:
        db_path: 数据库文件路径
    """
    global _session_maker
    engine = get_engine(db_path)

    # 配置 SQLite PRAGMA 并创建所有表
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=10000"))
        await conn.run_sync(SQLModel.metadata.create_all)

    _session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # 同步引擎一并初始化，确保同步代码（TokenManager 等）可用
    _init_sync_engine(db_path)

    logger.info("数据库初始化完成（异步+同步引擎已就绪，所有表已创建）")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """获取异步会话（异步上下文管理器）。

    使用方式::

        async with get_session() as session:
            session.add(record)
            await session.commit()

    Yields:
        AsyncSession 实例

    Raises:
        RuntimeError: 异步数据库未初始化（未调用 init_db）
    """
    if _session_maker is None:
        raise RuntimeError("异步数据库未初始化，请先调用 init_db()")
    async with _session_maker() as session:
        yield session


# ==================== 同步引擎 ====================


def get_sync_engine(db_path: Optional[str] = None) -> Engine:
    """获取或创建同步引擎（单例）。

    Args:
        db_path: 数据库文件路径。仅在引擎未初始化时需要；
                 引擎已初始化后调用可省略。

    Returns:
        Engine 实例

    Raises:
        ValueError: 引擎未初始化且未提供 db_path
    """
    global _sync_engine
    if _sync_engine is None:
        if db_path is None:
            raise ValueError("同步数据库引擎未初始化，需提供 db_path")
        url = f"sqlite:///{db_path}"
        _sync_engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        _register_sqlite_pragma(_sync_engine)
        logger.info(f"同步数据库引擎已创建: {db_path}")
    return _sync_engine


def _register_sqlite_pragma(engine: Engine) -> None:
    """为同步引擎的每个新连接设置 SQLite PRAGMA（连接级生效）。

    ``journal_mode=WAL`` 为数据库级持久化；``foreign_keys`` 与
    ``busy_timeout`` 为连接级，故通过 ``connect`` 事件逐连接设置。
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
        finally:
            cursor.close()


def _init_sync_engine(db_path: str) -> None:
    """创建同步引擎、建表并构建同步会话工厂（内部共享逻辑）。

    若同步引擎已就绪则直接返回，保证幂等。
    """
    global _sync_session_maker
    if _sync_engine is not None and _sync_session_maker is not None:
        return
    engine = get_sync_engine(db_path)
    # 建表（SQLModel.metadata 与异步引擎共享同一份元数据）
    with engine.begin() as conn:
        SQLModel.metadata.create_all(conn)
    _sync_session_maker = sessionmaker(bind=engine, expire_on_commit=False)


def init_sync_db(db_path: str) -> None:
    """初始化同步数据库（建表 + 配置 PRAGMA + 同步会话工厂）。

    仅供同步代码路径使用（如 TokenManager）。若已通过 ``init_db`` 完成初始化，
    本调用为幂等无操作。

    Args:
        db_path: 数据库文件路径
    """
    _init_sync_engine(db_path)
    logger.info("同步数据库初始化完成（所有表已创建）")


@contextmanager
def get_sync_session() -> Iterator[Session]:
    """获取同步会话（同步上下文管理器）。

    使用方式::

        with get_sync_session() as session:
            session.add(record)
            session.commit()

    Yields:
        Session 实例

    Raises:
        RuntimeError: 同步数据库未初始化（未调用 init_sync_db / init_db）
    """
    if _sync_session_maker is None:
        raise RuntimeError("同步数据库未初始化，请先调用 init_sync_db() 或 init_db()")
    with _sync_session_maker() as session:
        yield session


def close_sync_db() -> None:
    """关闭同步数据库引擎。"""
    global _sync_engine, _sync_session_maker
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_maker = None
        logger.info("同步数据库引擎已关闭")


# ==================== 通用 ====================


async def close_db() -> None:
    """关闭所有数据库引擎（应用退出时调用）。"""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.info("异步数据库引擎已关闭")
    close_sync_db()


def is_initialized() -> bool:
    """检查数据库引擎是否已初始化（异步或同步任一就绪即为 True）。

    TokenManager 等同步代码在构造时调用本函数判定是否启用持久化；
    由于 ``init_db`` 会同时初始化同步引擎，故异步初始化后同步代码同样可用。
    """
    async_ready = _engine is not None and _session_maker is not None
    sync_ready = _sync_engine is not None and _sync_session_maker is not None
    return async_ready or sync_ready


def is_sync_initialized() -> bool:
    """检查同步数据库引擎是否已初始化。"""
    return _sync_engine is not None and _sync_session_maker is not None


def is_async_initialized() -> bool:
    """检查异步数据库引擎是否已初始化。"""
    return _engine is not None and _session_maker is not None
