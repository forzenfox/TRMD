# coding=UTF-8
"""核心模块包。

包含 TaskManager、FileManager、TokenManager、CacheManager、Monitor、
RepositoryDB、RepositoryManager 等核心业务组件。

子包结构：
- task/: 任务子系统
- repository/: 仓库子系统
- download/: 下载/上传子系统
- cache/: 缓存子系统
- auth/: 认证子系统
"""

from module.core.monitor import Monitor

__all__ = [
    "TaskManager",
    "FileManager",
    "TokenManager",
    "CacheManager",
    "Monitor",
    "RepositoryDB",
    "RepositoryManager",
]

# 延迟导入，避免 module → module.core → module 的循环依赖
# 导入链：core.__init__ → task/__init__ → executor → config_manager → yaml_utils → path_tool → module(log)
def __getattr__(name):
    _lazy = {
        "TaskManager": "module.core.task",
        "FileManager": "module.core.download.file_manager",
        "TokenManager": "module.core.auth",
        "CacheManager": "module.core.cache",
        "RepositoryDB": "module.core.repository",
        "RepositoryManager": "module.core.repository",
    }
    if name in _lazy:
        import importlib
        mod = importlib.import_module(_lazy[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
