"""
Page Object模块

封装页面交互逻辑，提供稳定的data-testid选择器接口。
"""

from .base_page import BasePage
from .config_page import ConfigPage
from .login_page import LoginPage

__all__ = ["BasePage", "ConfigPage", "LoginPage"]
