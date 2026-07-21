# coding=UTF-8
"""任务子系统。"""

from module.core.task.manager import (
    Task,
    TaskItem,
    TaskType,
    TaskStatus,
    ItemStatus,
    TaskManager,
    TaskManagerError,
    TaskNotFoundError,
    TaskConflictError,
    TaskStateError,
    ExecutorError,
    ValidationError,
    ResourceLimitError,
)
from module.core.task.models import TaskItemRecord, TaskRecord
from module.core.task.legacy import DownloadTask, UploadTask

# TaskExecutor 延迟导入，避免循环依赖链：
# task.__init__ → executor → config_manager → yaml_utils → path_tool → module(log)
def __getattr__(name):
    if name == "TaskExecutor":
        from module.core.task.executor import TaskExecutor
        return TaskExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Task",
    "TaskItem",
    "TaskType",
    "TaskStatus",
    "ItemStatus",
    "TaskManager",
    "TaskManagerError",
    "TaskNotFoundError",
    "TaskConflictError",
    "TaskStateError",
    "ExecutorError",
    "ValidationError",
    "ResourceLimitError",
    "TaskExecutor",
    "TaskItemRecord",
    "TaskRecord",
    "DownloadTask",
    "UploadTask",
]
