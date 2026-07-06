"""
登录流程E2E测试

覆盖登录成功、Token无效、自动登录、Token过期等场景。
"""
import pytest
from playwright.sync_api import Page

from ..pages.login_page import LoginPage
from ..fixtures.test_config import E2E_SERVER_URL


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    """登录页Page Object fixture"""
    return LoginPage(page)


class TestLoginSuccess:
    """L001: 登录成功场景"""

    def test_valid_token_login_success(
        self, login_page: LoginPage, test_token: str, live_server: str
    ):
        """
        L001: 使用有效Token登录成功

        验证点：
        1. 填写Token后登录按钮变为可用
        2. 点击登录后跳转到Dashboard
        3. 无错误提示
        """
        # 导航到登录页
        login_page.navigate(live_server)

        # 填写Token
        login_page.fill_token(test_token)

        # 验证登录按钮可用
        assert login_page.is_login_button_enabled()

        # 点击登录
        login_page.click_login()

        # 等待跳转到Dashboard
        login_page.wait_for_dashboard()

        # 验证当前URL
        assert "index.html" in login_page.get_current_url()


class TestLoginFailure:
    """L002: Token无效场景"""

    def test_invalid_token_shows_error(
        self, login_page: LoginPage, live_server: str
    ):
        """
        L002: 使用无效Token显示错误提示

        验证点：
        1. 填写无效Token后点击登录
        2. 显示错误提示
        3. 停留在登录页
        """
        # 导航到登录页
        login_page.navigate(live_server)

        # 填写无效Token
        login_page.fill_token("invalid_token_12345")

        # 点击登录
        login_page.click_login()

        # 等待错误提示出现
        login_page.wait_for_error(timeout=15000)

        # 验证错误提示可见
        assert login_page.has_error()

        # 验证错误消息非空
        error_msg = login_page.get_error_message()
        assert len(error_msg) > 0

        # 验证仍停留在登录页
        assert login_page.get_current_url().endswith("login.html")


class TestAutoLogin:
    """L003: 自动登录场景"""

    def test_url_token_auto_login(
        self, login_page: LoginPage, test_token: str, live_server: str
    ):
        """
        L003: URL携带Token参数自动登录

        验证点：
        1. URL携带Token时自动填入输入框
        2. 自动触发登录
        3. 跳转到Dashboard
        """
        # 导航到登录页（携带Token参数）
        login_page.navigate(live_server, token=test_token)

        # 等待自动登录完成
        login_page.wait_for_dashboard()

        # 验证跳转到Dashboard
        assert "index.html" in login_page.get_current_url()


class TestTokenExpiry:
    """L004: Token过期场景"""

    @pytest.mark.skip(reason="需要手动准备过期Token")
    def test_expired_token_redirect_to_login(
        self, login_page: LoginPage, live_server: str
    ):
        """
        L004: Token过期后跳转回登录页

        验证点：
        1. 使用过期Token访问Dashboard
        2. 自动跳转到登录页

        注意：此测试需要手动准备一个过期的Token
        """
        # 直接跳转到Dashboard（使用过期Token在cookie中）
        # 此测试需要特殊fixture提供过期Token
        login_page.goto_dashboard(live_server)

        # 等待跳转到登录页
        login_page.wait_for_navigation("**/login.html")

        # 验证跳转到登录页
        assert "login.html" in login_page.get_current_url()


class TestPasswordToggle:
    """L005: 显示密码场景"""

    def test_toggle_password_visibility(
        self, login_page: LoginPage, live_server: str
    ):
        """
        L005: 点击切换按钮显示/隐藏Token

        验证点：
        1. 默认Token为password类型（隐藏）
        2. 点击切换按钮后变为text类型（显示）
        3. 再次点击恢复password类型（隐藏）
        """
        # 导航到登录页
        login_page.navigate(live_server)

        # 填写Token（用于测试可见性）
        login_page.fill_token("test_token_value")

        # 验证默认隐藏
        assert not login_page.is_token_visible()

        # 点击切换按钮
        login_page.toggle_password_visibility()

        # 等待一小段时间让Alpine.js响应
        login_page.wait_for_timeout(100)

        # 验证Token可见
        assert login_page.is_token_visible()

        # 再次点击切换按钮
        login_page.toggle_password_visibility()

        # 等待响应
        login_page.wait_for_timeout(100)

        # 验证Token再次隐藏
        assert not login_page.is_token_visible()