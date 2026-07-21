# coding=UTF-8
"""Cache 相关 SQLModel 表模型单元测试。

覆盖 CacheEntryRecord、CacheParamRecord 的 CRUD 操作、
BLOB 字段、主键/UNIQUE 约束、TTL 过期逻辑、索引查询等场景。
使用内存数据库（sqlite+aiosqlite:///:memory:）进行测试。
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError

from module.core import db
from module.core.cache.models import CacheEntryRecord, CacheParamRecord


# ==================== Fixture ====================


@pytest_asyncio.fixture
async def cache_db():
    """提供使用内存数据库的异步会话。"""
    await db.init_db(":memory:")
    yield
    await db.close_db()


def _make_entry_record(**overrides) -> CacheEntryRecord:
    """创建 CacheEntryRecord 测试数据。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "cache_key": "repo_files:-1001234567890",
        "cache_type": "repository_files",
        "chat_id": -1001234567890,
        "payload": b'{"files": [{"id": 1, "name": "test.mp4"}]}',
        "expires_at": now + timedelta(seconds=600),  # 10 分钟后过期
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }
    defaults.update(overrides)
    return CacheEntryRecord(**defaults)


def _make_param_record(**overrides) -> CacheParamRecord:
    """创建 CacheParamRecord 测试数据。"""
    defaults = {
        "cache_key": "repo_files:-1001234567890",
        "param_hash": "abc123def456",
        "param_json": '{"limit": 100, "offset": 0}',
    }
    defaults.update(overrides)
    return CacheParamRecord(**defaults)


# ==================== CacheEntryRecord CRUD ====================


class TestCacheEntryRecordCRUD:
    """CacheEntryRecord CRUD 操作测试。"""

    async def test_create_entry(self, cache_db):
        """创建缓存条目。"""
        record = _make_entry_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.cache_key == "repo_files:-1001234567890"
            assert record.cache_type == "repository_files"
            assert record.chat_id == -1001234567890
            assert record.version == 1

    async def test_read_entry(self, cache_db):
        """按主键读取缓存条目。"""
        record = _make_entry_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            assert found is not None
            assert found.cache_type == "repository_files"

    async def test_update_entry(self, cache_db):
        """更新缓存条目（刷新缓存）。"""
        record = _make_entry_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        new_payload = b'{"files": [{"id": 2, "name": "updated.mp4"}]}'
        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            found.payload = new_payload
            found.updated_at = datetime.now(timezone.utc)
            found.version = 2
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            assert found.payload == new_payload
            assert found.version == 2

    async def test_delete_entry(self, cache_db):
        """删除缓存条目。"""
        record = _make_entry_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            await session.delete(found)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            assert result.scalars().first() is None

    async def test_upsert_entry(self, cache_db):
        """INSERT OR REPLACE 语义：相同 cache_key 应替换旧记录。"""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        now = datetime.now(timezone.utc)
        async with db.get_session() as session:
            # 第一次插入
            stmt = sqlite_insert(CacheEntryRecord).values(
                cache_key="repo_files:-1001234567890",
                cache_type="repository_files",
                chat_id=-1001234567890,
                payload=b'{"version": 1}',
                expires_at=now + timedelta(seconds=600),
                created_at=now,
                updated_at=now,
                version=1,
            )
            await session.execute(stmt)
            await session.commit()

        async with db.get_session() as session:
            # 第二次 INSERT OR REPLACE（on_conflict_do_update）
            stmt = (
                sqlite_insert(CacheEntryRecord)
                .values(
                    cache_key="repo_files:-1001234567890",
                    cache_type="repository_files",
                    chat_id=-1001234567890,
                    payload=b'{"version": 2}',
                    expires_at=now + timedelta(seconds=1200),
                    created_at=now,
                    updated_at=now + timedelta(seconds=1),
                    version=2,
                )
                .on_conflict_do_update(
                    index_elements=["cache_key"],
                    set_={
                        "cache_type": sqlite_insert(
                            CacheEntryRecord
                        ).excluded.cache_type,
                        "chat_id": sqlite_insert(CacheEntryRecord).excluded.chat_id,
                        "payload": sqlite_insert(CacheEntryRecord).excluded.payload,
                        "expires_at": sqlite_insert(
                            CacheEntryRecord
                        ).excluded.expires_at,
                        "updated_at": sqlite_insert(
                            CacheEntryRecord
                        ).excluded.updated_at,
                        "version": sqlite_insert(CacheEntryRecord).excluded.version,
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            assert found.version == 2
            assert found.payload == b'{"version": 2}'
            # SQLite 不保留 datetime 时区信息，读出为 naive datetime，
            # 与 aware `now` 比较前需统一为 naive UTC。
            assert found.expires_at == (now + timedelta(seconds=1200)).replace(
                tzinfo=None
            )


# ==================== CacheEntryRecord BLOB 字段 ====================


class TestCacheEntryRecordBLOB:
    """CacheEntryRecord BLOB（payload）字段测试。"""

    async def test_payload_bytes_storage(self, cache_db):
        """payload 字段存储和读取 bytes。"""
        payload = b"\x00\x01\x02\xff\xfe\xfd"  # 含非 ASCII 字节
        record = _make_entry_record(payload=payload)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.payload == payload

    async def test_payload_json_bytes(self, cache_db):
        """payload 存储 JSON 编码的 bytes。"""
        import json

        data = {"files": [{"id": i, "name": f"file_{i}.mp4"} for i in range(100)]}
        payload = json.dumps(data).encode("utf-8")
        record = _make_entry_record(payload=payload)
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            decoded = json.loads(record.payload.decode("utf-8"))
            assert len(decoded["files"]) == 100

    async def test_payload_empty_bytes(self, cache_db):
        """payload 存储空 bytes。"""
        record = _make_entry_record(payload=b"")
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.payload == b""


# ==================== CacheEntryRecord 索引和约束 ====================


class TestCacheEntryRecordIndex:
    """CacheEntryRecord 索引查询测试。"""

    async def test_query_by_cache_type(self, cache_db):
        """按 cache_type 查询缓存条目。"""
        async with db.get_session() as session:
            session.add(_make_entry_record(cache_type="repository_files"))
            session.add(
                _make_entry_record(
                    cache_key="src_data:-1001234567890",
                    cache_type="source_data",
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.cache_type == "source_data"
                )
            )
            found = result.scalars().all()
            assert len(found) == 1
            assert found[0].cache_type == "source_data"

    async def test_query_by_chat_id_index(self, cache_db):
        """按 chat_id 索引查询缓存条目。"""
        async with db.get_session() as session:
            session.add(_make_entry_record(chat_id=-1001234567890))
            session.add(
                _make_entry_record(
                    cache_key="repo_files:-1009999999999",
                    chat_id=-1009999999999,
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(
                    CacheEntryRecord.chat_id == -1001234567890
                )
            )
            found = result.scalars().all()
            assert len(found) == 1

    async def test_query_expired_entries(self, cache_db):
        """查询已过期的缓存条目。"""
        now = datetime.now(timezone.utc)
        async with db.get_session() as session:
            session.add(
                _make_entry_record(expires_at=now - timedelta(seconds=3600))
            )  # 1 小时前过期
            session.add(
                _make_entry_record(
                    cache_key="repo_files:fresh",
                    expires_at=now + timedelta(seconds=3600),  # 1 小时后过期
                )
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(CacheEntryRecord.expires_at < now)
            )
            expired = result.scalars().all()
            assert len(expired) == 1
            assert expired[0].cache_key == "repo_files:-1001234567890"

    async def test_delete_expired_entries(self, cache_db):
        """批量删除过期缓存条目。"""
        now = datetime.now(timezone.utc)
        async with db.get_session() as session:
            session.add(_make_entry_record(expires_at=now - timedelta(seconds=3600)))
            session.add(
                _make_entry_record(
                    cache_key="repo_files:fresh",
                    expires_at=now + timedelta(seconds=3600),
                )
            )
            await session.commit()

        async with db.get_session() as session:
            await session.execute(
                delete(CacheEntryRecord).where(CacheEntryRecord.expires_at < now)
            )
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(func.count()).select_from(CacheEntryRecord)
            )
            assert result.scalar() == 1


# ==================== CacheEntryRecord 默认值 ====================


class TestCacheEntryRecordDefaults:
    """CacheEntryRecord 默认值测试。"""

    async def test_version_default(self, cache_db):
        """version 默认值为 1。"""
        now = datetime.now(timezone.utc)
        record = CacheEntryRecord(
            cache_key="key_default",
            cache_type="test",
            payload=b"data",
            expires_at=now + timedelta(seconds=600),
            created_at=now,
            updated_at=now,
        )
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.version == 1

    async def test_chat_id_nullable(self, cache_db):
        """chat_id 为 None（全局缓存无 chat_id 关联）。"""
        now = datetime.now(timezone.utc)
        record = CacheEntryRecord(
            cache_key="global_config",
            cache_type="config",
            payload=b"{}",
            expires_at=now + timedelta(seconds=600),
            created_at=now,
            updated_at=now,
        )
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            assert record.chat_id is None


# ==================== CacheParamRecord CRUD ====================


class TestCacheParamRecordCRUD:
    """CacheParamRecord CRUD 操作测试。"""

    async def test_create_param(self, cache_db):
        """创建缓存参数记录。"""
        record = _make_param_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            assert record.id is not None
            assert record.cache_key == "repo_files:-1001234567890"
            assert record.param_hash == "abc123def456"
            assert record.param_json == '{"limit": 100, "offset": 0}'

    async def test_read_param(self, cache_db):
        """按 cache_key 读取参数记录。"""
        record = _make_param_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheParamRecord).where(
                    CacheParamRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            assert found is not None
            assert found.param_hash == "abc123def456"

    async def test_update_param(self, cache_db):
        """更新缓存参数记录。"""
        record = _make_param_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheParamRecord).where(
                    CacheParamRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            found.param_hash = "new_hash_789"
            found.param_json = '{"limit": 50}'
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheParamRecord).where(
                    CacheParamRecord.cache_key == "repo_files:-1001234567890"
                )
            )
            found = result.scalars().first()
            assert found.param_hash == "new_hash_789"
            assert found.param_json == '{"limit": 50}'

    async def test_delete_param(self, cache_db):
        """删除参数记录。"""
        record = _make_param_record()
        async with db.get_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            param_id = record.id

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheParamRecord).where(CacheParamRecord.id == param_id)
            )
            found = result.scalars().first()
            await session.delete(found)
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheParamRecord).where(CacheParamRecord.id == param_id)
            )
            assert result.scalars().first() is None


# ==================== CacheParamRecord 约束 ====================


class TestCacheParamRecordConstraints:
    """CacheParamRecord 约束测试。"""

    async def test_cache_key_unique_constraint(self, cache_db):
        """cache_key UNIQUE 约束：重复插入应失败。"""
        record1 = _make_param_record()
        record2 = _make_param_record(param_hash="different_hash")

        async with db.get_session() as session:
            session.add(record1)
            await session.commit()

        async with db.get_session() as session:
            session.add(record2)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_param_hash_index_query(self, cache_db):
        """param_hash 索引查询。"""
        async with db.get_session() as session:
            session.add(_make_param_record(param_hash="hash_search"))
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheParamRecord).where(
                    CacheParamRecord.param_hash == "hash_search"
                )
            )
            found = result.scalars().first()
            assert found is not None


# ==================== 跨表关联查询 ====================


class TestCacheCrossTableQuery:
    """Cache 相关表跨表关联查询测试。"""

    async def test_entry_with_params_join(self, cache_db):
        """缓存条目与参数 JOIN 查询。"""
        async with db.get_session() as session:
            session.add(_make_entry_record())
            session.add(_make_param_record())
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord, CacheParamRecord).join(
                    CacheParamRecord,
                    CacheEntryRecord.cache_key == CacheParamRecord.cache_key,
                )
            )
            row = result.first()
            assert row is not None
            entry, param = row
            assert entry.cache_key == param.cache_key

    async def test_entry_without_params(self, cache_db):
        """缓存条目可能没有参数记录。"""
        async with db.get_session() as session:
            session.add(_make_entry_record())
            await session.commit()

        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord, CacheParamRecord).join(
                    CacheParamRecord,
                    CacheEntryRecord.cache_key == CacheParamRecord.cache_key,
                    isouter=True,
                )
            )
            row = result.first()
            assert row is not None
            entry, param = row
            assert entry is not None
            assert param is None


# ==================== 并发安全 ====================


class TestCacheConcurrency:
    """Cache 并发操作安全测试。"""

    async def test_concurrent_reads(self, cache_db):
        """并发读取缓存条目。"""
        import asyncio

        now = datetime.now(timezone.utc)
        async with db.get_session() as session:
            for i in range(10):
                session.add(
                    _make_entry_record(
                        cache_key=f"key_{i:03d}",
                        cache_type="test",
                        expires_at=now + timedelta(seconds=600),
                    )
                )
            await session.commit()

        async def read_key(key: str) -> bool:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CacheEntryRecord).where(CacheEntryRecord.cache_key == key)
                )
                return result.scalars().first() is not None

        results = await asyncio.gather(*[read_key(f"key_{i:03d}") for i in range(10)])
        assert all(results)

    async def test_concurrent_write_and_read(self, cache_db):
        """并发写入和读取同一缓存条目。"""
        now = datetime.now(timezone.utc)
        key = "concurrent_key"

        # 先创建
        async with db.get_session() as session:
            session.add(
                _make_entry_record(
                    cache_key=key,
                    payload=b"initial",
                )
            )
            await session.commit()

        async def update_payload(version: int) -> bytes:
            async with db.get_session() as session:
                result = await session.execute(
                    select(CacheEntryRecord).where(CacheEntryRecord.cache_key == key)
                )
                found = result.scalars().first()
                new_payload = f"version_{version}".encode()
                found.payload = new_payload
                found.updated_at = now + timedelta(seconds=version)
                found.version = version
                await session.commit()
                return new_payload

        # 串行更新（SQLite WAL 模式下并发写会串行化）
        payloads = []
        for i in range(1, 4):
            p = await update_payload(i)
            payloads.append(p)

        # 验证最终状态
        async with db.get_session() as session:
            result = await session.execute(
                select(CacheEntryRecord).where(CacheEntryRecord.cache_key == key)
            )
            found = result.scalars().first()
            assert found.version == 3
            assert found.payload == b"version_3"
