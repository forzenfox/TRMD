# coding=UTF-8
"""文件相关 Pydantic 数据模型。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class FileInfo(BaseModel):
    """单个文件/目录信息。"""

    name: str
    path: str
    type: Literal["file", "directory"]
    size: Optional[int] = None
    modified_at: Optional[str] = None


class FileListOut(BaseModel):
    """文件列表响应数据。"""

    path: str
    items: list[FileInfo]
