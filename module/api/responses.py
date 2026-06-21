# coding=UTF-8
"""统一响应格式与响应工具。

提供将业务数据包装为统一 APIResponse 格式的辅助函数。
"""

from typing import Optional, Any

from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "success") -> dict:
    """构造成功响应字典。

    :param data: 响应数据
    :param message: 成功消息
    :return: 统一格式的成功响应
    """
    return {"code": 0, "message": message, "data": data}


def error_response(code: int, message: str, data: Any = None) -> dict:
    """构造错误响应字典。

    :param code: 业务错误码
    :param message: 错误消息
    :param data: 附加数据
    :return: 统一格式的错误响应
    """
    return {"code": code, "message": message, "data": data}


def json_response(
    data: Any = None, message: str = "success", status_code: int = 200
) -> JSONResponse:
    """构造 FastAPI JSONResponse。

    :param data: 响应数据
    :param message: 响应消息
    :param status_code: HTTP 状态码
    :return: JSONResponse 实例
    """
    return JSONResponse(
        status_code=status_code,
        content=success_response(data=data, message=message),
    )


def error_json_response(
    code: int, message: str, data: Any = None, status_code: int = 400
) -> JSONResponse:
    """构造错误 JSONResponse。

    :param code: 业务错误码
    :param message: 错误消息
    :param data: 附加数据
    :param status_code: HTTP 状态码
    :return: JSONResponse 实例
    """
    return JSONResponse(
        status_code=status_code,
        content=error_response(code=code, message=message, data=data),
    )
