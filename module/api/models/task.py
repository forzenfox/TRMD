# coding=UTF-8
"""任务相关 Pydantic 数据模型。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

TaskType = Literal["download", "forward", "upload"]
TaskStatus = Literal["pending", "queued", "running", "completed", "failed", "cancelled"]
RangeMode = Literal["date_range", "id_range", "multiple_ids", "all"]


class TaskBase(BaseModel):
    """任务基础模型。"""

    task_type: TaskType


class TaskCreate(BaseModel):
    """创建任务请求体。"""

    task_type: TaskType
    params: dict = Field(default_factory=dict)


class TaskOut(BaseModel):
    """任务响应数据。"""

    id: str
    task_type: TaskType
    status: TaskStatus
    progress: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: Optional[str] = None
    success_count: int = 0
    failed_count: int = 0
    total_count: int = 0
    params: dict = Field(default_factory=dict)
