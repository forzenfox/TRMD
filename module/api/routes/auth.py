# coding=UTF-8
"""认证相关路由。

提供 Token 状态检查接口。
"""

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

    # 将 datetime 转为 ISO 字符串以便 JSON 序列化
    result = data.model_dump()
    for key in ["expires_at", "created_at"]:
        if key in result and result[key] is not None:
            val = result[key]
            if hasattr(val, "isoformat"):
                result[key] = val.isoformat()
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
