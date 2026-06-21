# coding=UTF-8
"""全局常量定义。

从 module/__init__.py 提取的全局常量、路径和版本信息。
"""

import os
import atexit
import platform

from pyrogram.types.messages_and_media import LinkPreviewOptions


def read_input_history(history_path: str, max_record_len: int, **kwargs) -> None:
    if kwargs.get("platform") == "Windows":
        import readline

        readline.backend = "readline"
        try:
            readline.read_history_file(history_path)
        except FileNotFoundError:
            pass
        readline.set_history_length(max_record_len)
        atexit.register(readline.write_history_file, history_path)


# 版本与作者
AUTHOR = "Gentlesprite"
__version__ = "2.0.0"
__license__ = "MIT License"
__update_date__ = "2026/03/30 18:17:53"
__copyright__ = f"Copyright (C) 2024-{__update_date__[:4]} {AUTHOR} <https://github.com/Gentlesprite>"

# 软件名称
SOFTWARE_FULL_NAME = "Telegram Restricted Media Downloader"
SOFTWARE_SHORT_NAME = "TRMD"

# 路径常量
APPDATA_PATH = os.path.join(
    os.environ.get("APPDATA")
    or os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    SOFTWARE_SHORT_NAME,
)
GLOBAL_CONFIG_NAME = ".CONFIG.yaml"
GLOBAL_CONFIG_PATH = os.path.join(APPDATA_PATH, GLOBAL_CONFIG_NAME)
PLATFORM = platform.system()
os.makedirs(APPDATA_PATH, exist_ok=True)
INPUT_HISTORY_PATH = os.path.join(APPDATA_PATH, f".{SOFTWARE_SHORT_NAME}_HISTORY")
MAX_RECORD_LENGTH = 1000

# 执行副作用：读取输入历史
read_input_history(
    history_path=INPUT_HISTORY_PATH, max_record_len=MAX_RECORD_LENGTH, platform=PLATFORM
)

# 日志相关常量
LOG_PATH = os.path.join(APPDATA_PATH, f"{SOFTWARE_SHORT_NAME}_LOG.log")
MAX_LOG_SIZE = 200 * 1024 * 1024  # 200MB
BACKUP_COUNT = 0  # 不保留日志文件
LOG_FORMAT = "%(name)s:%(funcName)s:%(lineno)d - %(message)s"
LOG_TIME_FORMAT = "[%Y-%m-%d %H:%M:%S]"
SLEEP_THRESHOLD = 60
LINK_PREVIEW_OPTIONS = LinkPreviewOptions(is_disabled=True)
