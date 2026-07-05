# coding=UTF-8
"""IdentifierService - 统一对话标识符解析服务。

将 username、chat_id、t.me 链接统一解析为标准化对话信息，
供 WebUI、Bot 命令与任务管理层复用。
"""

import re
import asyncio
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import pyrogram

from module.utils.helpers import extract_info_from_link


# ============================================================
# 枚举定义
# ============================================================


class IdentifierFormat(Enum):
    """标识符输入格式。"""

    NUMERIC_ID = auto()  # 纯数字 ID（支持负数）
    AT_USERNAME = auto()  # @username
    BARE_USERNAME = auto()  # 裸 username
    T_ME_LINK = auto()  # https://t.me/username 或 t.me/username
    INVALID = auto()  # 无法识别的格式


# ============================================================
# 数据模型
# ============================================================


@dataclass(frozen=True, slots=True)
class ResolvedChat:
    """IdentifierService 解析后的标准化对话信息。"""

    chat_id: int  # 数字 ID（可为负数）
    chat_type: str  # "bot" | "private" | "channel" | "group" | "supergroup"
    chat_name: str  # 显示名称
    username: Optional[str]  # 用户名（无 username 为 None）
    message_count: int  # 消息总数估算（-1 表示未获取）
    media_count: int  # 媒体消息数估算（-1 表示未获取）
    has_access: bool  # 当前用户是否可访问该对话
    is_private: bool  # 是否为私聊类型（bot / private）


# ============================================================
# 异常体系
# ============================================================


class IdentifierServiceError(Exception):
    """IdentifierService 基础异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        retry_after: Optional[int] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)


class InvalidIdentifierError(IdentifierServiceError):
    """标识符格式无效。"""

    def __init__(self, message: str = "标识符格式不正确"):
        super().__init__("INVALID_IDENTIFIER", message, 400)


class UserNotFoundError(IdentifierServiceError):
    """用户名/ID 对应的对话不存在。"""

    def __init__(self, message: str = "无法找到该用户/频道"):
        super().__init__("USER_NOT_FOUND", message, 404)


class AccessDeniedError(IdentifierServiceError):
    """无权限访问该对话。"""

    def __init__(self, message: str = "您尚未与此用户建立对话"):
        super().__init__("ACCESS_DENIED", message, 403)


class ResolveTimeoutError(IdentifierServiceError):
    """解析请求超时。"""

    def __init__(self, message: str = "解析请求超时，请重试"):
        super().__init__("RESOLVE_TIMEOUT", message, 504)


class ClientNotConnectedError(IdentifierServiceError):
    """Telegram Client 未连接。"""

    def __init__(self, message: str = "Telegram client not connected"):
        super().__init__("CLIENT_NOT_CONNECTED", message, 503)


class RateLimitedError(IdentifierServiceError):
    """触发 Telegram FloodWait。"""

    def __init__(self, retry_after: int, message: str = "请求过于频繁，请稍后再试"):
        super().__init__("RATE_LIMITED", message, 429, retry_after=retry_after)


# ============================================================
# 服务实现
# ============================================================


class IdentifierService:
    """统一对话标识符解析服务。"""

    # Telegram username 规则：5-32 个字符，只能包含字母、数字、下划线
    _USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{5,32}$")
    # 纯数字 ID（支持负数）
    _NUMERIC_ID_RE = re.compile(r"^-?\d+$")
    # t.me 链接，path 只能有一段（即只接受对话主页，不接受消息链接）
    _T_ME_LINK_RE = re.compile(r"^https?://(www\.)?t\.me/([a-zA-Z0-9_+\-]{5,100})$")
    # 无 scheme 的 t.me 链接
    _T_ME_LINK_NO_SCHEME_RE = re.compile(r"^t\.me/([a-zA-Z0-9_+\-]{5,100})$")

    def __init__(self, client: Optional[pyrogram.Client]):
        """
        :param client: 已启动且已授权的 Pyrogram Client 实例；测试场景允许为 None，
                       实际调用 resolve() 时会抛出 ClientNotConnectedError。
        """
        self._client = client

    @staticmethod
    def _detect_format(identifier: str) -> IdentifierFormat:
        """检测输入字符串属于哪种标识符格式（不发起网络请求）。"""
        text = (identifier or "").strip()
        if not text:
            return IdentifierFormat.INVALID

        # 纯数字 ID
        if IdentifierService._NUMERIC_ID_RE.match(text):
            return IdentifierFormat.NUMERIC_ID

        # @username
        if text.startswith("@") and IdentifierService._USERNAME_RE.match(text[1:]):
            return IdentifierFormat.AT_USERNAME

        # t.me 链接（无 post_id）
        if IdentifierService._T_ME_LINK_RE.match(
            text
        ) or IdentifierService._T_ME_LINK_NO_SCHEME_RE.match(text):
            return IdentifierFormat.T_ME_LINK

        # 裸 username
        if IdentifierService._USERNAME_RE.match(text):
            return IdentifierFormat.BARE_USERNAME

        return IdentifierFormat.INVALID

    @staticmethod
    def _normalize(identifier: str, fmt: IdentifierFormat) -> str | int:
        """将标识符清洗为可直接传给 client.get_chat() 的值。"""
        text = identifier.strip()

        if fmt == IdentifierFormat.NUMERIC_ID:
            return int(text)

        if fmt == IdentifierFormat.AT_USERNAME:
            return text[1:]

        if fmt == IdentifierFormat.BARE_USERNAME:
            return text

        if fmt == IdentifierFormat.T_ME_LINK:
            # 无 scheme 的 t.me 链接需要补全，否则 urlparse 会错误解析
            link_to_parse = text if text.startswith("http") else f"https://{text}"
            parsed = extract_info_from_link(link_to_parse)
            group_id = parsed.group_id
            if group_id is None:
                raise InvalidIdentifierError(f"无法从链接中提取频道标识: {text}")
            if isinstance(group_id, str) and group_id.startswith("+"):
                # 私有频道邀请链接需要完整 URL
                return f"https://t.me/{group_id}"
            return group_id

        raise InvalidIdentifierError(f"无法规范化的标识符格式: {text}")

    async def resolve(self, identifier: str) -> ResolvedChat:
        """将任意支持的标识符解析为 ResolvedChat。

        :param identifier: 用户输入的标识符字符串。
        :return: ResolvedChat 对象。
        :raises InvalidIdentifierError: 输入格式无效。
        :raises UserNotFoundError: 用户名/ID 对应的对话不存在。
        :raises AccessDeniedError: 无权限访问该对话。
        :raises RateLimitedError: 触发 FloodWait。
        :raises ResolveTimeoutError: Telegram API 调用超时。
        """
        fmt = self._detect_format(identifier)
        if fmt == IdentifierFormat.INVALID:
            raise InvalidIdentifierError()

        if self._client is None:
            raise ClientNotConnectedError()

        query = self._normalize(identifier, fmt)

        try:
            chat = await self._client.get_chat(query)
        except asyncio.TimeoutError:
            raise ResolveTimeoutError()
        except Exception as e:
            raise self._map_exception(e)

        return self._chat_to_resolved(chat)

    def _map_exception(self, exc: Exception) -> IdentifierServiceError:
        """将 Pyrogram / 网络异常映射为 IdentifierServiceError。"""
        exc_module = exc.__class__.__module__
        exc_name = exc.__class__.__name__
        full_name = f"{exc_module}.{exc_name}" if exc_module else exc_name

        # 未找到
        if exc_name in (
            "UsernameNotOccupied",
            "PeerIdInvalid",
            "UsernameInvalid",
            "UserNotFound",
        ):
            return UserNotFoundError()

        # 无权限
        if exc_name in (
            "ChatForbidden",
            "UserPrivacyRestricted",
            "ChannelPrivate",
            "ChannelInvalid",
        ):
            return AccessDeniedError()

        # 限流
        if exc_name == "FloodWait":
            retry_after = getattr(exc, "value", None)
            if retry_after is None:
                retry_after = getattr(exc, "retry_after", None)
            if retry_after is None:
                retry_after = 0
            return RateLimitedError(retry_after=int(retry_after))

        # 超时（部分 Pyrogram 版本使用 TimeoutError 子类）
        if "TimeoutError" in exc_name or isinstance(exc, asyncio.TimeoutError):
            return ResolveTimeoutError()

        # 兜底：记录未预期异常并返回 500
        return IdentifierServiceError(
            code="RESOLVE_ERROR",
            message=f"解析失败: {full_name}: {exc}",
            status_code=500,
        )

    def _chat_to_resolved(self, chat) -> ResolvedChat:
        """将 Pyrogram Chat 对象转换为 ResolvedChat。"""
        chat_id = int(chat.id)
        raw_type = chat.type.value if chat.type else "unknown"

        # 私聊中的 Bot 特殊标记为 "bot"
        is_bot_private = raw_type == "private" and getattr(chat, "is_bot", False)
        chat_type = "bot" if is_bot_private else raw_type

        # 名称推导
        chat_name = chat.title
        if not chat_name:
            first = getattr(chat, "first_name", None) or ""
            last = getattr(chat, "last_name", None) or ""
            chat_name = (first + " " + last).strip()
        if not chat_name:
            chat_name = getattr(chat, "username", None)
        if not chat_name:
            chat_name = f"chat_{chat_id}"

        username = getattr(chat, "username", None)
        is_private = chat_type in {"bot", "private"}

        return ResolvedChat(
            chat_id=chat_id,
            chat_type=chat_type,
            chat_name=chat_name,
            username=username,
            message_count=-1,
            media_count=-1,
            has_access=True,
            is_private=is_private,
        )
