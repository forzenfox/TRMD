# coding=UTF-8
"""依赖注入：Token 校验、核心管理器获取。

所有受保护的 REST API 端点统一使用 require_token 依赖进行认证。
"""

from fastapi import Header, Query, HTTPException, status, Request
from typing import Optional

from module.core.token_manager import TokenManager


# ==================== 认证依赖 ====================


async def require_token(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token_query: Optional[str] = Query(None, alias="token"),
) -> str:
    """校验请求中的 Token。

    支持两种传递方式：
    1. HTTP Header: `Authorization: Bearer <token>`
    2. URL Query: `?token=<token>`

    :param authorization: 认证头
    :param token_query: URL 参数 token
    :return: 校验通过后的 Token 字符串
    :raises HTTPException: Token 缺失或无效时抛出 401
    """
    raw = authorization or token_query
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MISSING_TOKEN",
        )

    # 提取 Bearer Token
    token = (
        raw.removeprefix("Bearer ").strip()
        if raw.startswith("Bearer ")
        else raw.strip()
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MISSING_TOKEN",
        )

    # 从应用状态获取 TokenManager
    token_manager: TokenManager = request.app.state.token_manager
    if not token_manager.is_valid(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_OR_EXPIRED_TOKEN",
        )

    return token


# ==================== 核心管理器依赖 ====================


def get_token_manager(request: Request) -> TokenManager:
    """获取 TokenManager 实例。"""
    return request.app.state.token_manager


def get_task_manager(request: Request):
    """获取 TaskManager 实例。"""
    return request.app.state.task_manager


def get_file_manager(request: Request):
    """获取 FileManager 实例。"""
    return request.app.state.file_manager


def get_config_manager(request: Request):
    """获取配置管理器实例。"""
    cm = request.app.state.config_manager
    if cm is None:
        # 延迟导入，避免循环依赖
        from module.config.config_manager import ConfigManager

        cm = ConfigManager()
        request.app.state.config_manager = cm
    return cm


def get_monitor(request: Request):
    """获取 Monitor 实例。"""
    return getattr(request.app.state, "monitor", None)
