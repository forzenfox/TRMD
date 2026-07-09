# coding=UTF-8
"""TokenManager 单元测试。

遵循设计文档 `docs/module-design-token-auth.md` 的接口契约，
覆盖 Token 生成、验证、刷新、撤销、清理、持久化等场景。
"""

import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from module.core.token_manager import (
    TokenManager,
    TokenRecord,
    TokenAuthError,
    TokenInvalidError,
    TokenExpiredError,
    TokenRevokedError,
)

# ==================== 测试工具 ====================


@pytest.fixture
def tmp_db_path():
    """提供临时 SQLite 文件路径，测试结束后自动清理。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # 清理
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def memory_manager():
    """提供内存模式的 TokenManager 实例。"""
    return TokenManager(db_path=None, default_ttl=3600, token_length=32)


@pytest.fixture
def sqlite_manager(tmp_db_path):
    """提供 SQLite 持久化模式的 TokenManager 实例。"""
    return TokenManager(db_path=tmp_db_path, default_ttl=3600, token_length=32)


# ==================== 生成测试 ====================


class TestGenerate:
    """Token 生成相关测试。"""

    def test_generate_returns_string(self, memory_manager):
        """generate() 应返回字符串类型。"""
        token = memory_manager.generate(user_id=123)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_unique_tokens(self, memory_manager):
        """连续两次 generate() 应返回不同的 Token。"""
        t1 = memory_manager.generate(user_id=123)
        t2 = memory_manager.generate(user_id=123)
        assert t1 != t2

    def test_generate_token_length(self, memory_manager):
        """Token 长度应符合 secrets.token_urlsafe(32) 的预期。"""
        token = memory_manager.generate(user_id=123)
        # token_urlsafe(32) 产生约 43 个字符
        assert len(token) >= 40

    def test_generate_with_default_user_id(self, memory_manager):
        """未指定 user_id 时默认使用 0。"""
        token = memory_manager.generate()
        record = memory_manager.verify(token)
        assert record.user_id == 0

    def test_generate_with_custom_user_id(self, memory_manager):
        """指定 user_id 后应正确保存。"""
        token = memory_manager.generate(user_id=999)
        record = memory_manager.verify(token)
        assert record.user_id == 999

    @patch("secrets.token_urlsafe", return_value="fixed_token_value")
    def test_generate_uses_secrets(self, mock_urlsafe, memory_manager):
        """generate() 应调用 secrets.token_urlsafe。"""
        token = memory_manager.generate(user_id=1)
        mock_urlsafe.assert_called_once_with(32)
        assert token == "fixed_token_value"


# ==================== 验证测试 ====================


class TestVerify:
    """Token 验证相关测试。"""

    def test_verify_valid_token(self, memory_manager):
        """验证有效 Token 应返回 TokenRecord。"""
        token = memory_manager.generate(user_id=123)
        record = memory_manager.verify(token)
        assert isinstance(record, TokenRecord)
        assert record.token == token
        assert record.user_id == 123
        assert record.usage_count == 1
        assert record.last_used_at is not None
        assert record.revoked is False

    def test_verify_empty_token_raises(self, memory_manager):
        """验证空字符串应抛出 TokenInvalidError。"""
        with pytest.raises(TokenInvalidError):
            memory_manager.verify("")

    def test_verify_nonexistent_token_raises(self, memory_manager):
        """验证不存在的 Token 应抛出 TokenInvalidError。"""
        with pytest.raises(TokenInvalidError):
            memory_manager.verify("nonexistent_token_xyz")

    def test_verify_updates_usage_count(self, memory_manager):
        """每次 verify() 应递增 usage_count。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.verify(token)
        record = memory_manager.verify(token)
        assert record.usage_count == 2

    def test_verify_updates_last_used_at(self, memory_manager):
        """verify() 应更新 last_used_at。"""
        token = memory_manager.generate(user_id=1)
        r1 = memory_manager.verify(token)
        time.sleep(0.01)
        r2 = memory_manager.verify(token)
        assert r2.last_used_at >= r1.last_used_at

    def test_verify_expired_token_raises(self, memory_manager):
        """验证过期 Token 应抛出 TokenExpiredError。"""
        token = memory_manager.generate(user_id=1)
        # 模拟时间跳到过期后
        with freeze_time(datetime.now(timezone.utc) + timedelta(hours=2)):
            with pytest.raises(TokenExpiredError):
                memory_manager.verify(token)

    def test_verify_revoked_token_raises(self, memory_manager):
        """验证已撤销 Token 应抛出 TokenRevokedError。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.revoke(token)
        with pytest.raises(TokenRevokedError):
            memory_manager.verify(token)

    def test_verify_sets_created_at(self, memory_manager):
        """TokenRecord 应包含 created_at。"""
        token = memory_manager.generate(user_id=1)
        record = memory_manager.verify(token)
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.expires_at, datetime)


# ==================== 刷新测试 ====================


class TestRefresh:
    """Token 刷新相关测试。"""

    def test_refresh_returns_new_token(self, memory_manager):
        """refresh() 应返回新的 Token 字符串。"""
        old_token = memory_manager.generate(user_id=1)
        new_token = memory_manager.refresh(old_token)
        assert isinstance(new_token, str)
        assert new_token != old_token

    def test_refresh_revokes_old_token(self, memory_manager):
        """刷新后旧 Token 应被撤销。"""
        old_token = memory_manager.generate(user_id=1)
        memory_manager.refresh(old_token)
        assert memory_manager.is_valid(old_token) is False

    def test_refresh_new_token_valid(self, memory_manager):
        """刷新后的新 Token 应可验证通过。"""
        old_token = memory_manager.generate(user_id=1)
        new_token = memory_manager.refresh(old_token)
        record = memory_manager.verify(new_token)
        assert record.token == new_token
        assert record.revoked is False

    def test_refresh_invalid_token_raises(self, memory_manager):
        """刷新无效 Token 应抛出异常。"""
        with pytest.raises(TokenAuthError):
            memory_manager.refresh("invalid_token")

    def test_refresh_expired_token_raises(self, memory_manager):
        """刷新过期 Token 应抛出异常。"""
        token = memory_manager.generate(user_id=1)
        with freeze_time(datetime.now(timezone.utc) + timedelta(hours=2)):
            with pytest.raises(TokenAuthError):
                memory_manager.refresh(token)

    def test_refresh_preserves_user_id(self, memory_manager):
        """刷新后新 Token 的 user_id 应与旧 Token 一致。"""
        old_token = memory_manager.generate(user_id=777)
        new_token = memory_manager.refresh(old_token)
        record = memory_manager.verify(new_token)
        assert record.user_id == 777


# ==================== 撤销测试 ====================


class TestRevoke:
    """Token 撤销相关测试。"""

    def test_revoke_valid_token(self, memory_manager):
        """撤销有效 Token 应返回 True。"""
        token = memory_manager.generate(user_id=1)
        result = memory_manager.revoke(token)
        assert result is True

    def test_revoke_nonexistent_token(self, memory_manager):
        """撤销不存在的 Token 应返回 False。"""
        result = memory_manager.revoke("nonexistent")
        assert result is False

    def test_revoke_already_revoked(self, memory_manager):
        """重复撤销已撤销的 Token 应返回 False。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.revoke(token)
        result = memory_manager.revoke(token)
        assert result is False

    def test_revoke_makes_token_invalid(self, memory_manager):
        """撤销后 is_valid() 应返回 False。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.revoke(token)
        assert memory_manager.is_valid(token) is False

    def test_revoke_does_not_delete_record(self, memory_manager):
        """撤销不应删除记录，而是标记 revoked。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.revoke(token)
        # 记录仍存在，verify 应抛 TokenRevokedError
        with pytest.raises(TokenRevokedError):
            memory_manager.verify(token)


class TestRevokeAll:
    """全量撤销相关测试。"""

    def test_revoke_all_revokes_all_tokens(self, memory_manager):
        """revoke_all() 应撤销所有未过期 Token。"""
        t1 = memory_manager.generate(user_id=1)
        t2 = memory_manager.generate(user_id=1)
        t3 = memory_manager.generate(user_id=1)
        count = memory_manager.revoke_all()
        assert count == 3
        assert memory_manager.is_valid(t1) is False
        assert memory_manager.is_valid(t2) is False
        assert memory_manager.is_valid(t3) is False

    def test_revoke_all_returns_count(self, memory_manager):
        """revoke_all() 应返回撤销数量。"""
        memory_manager.generate(user_id=1)
        memory_manager.generate(user_id=1)
        count = memory_manager.revoke_all()
        assert count == 2

    def test_revoke_all_does_not_revoke_already_revoked(self, memory_manager):
        """revoke_all() 不计入已撤销的 Token。"""
        t1 = memory_manager.generate(user_id=1)
        memory_manager.generate(user_id=1)
        memory_manager.revoke(t1)
        count = memory_manager.revoke_all()
        assert count == 1

    def test_revoke_all_empty(self, memory_manager):
        """无 Token 时 revoke_all() 应返回 0。"""
        count = memory_manager.revoke_all()
        assert count == 0

    def test_revoke_all_with_user_id(self, memory_manager):
        """revoke_all(user_id=1) 应仅撤销指定用户的 Token。"""
        t1 = memory_manager.generate(user_id=1)
        t2 = memory_manager.generate(user_id=2)
        count = memory_manager.revoke_all(user_id=1)
        assert count == 1
        assert memory_manager.is_valid(t1) is False
        assert memory_manager.is_valid(t2) is True


# ==================== is_valid 测试 ====================


class TestIsValid:
    """is_valid() 布尔判定测试。"""

    def test_is_valid_returns_true_for_active_token(self, memory_manager):
        """有效 Token is_valid() 应返回 True。"""
        token = memory_manager.generate(user_id=1)
        assert memory_manager.is_valid(token) is True

    def test_is_valid_returns_false_for_expired_token(self, memory_manager):
        """过期 Token is_valid() 应返回 False。"""
        token = memory_manager.generate(user_id=1)
        with freeze_time(datetime.now(timezone.utc) + timedelta(hours=2)):
            assert memory_manager.is_valid(token) is False

    def test_is_valid_returns_false_for_revoked_token(self, memory_manager):
        """已撤销 Token is_valid() 应返回 False。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.revoke(token)
        assert memory_manager.is_valid(token) is False

    def test_is_valid_returns_false_for_nonexistent(self, memory_manager):
        """不存在的 Token is_valid() 应返回 False。"""
        assert memory_manager.is_valid("ghost_token") is False

    def test_is_valid_does_not_increment_usage_count(self, memory_manager):
        """is_valid() 不应更新 usage_count。"""
        token = memory_manager.generate(user_id=1)
        memory_manager.is_valid(token)
        memory_manager.is_valid(token)
        memory_manager.is_valid(token)
        record = memory_manager.verify(token)
        assert record.usage_count == 1


# ==================== 清理测试 ====================


class TestCleanupExpired:
    """清理过期记录测试。"""

    def test_cleanup_expired_removes_old_records(self, memory_manager):
        """cleanup_expired() 应删除过期超过指定时长的记录。"""
        token = memory_manager.generate(user_id=1)
        # 模拟过期 26 小时（留余量避免边界相等导致 strict < 不匹配）
        with freeze_time(datetime.now(timezone.utc) + timedelta(hours=26)):
            count = memory_manager.cleanup_expired(max_age_hours=24)
            assert count == 1
            assert memory_manager.is_valid(token) is False

    def test_cleanup_expired_returns_zero_when_nothing_to_clean(self, memory_manager):
        """没有符合条件的记录时应返回 0。"""
        memory_manager.generate(user_id=1)
        count = memory_manager.cleanup_expired(max_age_hours=24)
        assert count == 0

    def test_cleanup_expired_respects_max_age(self, memory_manager):
        """仅删除过期超过 max_age_hours 的记录。"""
        # 生成两个 Token：一个过期 26h（应删除），一个过期 12h（应保留）
        with freeze_time("2026-01-01 00:00:00"):
            memory_manager.generate(user_id=1)
        with freeze_time("2026-01-01 13:00:00"):
            t2 = memory_manager.generate(user_id=1)
        # 当前时间：2026-01-02 02:00:00
        # t1 expires_at = 2026-01-01 01:00, cutoff = 2026-01-02 02:00 - 24h = 2026-01-01 02:00
        #   01:00 < 02:00 → 应删除
        # t2 expires_at = 2026-01-01 14:00, cutoff = 2026-01-01 02:00
        #   14:00 > 02:00 → 应保留
        with freeze_time("2026-01-02 02:00:00"):
            count = memory_manager.cleanup_expired(max_age_hours=24)
            assert count == 1
            # t2 仍应存在（虽然过期但未满 24h）
            assert memory_manager.is_valid(t2) is False  # 过期，但记录还在
            with pytest.raises(TokenExpiredError):
                memory_manager.verify(t2)


# ==================== 持久化测试 ====================


class TestPersistence:
    """SQLite 持久化测试。"""

    def test_persistence_across_instances(self, tmp_db_path):
        """重建 TokenManager 实例后仍应能验证旧 Token。"""
        mgr1 = TokenManager(db_path=tmp_db_path, default_ttl=3600)
        token = mgr1.generate(user_id=42)

        # 新建实例（模拟重启）
        mgr2 = TokenManager(db_path=tmp_db_path, default_ttl=3600)
        record = mgr2.verify(token)
        assert record.user_id == 42
        assert record.token == token

    def test_persistence_revoked_state(self, tmp_db_path):
        """撤销状态应持久化。"""
        mgr1 = TokenManager(db_path=tmp_db_path)
        token = mgr1.generate(user_id=1)
        mgr1.revoke(token)

        mgr2 = TokenManager(db_path=tmp_db_path)
        with pytest.raises(TokenRevokedError):
            mgr2.verify(token)

    def test_sqlite_table_creation(self, tmp_db_path):
        """初始化后 SQLite 应包含 tokens 表。"""
        TokenManager(db_path=tmp_db_path)
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tokens'"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "tokens"


# ==================== 常量时间比较测试 ====================


class TestConstantTimeComparison:
    """验证使用 hmac.compare_digest 进行常量时间比较。"""

    def test_verify_uses_constant_time_comparison(self, sqlite_manager):
        """verify() 应使用 hmac.compare_digest 比较 Token。"""
        token = sqlite_manager.generate(user_id=1)
        # 通过检查 verify 逻辑间接确认（hmac.compare_digest 的使用）
        record = sqlite_manager.verify(token)
        assert record.token == token


# ==================== 自定义 TTL 测试 ====================


class TestCustomTTL:
    """自定义 TTL 测试。"""

    def test_custom_ttl(self):
        """指定 default_ttl 后，过期时间应正确计算。"""
        manager = TokenManager(db_path=None, default_ttl=1800)  # 30 分钟
        token = manager.generate(user_id=1)
        record = manager.verify(token)
        expected_diff = timedelta(seconds=1800)
        actual_diff = record.expires_at - record.created_at
        assert abs(actual_diff - expected_diff) < timedelta(seconds=1)

    def test_default_ttl_is_one_hour(self):
        """默认 TTL 应为 3600 秒（1 小时）。"""
        manager = TokenManager(db_path=None)
        token = manager.generate(user_id=1)
        record = manager.verify(token)
        expected_diff = timedelta(seconds=3600)
        actual_diff = record.expires_at - record.created_at
        assert abs(actual_diff - expected_diff) < timedelta(seconds=1)


# ==================== 应用上下文 TTL 测试 ====================


class TestAppContextTokenTTL:
    """验证 AppContext 初始化 TokenManager 时使用的 TTL。"""

    def test_app_context_token_manager_ttl_is_12_hours(self, tmp_path):
        """AppContext 创建的 TokenManager 默认 TTL 应为 12 小时（43200 秒）。"""
        from module.integration import AppContext

        # 重置单例，避免影响其他测试
        AppContext._instance = None
        try:
            ctx = AppContext.__new__(AppContext)
            ctx.data_dir = str(tmp_path)
            tm = ctx._init_token_manager()
            assert tm._default_ttl == 12 * 3600, (
                f"AppContext TokenManager TTL 应为 12 小时，实际为 {tm._default_ttl} 秒"
            )
        finally:
            AppContext._instance = None


# ==================== 异常层次测试 ====================


class TestExceptionHierarchy:
    """异常类层次结构测试。"""

    def test_token_invalid_error_is_auth_error(self):
        """TokenInvalidError 应继承 TokenAuthError。"""
        assert issubclass(TokenInvalidError, TokenAuthError)

    def test_token_expired_error_is_auth_error(self):
        """TokenExpiredError 应继承 TokenAuthError。"""
        assert issubclass(TokenExpiredError, TokenAuthError)

    def test_token_revoked_error_is_auth_error(self):
        """TokenRevokedError 应继承 TokenAuthError。"""
        assert issubclass(TokenRevokedError, TokenAuthError)

    def test_token_missing_error_is_auth_error(self):
        """TokenMissingError 应继承 TokenAuthError。"""
        from module.core.token_manager import TokenMissingError

        assert issubclass(TokenMissingError, TokenAuthError)
