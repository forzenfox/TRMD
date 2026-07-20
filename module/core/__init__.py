# coding=UTF-8
"""核心模块包。

包含 TaskManager、FileManager、TokenManager、CacheManager、Monitor、
RepositoryDB、RepositoryManager 等核心业务组件。
"""

from module.core.task_manager import TaskManager
from module.core.token_manager import TokenManager
from module.core.cache_manager import CacheManager
from module.core.monitor import Monitor
from module.core.repository_db import RepositoryDB
from module.core.repository_manager import RepositoryManager

# FileManager 延迟导入，避免 module → module.core → module 的循环依赖
def __getattr__(name):
    if name == "FileManager":
        from module.core.file_manager import FileManager
        return FileManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TaskManager",
    "FileManager",
    "TokenManager",
    "CacheManager",
    "Monitor",
    "RepositoryDB",
    "RepositoryManager",
]
