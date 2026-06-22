# coding=UTF-8
"""日志配置模块。

从 module/__init__.py 提取的日志初始化逻辑。
"""

import logging
import os
from logging.handlers import RotatingFileHandler

import yaml
from rich.console import Console
from rich.logging import RichHandler

from module.constants import (
    LOG_PATH,
    MAX_LOG_SIZE,
    BACKUP_COUNT,
    LOG_FORMAT,
    LOG_TIME_FORMAT,
    GLOBAL_CONFIG_PATH,
    SOFTWARE_SHORT_NAME,
    __version__,
    __update_date__,
)


def via_log_level(
    log_level: str, param_name: str, default_level: int = logging.INFO
) -> bool:
    """验证日志级别是否有效。"""
    valid_levels = [
        "CRITICAL",
        "FATAL",
        "ERROR",
        "WARN",
        "WARNING",
        "INFO",
        "DEBUG",
        "NOTSET",
    ]
    return log_level in valid_levels


class CustomDumper(yaml.Dumper):
    """自定义 YAML Dumper，将 None 表示为 ~。"""

    def represent_none(self, data):
        return self.represent_scalar("tag:yaml.org,2002:null", "~")


# 初始化日志级别（从配置文件读取）
FILE_LOG_LEVEL: int = logging.INFO
CONSOLE_LOG_LEVEL: int = logging.WARNING


def _load_log_levels_from_config():
    """从 config.yaml 的 log 分组读取日志级别。

    优先级：
    1. 工作目录下的 config.yaml 的 log 分组
    2. 工作目录下的 .CONFIG.yaml
    3. 默认值 INFO / WARNING
    """
    global FILE_LOG_LEVEL, CONSOLE_LOG_LEVEL

    # 尝试从 config.yaml 的 log 分组读取
    config_yaml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "config.yaml"
    )
    config_yaml_path = os.path.normpath(config_yaml_path)
    if os.path.exists(config_yaml_path):
        try:
            with open(file=config_yaml_path, mode="r", encoding="UTF-8") as f:
                config_data = yaml.safe_load(f)
            if config_data and isinstance(config_data, dict):
                log_section = config_data.get("log", {})
                if isinstance(log_section, dict):
                    file_log_level = log_section.get("file_log_level")
                    console_log_level = log_section.get("console_log_level")
                    if file_log_level and via_log_level(
                        file_log_level, "file_log_level", logging.INFO
                    ):
                        FILE_LOG_LEVEL = logging.getLevelName(file_log_level)
                    if console_log_level and via_log_level(
                        console_log_level, "console_log_level", logging.WARNING
                    ):
                        CONSOLE_LOG_LEVEL = logging.getLevelName(console_log_level)
                    return
        except Exception:
            pass

    # 回退：从旧的 .CONFIG.yaml 读取（向后兼容）
    if os.path.exists(GLOBAL_CONFIG_PATH):
        try:
            with open(file=GLOBAL_CONFIG_PATH, mode="r", encoding="UTF-8") as f:
                global_config = yaml.safe_load(f)
            if global_config and isinstance(global_config, dict):
                file_log_level = global_config.get("file_log_level")
                console_log_level = global_config.get("console_log_level")
                if file_log_level and via_log_level(
                    file_log_level, "file_log_level", logging.INFO
                ):
                    FILE_LOG_LEVEL = logging.getLevelName(file_log_level)
                if console_log_level and via_log_level(
                    console_log_level, "console_log_level", logging.WARNING
                ):
                    CONSOLE_LOG_LEVEL = logging.getLevelName(console_log_level)
        except Exception:
            pass


# 加载日志级别
_load_log_levels_from_config()

# 创建控制台
console = Console(log_path=False, log_time_format=LOG_TIME_FORMAT)

# 配置文件处理器
file_handler = RotatingFileHandler(
    filename=LOG_PATH, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding="UTF-8"
)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)-8s" + " " + LOG_FORMAT, datefmt=LOG_TIME_FORMAT
    )
)
file_handler.setLevel(logging.getLevelName(FILE_LOG_LEVEL))

# 配置控制台处理器
console_handler = RichHandler(
    level=CONSOLE_LOG_LEVEL,
    console=console,
    rich_tracebacks=True,
    show_path=False,
    omit_repeated_times=True,
    log_time_format=LOG_TIME_FORMAT,
)

# 配置根日志记录器
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=LOG_TIME_FORMAT,
    handlers=[console_handler, file_handler],
)

# 创建主日志记录器
log = logging.getLogger("rich")
# 抑制 Pyrogram 的 INFO 级别日志
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log.info(f"{SOFTWARE_SHORT_NAME}:{__version__},更新日期:{__update_date__}。")
log.info(f'文件日志等级:"{logging.getLevelName(FILE_LOG_LEVEL)}"。')
log.info(f'终端日志等级:"{logging.getLevelName(CONSOLE_LOG_LEVEL)}"。')

# 注册自定义 Dumper
CustomDumper.add_representer(type(None), CustomDumper.represent_none)
