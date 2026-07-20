# coding=UTF-8
"""配置子包。

提供统一的配置管理接口。
"""

from module.core.config_manager import ConfigManager  # noqa: F401
from module.core.legacy_config import UserConfig, BaseConfig

__all__ = ["ConfigManager", "UserConfig", "BaseConfig"]
