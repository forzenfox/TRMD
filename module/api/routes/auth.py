# coding=UTF-8
"""认证相关路由。

提供 Token 状态检查接口。
"""

import os

from fastapi import APIRouter, Depends, Request

from module.api.dependencies import require_token, get_token_manager
from module.api.responses import json_response
from module.api.models.auth import TokenInfo
from module.core.token_manager import TokenManager

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/me")
async def get_token_status(
    request: Request,
    token: str = Depends(require_token),
    token_manager: TokenManager = Depends(get_token_manager),
):
    """获取当前 Token 状态与过期时间。

    :param request: FastAPI 请求对象
    :param token: 校验通过的 Token
    :param token_manager: Token 管理器
    :return: Token 状态信息
    """
    # 获取 Token 详情
    try:
        record = token_manager.verify(token)
        data = TokenInfo(
            valid=True,
            expires_at=record.expires_at,
            created_at=record.created_at,
            usage_count=record.usage_count,
        )
    except Exception:
        # 如果 verify 抛异常（如已使用），仍然标记为有效
        data = TokenInfo(valid=True)

    # Pydantic model_dump(mode="json") 自动将 datetime 转为 ISO 字符串
    result = data.model_dump(mode="json")
    return json_response(data=result)


@router.post("/refresh")
async def refresh_token(
    request: Request,
    token: str = Depends(require_token),
    token_manager: TokenManager = Depends(get_token_manager),
):
    """刷新 Token，生成新 Token 并撤销旧 Token。

    :param request: FastAPI 请求对象
    :param token: 当前有效 Token
    :param token_manager: Token 管理器
    :return: 新 Token 字符串
    """
    try:
        new_token = token_manager.refresh(token)
        return json_response(data={"token": new_token}, message="Token 已刷新")
    except Exception as e:
        return json_response(
            data=None,
            message=f"Token 刷新失败: {str(e)}",
            status_code=400,
        )


@router.post("/e2e_token")
async def generate_e2e_token(request: Request):
    """E2E测试专用Token生成端点。

    仅在 TRMD_E2E_TEST=1 环境变量时可用。
    生产环境完全不可用。

    :param request: FastAPI 请求对象
    :return: 生成的Token信息
    """
    # 安全检查：仅E2E测试模式可用
    if os.environ.get("TRMD_E2E_TEST") != "1":
        return json_response(
            data=None,
            message="此端点仅E2E测试模式可用",
            status_code=403,
        )

    token_manager: TokenManager = request.app.state.token_manager
    token = token_manager.generate(user_id=0)

    # 获取Token详情
    record = token_manager.verify(token)

    return json_response(
        data={
            "token": token,
            "expires_at": record.expires_at.isoformat(),
            "ttl_hours": token_manager._default_ttl / 3600,
        },
        message="E2E测试Token已生成",
    )
