# coding=UTF-8
"""通用 Pydantic 数据模型。

定义 API 统一响应格式、分页参数等通用模型。
"""

from typing import Generic, TypeVar, Optional, Any

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。

    所有 REST API 返回统一结构：
    {"code": int, "message": str, "data": T}
    """

    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PaginationParams(BaseModel):
    """分页查询参数。"""

    limit: int = 20
    offset: int = 0


class PaginatedData(BaseModel, Generic[T]):
    """分页数据结构。"""

    items: list[T]
    total: int
    limit: int
    offset: int
