# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/11/18 12:28:18
# File:__init__.py
"""
模块初始化文件。

作为 re-export 层，保持向后兼容性。
实际实现已拆分到以下模块：
- constants.py: 全局常量
- logging_config.py: 日志配置
- config_template.py: 配置模板
"""

# Re-export 所有公开接口以保持向后兼容
from module.constants import (
    AUTHOR,
    SOFTWARE_FULL_NAME,
    SOFTWARE_SHORT_NAME,
    WORK_DIR,
    GLOBAL_CONFIG_NAME,
    GLOBAL_CONFIG_PATH,
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

from module.logging_config import (
    console,
    log,
    file_handler,
    console_handler,
    FILE_LOG_LEVEL,
    CONSOLE_LOG_LEVEL,
    CustomDumper,
    via_log_level,
)

from module.config_template import README

# 保留全局配置变量（向后兼容）
import yaml
import os

if os.path.exists(GLOBAL_CONFIG_PATH):
    try:
        with open(file=GLOBAL_CONFIG_PATH, mode="r", encoding="UTF-8") as f:
            global_config = yaml.safe_load(f)
    except Exception:
        global_config = {}
else:
    global_config = {}

__all__ = [
    # 常量
    "AUTHOR",
    "SOFTWARE_FULL_NAME",
    "SOFTWARE_SHORT_NAME",
    "WORK_DIR",
    "GLOBAL_CONFIG_NAME",
    "GLOBAL_CONFIG_PATH",
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
    "global_config",
]
