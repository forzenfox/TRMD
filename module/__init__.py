# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/11/18 12:28:18
# File:__init__.py
"""
模块初始化文件。

作为 re-export 层，保持向后兼容性。
实际实现已迁移到以下模块：
- module.core.constants: 全局常量
- module.core.logging_config: 日志配置
- module.core.config_template: 配置模板
"""

# Re-export 所有公开接口以保持向后兼容
from module.core.constants import (
    AUTHOR,
    SOFTWARE_FULL_NAME,
    SOFTWARE_SHORT_NAME,
    WORK_DIR,
    PLATFORM,
    INPUT_HISTORY_PATH,
    MAX_RECORD_LENGTH,
    LOG_PATH,
    MAX_LOG_SIZE,
    BACKUP_COUNT,
    LOG_FORMAT,
    LOG_TIME_FORMAT,
    SLEEP_THRESHOLD,
    LINK_PREVIEW_OPTIONS,
    __version__,
    __license__,
    __update_date__,
    __copyright__,
)

from module.core.logging_config import (
    console,
    log,
    file_handler,
    console_handler,
    FILE_LOG_LEVEL,
    CONSOLE_LOG_LEVEL,
    CustomDumper,
    via_log_level,
)

from module.core.config_template import README

__all__ = [
    # 常量
    "AUTHOR",
    "SOFTWARE_FULL_NAME",
    "SOFTWARE_SHORT_NAME",
    "WORK_DIR",
    "PLATFORM",
    "INPUT_HISTORY_PATH",
    "MAX_RECORD_LENGTH",
    "LOG_PATH",
    "MAX_LOG_SIZE",
    "BACKUP_COUNT",
    "LOG_FORMAT",
    "LOG_TIME_FORMAT",
    "SLEEP_THRESHOLD",
    "LINK_PREVIEW_OPTIONS",
    "__version__",
    "__license__",
    "__update_date__",
    "__copyright__",
    # 日志
    "console",
    "log",
    "file_handler",
    "console_handler",
    "FILE_LOG_LEVEL",
    "CONSOLE_LOG_LEVEL",
    "CustomDumper",
    "via_log_level",
    # 配置
    "README",
]
