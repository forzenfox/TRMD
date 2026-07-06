"""
LoginPage - 登录页Page Object

封装登录页面的交互逻辑，提供稳定的data-testid选择器接口。
"""
from playwright.sync_api import Page
from .base_page import BasePage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


class LoginPage(BasePage):
    """登录页Page Object"""

    # 页面路径
    URL_PATH = "/web/login.html"

    # data-testid常量
    TOKEN_INPUT = "token-input"
    LOGIN_BUTTON = "login-submit-btn"
    ERROR_MESSAGE = "login-error-msg"
    ERROR_TEXT = "login-error-text"
    TOGGLE_PASSWORD = "toggle-password-btn"
    AUTO_LOGIN_HINT = "auto-login-hint"

    def __init__(self, page: Page):
        super().__init__(page)

    def navigate(self, base_url: str, token: str = None) -> None:
        """
        导航到登录页

        Args:
            base_url: 服务基础URL
            token: 可选，URL参数Token用于自动登录
        """
        if token:
            url = f"{base_url}{self.URL_PATH}?token={token}"
        else:
            url = f"{base_url}{self.URL_PATH}"
        self.page.goto(url)

    def goto_dashboard(self, base_url: str) -> None:
        """直接跳转到Dashboard（用于测试Token过期跳转）"""
        self.page.goto(f"{base_url}/web/index.html")

    def fill_token(self, token: str) -> None:
        """填写Token输入框"""
        self.fill_by_testid(self.TOKEN_INPUT, token)

    def clear_token(self) -> None:
        """清空Token输入框"""
        self.fill_by_testid(self.TOKEN_INPUT, "")

    def get_token_value(self) -> str:
        """获取Token输入框的值"""
        return self.get_value_by_testid(self.TOKEN_INPUT)

    def click_login(self) -> None:
        """点击登录按钮"""
        self.click_by_testid(self.LOGIN_BUTTON)

    def login(self, token: str) -> None:
        """
        执行登录操作

        Args:
            token: 认证Token
        """
        self.fill_token(token)
        self.click_login()

    def is_login_button_enabled(self) -> bool:
        """检查登录按钮是否可用"""
        return self.is_enabled_by_testid(self.LOGIN_BUTTON)

    def is_loading(self) -> bool:
        """检查是否在加载状态"""
        return self.is_visible_by_testid(self.AUTO_LOGIN_HINT)

    def has_error(self) -> bool:
        """检查是否有错误提示"""
        return self.is_visible_by_testid(self.ERROR_MESSAGE)

    def get_error_message(self) -> str:
        """获取错误提示文本"""
        if self.has_error():
            return self.get_text_by_testid(self.ERROR_TEXT)
        return ""

    def toggle_password_visibility(self) -> None:
        """切换密码显示/隐藏"""
        self.click_by_testid(self.TOGGLE_PASSWORD)

    def is_token_visible(self) -> bool:
        """检查Token是否可见（非password类型）"""
        input_type = self.page.locator(f'[data-testid="{self.TOKEN_INPUT}"]').get_attribute("type")
        return input_type == "text"

    def wait_for_dashboard(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待跳转到Dashboard"""
        self.wait_for_navigation("**/index.html", timeout)

    def wait_for_login_to_complete(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待登录完成（跳转到Dashboard或显示错误）"""
        # 等待加载状态消失
        self.wait_for_hidden_by_testid(self.AUTO_LOGIN_HINT, timeout)

    def wait_for_error(self, timeout: int = 10000) -> None:
        """等待错误提示出现"""
        self.wait_for_selector(self.ERROR_MESSAGE, timeout)