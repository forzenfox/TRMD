# coding=UTF-8
"""Token 认证管理模块。

负责 Token 的生成、验证、刷新、撤销、过期清理与持久化。
详见 `docs/module-design-token-auth.md`。
"""

import hmac
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass(slots=True)
class TokenRecord:
    """Token 运行时记录。"""

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
    """临时 Token 生命周期管理器。"""

    # SQLite 建表语句
    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS tokens (
            token           TEXT PRIMARY KEY,
            user_id         INTEGER NOT NULL DEFAULT 0,
            created_at      REAL    NOT NULL,
            expires_at      REAL    NOT NULL,
            last_used_at    REAL,
            revoked         INTEGER NOT NULL DEFAULT 0,
            usage_count     INTEGER NOT NULL DEFAULT 0
        );
    """

    _INDEX_EXPIRES_AT = (
        "CREATE INDEX IF NOT EXISTS idx_tokens_expires_at ON tokens(expires_at);"
    )
    _INDEX_REVOKED = "CREATE INDEX IF NOT EXISTS idx_tokens_revoked ON tokens(revoked);"

    def __init__(
        self,
        db_path: Optional[str] = None,
        default_ttl: int = 3600,
        token_length: int = 32,
    ) -> None:
        """
        :param db_path: SQLite 文件路径；若为 None，则回退到内存字典。
        :param default_ttl: Token 默认有效期，单位秒，默认 1 小时。
        :param token_length: secrets.token_urlsafe 长度参数。
        """
        self._default_ttl = default_ttl
        self._token_length = token_length
        self._use_sqlite = db_path is not None

        if self._use_sqlite:
            self._db_path = db_path
            self._init_sqlite()
        else:
            # 内存字典：token -> TokenRecord
            self._store: dict[str, TokenRecord] = {}

    # ---- SQLite 初始化 ----

    def _init_sqlite(self) -> None:
        """初始化 SQLite 数据库并创建表结构。"""
        conn = self._get_connection()
        try:
            conn.execute(self._CREATE_TABLE_SQL)
            conn.execute(self._INDEX_EXPIRES_AT)
            conn.execute(self._INDEX_REVOKED)
            conn.commit()
        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """获取 SQLite 连接（线程安全模式）。"""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    # ---- 内部辅助方法 ----

    def _now(self) -> datetime:
        """获取当前 UTC 时间。"""
        return datetime.now(timezone.utc)

    def _now_ts(self) -> float:
        """获取当前 UTC Unix 时间戳（秒）。"""
        return self._now().timestamp()

    def _to_datetime(self, ts: float) -> datetime:
        """将 Unix 时间戳转换为 UTC datetime。"""
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    def _record_to_row(self, record: TokenRecord) -> tuple:
        """将 TokenRecord 转换为 SQLite 行元组。"""
        return (
            record.token,
            record.user_id,
            record.created_at.timestamp(),
            record.expires_at.timestamp(),
            record.last_used_at.timestamp() if record.last_used_at else None,
            1 if record.revoked else 0,
            record.usage_count,
        )

    def _row_to_record(self, row: tuple) -> TokenRecord:
        """将 SQLite 行元组转换为 TokenRecord。"""
        return TokenRecord(
            token=row[0],
            user_id=row[1],
            created_at=self._to_datetime(row[2]),
            expires_at=self._to_datetime(row[3]),
            last_used_at=self._to_datetime(row[4]) if row[4] is not None else None,
            revoked=bool(row[5]),
            usage_count=row[6],
        )

    def _find_record(self, token: str) -> Optional[TokenRecord]:
        """根据 Token 查找记录。"""
        if self._use_sqlite:
            return self._find_record_sqlite(token)
        return self._store.get(token)

    def _find_record_sqlite(self, token: str) -> Optional[TokenRecord]:
        """从 SQLite 查找记录，使用常量时间比较。"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,))
            row = cursor.fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        # 使用 hmac.compare_digest 做常量时间比较
        stored_token = row[0]
        if not hmac.compare_digest(token, stored_token):
            return None
        return self._row_to_record(row)

    def _save_record(self, record: TokenRecord) -> None:
        """保存/更新记录。"""
        if self._use_sqlite:
            self._save_record_sqlite(record)
        else:
            self._store[record.token] = record

    def _save_record_sqlite(self, record: TokenRecord) -> None:
        """将记录写入 SQLite（INSERT OR REPLACE）。"""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tokens
                    (token, user_id, created_at, expires_at, last_used_at, revoked, usage_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._record_to_row(record),
            )
            conn.commit()
        finally:
            conn.close()

    def _delete_record(self, token: str) -> None:
        """从存储中删除记录（仅用于清理过期）。"""
        if self._use_sqlite:
            self._delete_record_sqlite(token)
        else:
            self._store.pop(token, None)

    def _delete_record_sqlite(self, token: str) -> None:
        """从 SQLite 删除记录。"""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()

    def _is_expired(self, record: TokenRecord) -> bool:
        """判断记录是否过期。"""
        return self._now() >= record.expires_at

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
            count = self._revoke_all_sqlite(user_id)
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

    def _revoke_all_sqlite(self, user_id: Optional[int] = None) -> int:
        """SQLite 模式的全量撤销。"""
        now_ts = self._now_ts()
        conn = self._get_connection()
        try:
            if user_id is not None:
                cursor = conn.execute(
                    """
                    UPDATE tokens SET revoked = 1
                    WHERE user_id = ? AND revoked = 0 AND expires_at > ?
                    """,
                    (user_id, now_ts),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE tokens SET revoked = 1
                    WHERE revoked = 0 AND expires_at > ?
                    """,
                    (now_ts,),
                )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

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
        cutoff_ts = (now - timedelta(hours=max_age_hours)).timestamp()

        if self._use_sqlite:
            count = self._cleanup_expired_sqlite(cutoff_ts)
        else:
            for token, record in list(self._store.items()):
                if record.expires_at.timestamp() < cutoff_ts:
                    self._store.pop(token, None)
                    count += 1

        logger.info(
            "清理过期 Token: 删除 %d 条记录 (max_age=%dh)", count, max_age_hours
        )
        return count

    def _cleanup_expired_sqlite(self, cutoff_ts: float) -> int:
        """SQLite 模式的过期清理。"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM tokens WHERE expires_at < ?", (cutoff_ts,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
