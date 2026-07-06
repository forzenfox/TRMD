"""
Page Object模块

封装页面交互逻辑，提供稳定的data-testid选择器接口。
"""
from .base_page import BasePage
from .login_page import LoginPage

__all__ = ["BasePage", "LoginPage"]