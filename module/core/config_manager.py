# coding=UTF-8
"""向后兼容 shim - 实际实现已移至 module.config.config_manager"""

from module.config.config_manager import *  # noqa: F401,F403
from module.config.config_manager import (
    ConfigManager,
    ConfigManagerError,
    ConfigValidationError,
)  # noqa: F401
