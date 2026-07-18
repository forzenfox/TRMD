# coding=UTF-8
"""Token 相关 SQLModel 表模型单元测试。

覆盖 TokenRecordDB 的 CRUD 操作、主键约束、索引查询、
datetime 时间字段、revoked 布尔语义（0/1）、TTL 过期逻辑等场景。
使用同步引擎（SQLite）进行测试，与 TokenManager 实际使用方式一致。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, func, delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from module.core.models.token import TokenRecordDB


# ==================== Fixture ====================


@pytest.fixture
def sync_engine():
    """提供使用内存数据库的同步引擎。

    TokenManager 使用同步引擎，此处匹配其使用模式。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(sync_engine):
    """提供同步会话。"""
    with Session(sync_engine) as session:
        yield session


def _make_token_record(**overrides) -> TokenRecordDB:
    """创建 TokenRecordDB 测试数据。"""
    now = datetime.now(timezone.utc)
    defaults = {
        "token": "tk_abc123def456",
        "user_id": 123,
        "created_at": now,
        "expires_at": now + timedelta(seconds=3600),  # 1 小时后过期
        "last_used_at": None,
        "revoked": 0,
        "usage_count": 0,
    }
    defaults.update(overrides)
    return TokenRecordDB(**defaults)


# ==================== TokenRecordDB CRUD ====================


class TestTokenRecordDBCRUD:
    """TokenRecordDB CRUD 操作测试。"""

    def test_create_token(self, session):
        """创建 Token 记录。"""
        record = _make_token_record()
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.token == "tk_abc123def456"
        assert record.user_id == 123
        assert record.revoked == 0
        assert record.usage_count == 0

    def test_read_token(self, session):
        """按主键读取 Token 记录。"""
        record = _make_token_record()
        session.add(record)
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        assert found is not None
        assert found.user_id == 123

    def test_update_token(self, session):
        """更新 Token 记录（标记已使用）。"""
        record = _make_token_record()
        session.add(record)
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        found.usage_count = 5
        found.last_used_at = datetime.now(timezone.utc)
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        assert found.usage_count == 5
        assert found.last_used_at is not None

    def test_delete_token(self, session):
        """删除 Token 记录。"""
        record = _make_token_record()
        session.add(record)
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        session.delete(found)
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        assert found is None

    def test_count_tokens(self, session):
        """统计 Token 数量。"""
        for i in range(5):
            session.add(_make_token_record(token=f"tk_{i:03d}"))
        session.commit()

        count = session.execute(
            select(func.count()).select_from(TokenRecordDB)
        ).scalar()
        assert count == 5


# ==================== TokenRecordDB 时间字段 ====================


class TestTokenRecordDBDateTime:
    """TokenRecordDB 时间字段（datetime 类型）测试。"""

    def test_created_at_datetime(self, session):
        """created_at 存储为 datetime 对象。"""
        now = datetime.now(timezone.utc)
        record = _make_token_record(created_at=now)
        session.add(record)
        session.commit()
        session.refresh(record)

        assert isinstance(record.created_at, datetime)
        # SQLite 不保留 datetime 时区信息，读出为 naive datetime；
        # 与 aware `now` 比较前需统一为 naive UTC。
        assert abs((record.created_at - now.replace(tzinfo=None)).total_seconds()) < 1

    def test_expires_at_datetime(self, session):
        """expires_at 存储为 datetime 对象。"""
        now = datetime.now(timezone.utc)
        record = _make_token_record(expires_at=now + timedelta(seconds=7200))
        session.add(record)
        session.commit()
        session.refresh(record)

        assert isinstance(record.expires_at, datetime)
        assert record.expires_at > record.created_at

    def test_last_used_at_nullable(self, session):
        """last_used_at 为 None 表示从未使用。"""
        record = _make_token_record(last_used_at=None)
        session.add(record)
        session.commit()
        session.refresh(record)
        assert record.last_used_at is None

    def test_last_used_at_set_on_use(self, session):
        """使用后 last_used_at 被设为当前时间。"""
        record = _make_token_record()
        session.add(record)
        session.commit()

        now = datetime.now(timezone.utc)
        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        found.last_used_at = now
        found.usage_count += 1
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        assert found.last_used_at is not None
        assert abs((found.last_used_at - now.replace(tzinfo=None)).total_seconds()) < 1
        assert found.usage_count == 1


# ==================== TokenRecordDB revoked 字段 ====================


class TestTokenRecordDBRevoked:
    """TokenRecordDB revoked 字段（INTEGER 0/1 布尔语义）测试。"""

    def test_revoked_default_zero(self, session):
        """revoked 默认值为 0（未撤销）。"""
        record = _make_token_record()
        session.add(record)
        session.commit()
        session.refresh(record)
        assert record.revoked == 0

    def test_revoke_token(self, session):
        """撤销 Token：revoked 设为 1。"""
        record = _make_token_record()
        session.add(record)
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        found.revoked = 1
        session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        assert found.revoked == 1

    def test_query_active_tokens(self, session):
        """查询未撤销的 Token。"""
        session.add(_make_token_record(token="tk_active", revoked=0))
        session.add(_make_token_record(token="tk_revoked", revoked=1))
        session.commit()

        active = (
            session.execute(select(TokenRecordDB).where(TokenRecordDB.revoked == 0))
            .scalars()
            .all()
        )
        assert len(active) == 1
        assert active[0].token == "tk_active"

    def test_query_revoked_tokens(self, session):
        """查询已撤销的 Token。"""
        session.add(_make_token_record(token="tk_active", revoked=0))
        session.add(_make_token_record(token="tk_revoked", revoked=1))
        session.commit()

        revoked = (
            session.execute(select(TokenRecordDB).where(TokenRecordDB.revoked == 1))
            .scalars()
            .all()
        )
        assert len(revoked) == 1
        assert revoked[0].token == "tk_revoked"


# ==================== TokenRecordDB 索引查询 ====================


class TestTokenRecordDBIndex:
    """TokenRecordDB 索引查询测试。"""

    def test_query_by_created_at_index(self, session):
        """按 created_at 索引查询 Token。"""
        now = datetime.now(timezone.utc)
        session.add(
            _make_token_record(token="tk_old", created_at=now - timedelta(seconds=7200))
        )
        session.add(_make_token_record(token="tk_new", created_at=now))
        session.commit()

        recent = (
            session.execute(
                select(TokenRecordDB).where(
                    TokenRecordDB.created_at > now - timedelta(seconds=3600)
                )
            )
            .scalars()
            .all()
        )
        assert len(recent) == 1
        assert recent[0].token == "tk_new"

    def test_query_by_expires_at_index(self, session):
        """按 expires_at 索引查询即将过期的 Token。"""
        now = datetime.now(timezone.utc)
        session.add(
            _make_token_record(
                token="tk_expiring", expires_at=now + timedelta(seconds=300)
            )
        )
        session.add(
            _make_token_record(
                token="tk_long_lived", expires_at=now + timedelta(seconds=86400)
            )
        )
        session.commit()

        expiring_soon = (
            session.execute(
                select(TokenRecordDB).where(
                    TokenRecordDB.expires_at < now + timedelta(seconds=600)
                )
            )
            .scalars()
            .all()
        )
        assert len(expiring_soon) == 1
        assert expiring_soon[0].token == "tk_expiring"

    def test_query_by_revoked_index(self, session):
        """按 revoked 索引查询。"""
        session.add(_make_token_record(token="tk_001", revoked=0))
        session.add(_make_token_record(token="tk_002", revoked=1))
        session.add(_make_token_record(token="tk_003", revoked=0))
        session.commit()

        active = (
            session.execute(select(TokenRecordDB).where(TokenRecordDB.revoked == 0))
            .scalars()
            .all()
        )
        assert len(active) == 2


# ==================== TokenRecordDB 过期清理 ====================


class TestTokenRecordDBExpiry:
    """TokenRecordDB 过期清理逻辑测试。"""

    def test_query_expired_tokens(self, session):
        """查询已过期的 Token。"""
        now = datetime.now(timezone.utc)
        session.add(
            _make_token_record(
                token="tk_expired", expires_at=now - timedelta(seconds=3600)
            )
        )
        session.add(
            _make_token_record(
                token="tk_valid", expires_at=now + timedelta(seconds=3600)
            )
        )
        session.commit()

        expired = (
            session.execute(select(TokenRecordDB).where(TokenRecordDB.expires_at < now))
            .scalars()
            .all()
        )
        assert len(expired) == 1
        assert expired[0].token == "tk_expired"

    def test_delete_expired_tokens(self, session):
        """批量删除过期 Token。"""
        now = datetime.now(timezone.utc)
        session.add(
            _make_token_record(
                token="tk_expired_1", expires_at=now - timedelta(seconds=3600)
            )
        )
        session.add(
            _make_token_record(
                token="tk_expired_2", expires_at=now - timedelta(seconds=1800)
            )
        )
        session.add(
            _make_token_record(
                token="tk_valid", expires_at=now + timedelta(seconds=3600)
            )
        )
        session.commit()

        result = session.execute(
            delete(TokenRecordDB).where(TokenRecordDB.expires_at < now)
        )
        session.commit()

        assert result.rowcount == 2

        remaining = session.execute(
            select(func.count()).select_from(TokenRecordDB)
        ).scalar()
        assert remaining == 1

    def test_delete_expired_and_revoked(self, session):
        """清理已过期或已撤销的 Token。"""
        now = datetime.now(timezone.utc)
        session.add(
            _make_token_record(
                token="tk_expired", expires_at=now - timedelta(seconds=3600)
            )
        )
        session.add(_make_token_record(token="tk_revoked", revoked=1))
        session.add(
            _make_token_record(
                token="tk_valid",
                expires_at=now + timedelta(seconds=3600),
                revoked=0,
            )
        )
        session.commit()

        result = session.execute(
            delete(TokenRecordDB).where(
                (TokenRecordDB.expires_at < now) | (TokenRecordDB.revoked == 1)
            )
        )
        session.commit()

        assert result.rowcount == 2

        remaining = session.execute(
            select(func.count()).select_from(TokenRecordDB)
        ).scalar()
        assert remaining == 1


# ==================== TokenRecordDB 默认值 ====================


class TestTokenRecordDBDefaults:
    """TokenRecordDB 默认值测试。"""

    def test_all_default_values(self, session):
        """验证字段的默认值。"""
        now = datetime.now(timezone.utc)
        record = TokenRecordDB(
            token="tk_defaults",
            created_at=now,
            expires_at=now + timedelta(seconds=3600),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.user_id == 0
        assert record.last_used_at is None
        assert record.revoked == 0
        assert record.usage_count == 0


# ==================== TokenRecordDB 主键约束 ====================


class TestTokenRecordDBPrimaryKey:
    """TokenRecordDB 主键约束测试。"""

    def test_token_primary_key_unique(self, session):
        """token 字段为主键，不可重复。"""
        record1 = _make_token_record(token="tk_duplicate")
        record2 = _make_token_record(token="tk_duplicate")

        session.add(record1)
        session.commit()

        session.add(record2)
        with pytest.raises(IntegrityError):
            session.commit()


# ==================== TokenRecordDB usage_count 递增 ====================


class TestTokenRecordDBUsageCount:
    """TokenRecordDB usage_count 递增逻辑测试。"""

    def test_usage_count_increment(self, session):
        """每次使用后 usage_count 递增 1。"""
        record = _make_token_record()
        session.add(record)
        session.commit()

        for i in range(1, 6):
            found = (
                session.execute(
                    select(TokenRecordDB).where(
                        TokenRecordDB.token == "tk_abc123def456"
                    )
                )
                .scalars()
                .first()
            )
            found.usage_count += 1
            session.commit()

        found = (
            session.execute(
                select(TokenRecordDB).where(TokenRecordDB.token == "tk_abc123def456")
            )
            .scalars()
            .first()
        )
        assert found.usage_count == 5


# ==================== TokenRecordDB 表结构验证 ====================


class TestTokenRecordDBSchema:
    """TokenRecordDB 表结构验证测试。"""

    def test_table_name(self, sync_engine):
        """表名应为 'tokens'。"""
        inspector = inspect(sync_engine)
        assert "tokens" in inspector.get_table_names()

    def test_column_names(self, sync_engine):
        """验证列名集合。"""
        inspector = inspect(sync_engine)
        columns = {col["name"] for col in inspector.get_columns("tokens")}
        expected = {
            "token",
            "user_id",
            "created_at",
            "expires_at",
            "last_used_at",
            "revoked",
            "usage_count",
        }
        assert columns == expected

    def test_primary_key(self, sync_engine):
        """主键应为 token 字段。"""
        inspector = inspect(sync_engine)
        pk = inspector.get_pk_constraint("tokens")
        assert "token" in pk["constrained_columns"]
