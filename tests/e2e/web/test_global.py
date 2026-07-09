"""
全局/共享组件E2E测试

覆盖侧边栏导航、退出登录、通知系统等跨页面共享组件场景。
"""

import pytest
from playwright.sync_api import Page

from ..pages.dashboard_page import DashboardPage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


@pytest.fixture
def dashboard_page(authenticated_page: Page) -> DashboardPage:
    """Dashboard页Page Object fixture（已认证）"""
    return DashboardPage(authenticated_page)


class TestSidebarNavigation:
    """G001: 侧边栏导航场景"""

    def test_sidebar_navigation_tasks(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        G001-1: 在Dashboard页点击侧边栏"任务管理"跳转到tasks.html

        验证点：
        1. 在Dashboard页面
        2. 点击侧边栏"任务管理"链接
        3. 跳转到tasks.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 点击侧边栏"任务管理"链接
        tasks_link = dashboard_page.page.locator("a.sidebar-link[href='tasks.html']")
        tasks_link.click()

        # 等待页面跳转
        dashboard_page.wait_for_navigation("**/tasks.html", timeout=NAVIGATION_TIMEOUT)

        # 验证URL包含tasks.html
        current_url = dashboard_page.get_current_url()
        assert "tasks.html" in current_url

    def test_sidebar_navigation_files(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        G001-2: 点击"文件管理"跳转到files.html

        验证点：
        1. 在Dashboard页面
        2. 点击侧边栏"文件管理"链接
        3. 跳转到files.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 点击侧边栏"文件管理"链接
        files_link = dashboard_page.page.locator("a.sidebar-link[href='files.html']")
        files_link.click()

        # 等待页面跳转
        dashboard_page.wait_for_navigation("**/files.html", timeout=NAVIGATION_TIMEOUT)

        # 验证URL包含files.html
        current_url = dashboard_page.get_current_url()
        assert "files.html" in current_url

    def test_sidebar_navigation_config(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        G001-3: 点击"系统配置"跳转到config.html

        验证点：
        1. 在Dashboard页面
        2. 点击侧边栏"系统配置"链接
        3. 跳转到config.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 点击侧边栏"系统配置"链接
        config_link = dashboard_page.page.locator("a.sidebar-link[href='config.html']")
        config_link.click()

        # 等待页面跳转
        dashboard_page.wait_for_navigation("**/config.html", timeout=NAVIGATION_TIMEOUT)

        # 验证URL包含config.html
        current_url = dashboard_page.get_current_url()
        assert "config.html" in current_url

    def test_sidebar_navigation_dashboard(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        G001-4: 在其他页点击"Dashboard"跳转到index.html

        验证点：
        1. 先导航到任务管理页（非Dashboard页）
        2. 点击侧边栏"Dashboard"链接
        3. 跳转到index.html
        """
        # 先导航到任务管理页（非Dashboard）
        dashboard_page.page.goto(f"{live_server}/web/tasks.html")
        try:
            dashboard_page.page.wait_for_load_state(
                "networkidle", timeout=NAVIGATION_TIMEOUT
            )
        except Exception:
            pass

        # 点击侧边栏"Dashboard"链接
        dashboard_link = dashboard_page.page.locator(
            "a.sidebar-link[href='index.html']"
        )
        dashboard_link.click()

        # 等待页面跳转
        dashboard_page.wait_for_navigation("**/index.html", timeout=NAVIGATION_TIMEOUT)

        # 验证URL包含index.html
        current_url = dashboard_page.get_current_url()
        assert "index.html" in current_url


class TestLogout:
    """G002: 退出登录场景"""

    def test_logout_redirect(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        G002-1: 点击退出登录按钮→跳转到login.html→Token被清除

        验证点：
        1. 在Dashboard页面点击退出登录按钮
        2. 跳转到login.html
        3. localStorage中的Token被清除
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 点击退出登录按钮（使用title属性定位）
        logout_btn = dashboard_page.page.locator('button[title="退出登录"]')
        logout_btn.click()

        # 等待跳转到登录页
        dashboard_page.wait_for_navigation("**/login.html", timeout=NAVIGATION_TIMEOUT)

        # 验证URL包含login.html
        current_url = dashboard_page.get_current_url()
        assert "login.html" in current_url

        # 验证Token已被清除
        token_after = dashboard_page.page.evaluate("localStorage.getItem('trmd_token')")
        assert token_after is None or token_after == "", (
            "退出登录后localStorage中的Token应被清除"
        )


class TestNotificationSystem:
    """G003: 通知系统场景"""

    def test_notification_appears_on_action(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        G003-1: 执行操作→通知出现→等待5秒后自动消失

        验证点：
        1. 在Dashboard页点击刷新按钮触发通知
        2. 验证通知出现
        3. 等待约5秒后通知自动消失
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 点击刷新按钮（Dashboard刷新后会添加success通知"已刷新"）
        dashboard_page.click_refresh()

        # 等待通知出现
        notification_item = dashboard_page.page.locator(
            '[data-testid="notification-container"] div.border-l-4'
        ).first
        notification_item.wait_for(state="visible", timeout=5000)

        # 验证通知可见
        assert notification_item.is_visible(), "刷新后应出现通知"

        # 验证通知文本包含"已刷新"
        notification_text = notification_item.locator("p").text_content() or ""
        assert "已刷新" in notification_text, (
            f"通知文本应包含'已刷新'，实际为'{notification_text}'"
        )

        # 等待通知自动消失（5秒 + 1秒缓冲）
        notification_item.wait_for(state="hidden", timeout=7000)

        # 验证通知已消失
        assert not notification_item.is_visible(), "通知应在5秒后自动消失"


class TestNotificationManualClose:
    """G004: 通知手动关闭场景"""

    def test_notification_manual_close(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """G004-1: 点击通知X按钮立即移除通知"""
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 触发通知
        dashboard_page.click_refresh()

        # 等待通知出现
        notification_item = dashboard_page.page.locator(
            '[data-testid="notification-container"] div.border-l-4'
        ).first
        notification_item.wait_for(state="visible", timeout=5000)

        # 点击X按钮关闭
        close_btn = notification_item.locator("button")
        close_btn.click()

        dashboard_page.wait_for_timeout(500)

        # 验证通知已消失
        assert not notification_item.is_visible()


# ========== P2辅助场景补充 ==========


class TestNotificationStacking:
    """G067: 通知堆叠场景"""

    def test_notification_stacking(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """G067-1: 连续触发多条通知时通知堆叠显示"""
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 连续触发3条通知（dashboardApp 是组件工厂函数，需通过 Alpine.$data 获取实例）
        dashboard_page.page.evaluate(
            """
            () => {
                const el = document.querySelector('[x-data]');
                const app = window.Alpine.$data(el);
                app.addNotification('info', '通知1');
                app.addNotification('success', '通知2');
                app.addNotification('warning', '通知3');
            }
            """
        )

        # 等待通知渲染
        dashboard_page.wait_for_timeout(500)

        # 验证通知容器中通知项数量>=3
        notification_count = dashboard_page.page.locator(
            '[data-testid="notification-container"] div.border-l-4'
        ).count()

        assert notification_count >= 3, (
            f"连续触发3条通知后应堆叠显示至少3条通知，实际为{notification_count}条"
        )
