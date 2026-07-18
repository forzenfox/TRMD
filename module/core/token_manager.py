# coding=UTF-8
"""Token 认证管理模块。

负责 Token 的生成、验证、刷新、撤销、过期清理与持久化。
详见 `docs/模块设计-Token认证.md`。

持久化通过 SQLModel 同步引擎（`module.core.db`）实现；若数据库未初始化，
则回退到内存字典（便于测试与无写权限环境）。数据库引擎与表结构由
`module.core.db.init_sync_db` / `init_db` 统一管理，本类不再持有 db_path。
"""

import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, update
from sqlmodel import select

from module.core import db
from module.core.models.token import TokenRecordDB

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass(slots=True)
class TokenRecord:
    """Token 运行时记录（业务逻辑层）。"""

    token: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime] = None
    revoked: bool = False
    usage_count: int = 0


# ==================== 异常类型 ====================


class TokenAuthError(Exception):
    """认证相关异常的基类。"""


class TokenMissingError(TokenAuthError):
    """请求未携带 Token。"""


class TokenInvalidError(TokenAuthError):
    """Token 格式错误或不存在。"""


class TokenExpiredError(TokenAuthError):
    """Token 已过期。"""


class TokenRevokedError(TokenAuthError):
    """Token 已被撤销。"""


# ==================== TokenManager ====================


class TokenManager:
    """临时 Token 生命周期管理器。

    数据库是否可用在构造时一次性判定（`db.is_initialized()`）。若需持久化，
    调用方必须在构造 TokenManager 之前完成 `db.init_sync_db()` / `db.init_db()`；
    否则回退到内存字典模式。
    """

    def __init__(
        self,
        default_ttl: int = 3600,
        token_length: int = 32,
    ) -> None:
        """
        :param default_ttl: Token 默认有效期，单位秒，默认 1 小时。
        :param token_length: secrets.token_urlsafe 长度参数。
        """
        self._default_ttl = default_ttl
        self._token_length = token_length
        self._use_sqlite = db.is_initialized()

        if not self._use_sqlite:
            # 内存字典：token -> TokenRecord
            self._store: dict[str, TokenRecord] = {}

    # ---- 内部辅助方法 ----

    def _now(self) -> datetime:
        """获取当前 UTC 时间。"""
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """将 naive datetime 视为 UTC 并补充时区信息。

        SQLite 不保留 datetime 时区信息，从数据库读出的 naive datetime
        与 aware `_now()` 比较前需统一为 aware UTC。
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _record_to_db(self, record: TokenRecord) -> TokenRecordDB:
        """TokenRecord -> TokenRecordDB（持久化模型）。

        时间字段（datetime）由 SQLAlchemy 自动序列化为 ISO 8601 字符串存储，
        无需手动转换为 Unix 时间戳。
        """
        return TokenRecordDB(
            token=record.token,
            user_id=record.user_id,
            created_at=record.created_at,
            expires_at=record.expires_at,
            last_used_at=record.last_used_at,
            revoked=1 if record.revoked else 0,
            usage_count=record.usage_count,
        )

    def _db_to_record(self, row: TokenRecordDB) -> TokenRecord:
        """TokenRecordDB -> TokenRecord（业务模型）。

        SQLModel datetime 字段读取时自动返回 datetime 对象，无需手动转换。
        """
        return TokenRecord(
            token=row.token,
            user_id=row.user_id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            revoked=bool(row.revoked),
            usage_count=row.usage_count,
        )

    def _find_record(self, token: str) -> Optional[TokenRecord]:
        """根据 Token 查找记录。"""
        if self._use_sqlite:
            return self._find_record_db(token)
        return self._store.get(token)

    def _find_record_db(self, token: str) -> Optional[TokenRecord]:
        """从数据库查找记录，使用常量时间比较。"""
        with db.get_sync_session() as session:
            statement = select(TokenRecordDB).where(TokenRecordDB.token == token)
            row = session.execute(statement).scalars().first()
        if row is None:
            return None
        # 使用 hmac.compare_digest 做常量时间比较（防御性）
        if not hmac.compare_digest(token, row.token):
            return None
        return self._db_to_record(row)

    def _save_record(self, record: TokenRecord) -> None:
        """保存/更新记录。"""
        if self._use_sqlite:
            self._save_record_db(record)
        else:
            self._store[record.token] = record

    def _save_record_db(self, record: TokenRecord) -> None:
        """将记录写入数据库（upsert，等价于 INSERT OR REPLACE）。"""
        with db.get_sync_session() as session:
            session.merge(self._record_to_db(record))
            session.commit()

    def _delete_record(self, token: str) -> None:
        """从存储中删除记录（仅用于清理过期）。"""
        if self._use_sqlite:
            self._delete_record_db(token)
        else:
            self._store.pop(token, None)

    def _delete_record_db(self, token: str) -> None:
        """从数据库删除记录。"""
        with db.get_sync_session() as session:
            statement = delete(TokenRecordDB).where(TokenRecordDB.token == token)
            session.execute(statement)
            session.commit()

    def _is_expired(self, record: TokenRecord) -> bool:
        """判断记录是否过期。"""
        return self._now() >= self._ensure_aware(record.expires_at)

    # ---- 公共接口 ----

    def generate(self, user_id: int = 0) -> str:
        """生成新的临时 Token，默认有效期 1 小时。"""
        token = secrets.token_urlsafe(self._token_length)
        now = self._now()
        record = TokenRecord(
            token=token,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._default_ttl),
            revoked=False,
            usage_count=0,
        )
        self._save_record(record)
        logger.info("Token 已生成: user_id=%s, ttl=%ds", user_id, self._default_ttl)
        return token

    def verify(self, token: str) -> TokenRecord:
        """
        校验 Token。
        成功返回 TokenRecord；失败抛出 TokenInvalidError / TokenExpiredError / TokenRevokedError。
        """
        if not token:
            raise TokenInvalidError("Token 为空")

        record = self._find_record(token)
        if record is None:
            raise TokenInvalidError("Token 不存在或格式错误")

        if record.revoked:
            raise TokenRevokedError("Token 已被撤销")

        if self._is_expired(record):
            raise TokenExpiredError("Token 已过期")

        # 更新使用信息
        record.last_used_at = self._now()
        record.usage_count += 1
        self._save_record(record)

        return record

    def refresh(self, token: str) -> str:
        """
        刷新 Token：验证旧 Token 有效后，生成新 Token 并撤销旧 Token。
        返回新的 Token 字符串。
        """
        # 先验证旧 Token 有效（可能抛异常）
        old_record = self.verify(token)
        user_id = old_record.user_id

        # 撤销旧 Token
        self.revoke(token)

        # 生成新 Token
        new_token = self.generate(user_id=user_id)
        logger.info("Token 已刷新: 旧 -> 新, user_id=%s", user_id)
        return new_token

    def revoke(self, token: str) -> bool:
        """撤销指定 Token；若 Token 不存在或已撤销返回 False。"""
        record = self._find_record(token)
        if record is None:
            return False

        if record.revoked:
            return False

        record.revoked = True
        self._save_record(record)
        logger.info("Token 已撤销: token=%s", token[:8] + "...")
        return True

    def revoke_all(self, user_id: Optional[int] = None) -> int:
        """
        撤销全部（或指定 user_id 的）未过期 Token。
        返回被撤销的数量。
        """
        count = 0
        if self._use_sqlite:
            count = self._revoke_all_db(user_id)
        else:
            for token, record in list(self._store.items()):
                if user_id is not None and record.user_id != user_id:
                    continue
                if not record.revoked and not self._is_expired(record):
                    record.revoked = True
                    self._store[token] = record
                    count += 1
        logger.info("全量撤销完成: 撤销 %d 个 Token, user_id=%s", count, user_id)
        return count

    def _revoke_all_db(self, user_id: Optional[int] = None) -> int:
        """数据库模式的全量撤销。"""
        now = self._now()
        with db.get_sync_session() as session:
            statement = (
                update(TokenRecordDB)
                .where(
                    TokenRecordDB.revoked == 0,
                    TokenRecordDB.expires_at > now,
                )
                .values(revoked=1)
            )
            if user_id is not None:
                statement = statement.where(TokenRecordDB.user_id == user_id)
            result = session.execute(statement)
            session.commit()
            # SQLite 的 UPDATE rowcount 为实际命中数（>=0）；防御 -1/None
            return max(result.rowcount or 0, 0)

    def is_valid(self, token: str) -> bool:
        """仅做布尔判定，不更新使用次数。"""
        record = self._find_record(token)
        if record is None:
            return False
        if record.revoked:
            return False
        if self._is_expired(record):
            return False
        return True

    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """
        清理已过期超过 max_age_hours 的记录。
        返回清理数量。
        """
        count = 0
        now = self._now()
        cutoff = now - timedelta(hours=max_age_hours)

        if self._use_sqlite:
            count = self._cleanup_expired_db(cutoff)
        else:
            for token, record in list(self._store.items()):
                if self._ensure_aware(record.expires_at) < cutoff:
                    self._store.pop(token, None)
                    count += 1

        logger.info(
            "清理过期 Token: 删除 %d 条记录 (max_age=%dh)", count, max_age_hours
        )
        return count

    def _cleanup_expired_db(self, cutoff: datetime) -> int:
        """数据库模式的过期清理。"""
        with db.get_sync_session() as session:
            statement = delete(TokenRecordDB).where(TokenRecordDB.expires_at < cutoff)
            result = session.execute(statement)
            session.commit()
            return max(result.rowcount, 0)
