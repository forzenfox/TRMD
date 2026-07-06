"""
Dashboard页面E2E测试

覆盖Dashboard加载、资源监控、快捷操作等场景。
"""

import pytest
from playwright.sync_api import Page

from ..pages.dashboard_page import DashboardPage


@pytest.fixture
def dashboard_page(page: Page) -> DashboardPage:
    """Dashboard页Page Object fixture"""
    return DashboardPage(page)


class TestDashboardLoadsSuccessfully:
    """D001: Dashboard加载成功场景"""

    def test_dashboard_loads_after_login(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D001: 登录后Dashboard加载成功

        验证点：
        1. Dashboard页面可以正常访问
        2. 页面标题正确
        3. 主要UI元素可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证页面URL
        assert "index.html" in dashboard_page.get_current_url()

        # 验证页面标题
        title = dashboard_page.page.title()
        assert "Dashboard" in title

        # 验证刷新按钮可见
        assert dashboard_page.is_refresh_btn_visible()


class TestResourceCardsDisplay:
    """D002: 资源卡片正确显示场景"""

    def test_resource_cards_display(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D002: 资源卡片正确显示

        验证点：
        1. 磁盘空间卡片可见
        2. 内存使用卡片可见
        3. CPU使用率卡片可见
        4. 运行任务卡片可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 等待资源统计数据加载
        dashboard_page.wait_for_stats_loaded()

        # 验证磁盘卡片可见
        assert dashboard_page.is_disk_card_visible()
        disk_text = dashboard_page.get_disk_card_text()
        assert "磁盘" in disk_text

        # 验证内存卡片可见
        assert dashboard_page.is_memory_card_visible()
        memory_text = dashboard_page.get_memory_card_text()
        assert "内存" in memory_text

        # 验证CPU卡片可见
        assert dashboard_page.is_cpu_card_visible()
        cpu_text = dashboard_page.get_cpu_card_text()
        assert "CPU" in cpu_text

        # 验证运行任务卡片可见
        assert dashboard_page.is_running_tasks_card_visible()
        tasks_text = dashboard_page.get_running_tasks_count()
        assert "运行任务" in tasks_text or "队列" in tasks_text


class TestClientStatusIndicator:
    """D003: Client状态指示器显示场景"""

    def test_client_status_indicator_display(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D003: Client状态指示器显示

        验证点：
        1. Client状态指示器可见
        2. 状态文本非空
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证Client状态指示器可见
        assert dashboard_page.is_client_status_visible()

        # 获取状态文本
        status_text = dashboard_page.get_client_status()
        assert len(status_text) > 0


class TestQuickActionButtons:
    """D004: 快捷操作按钮可用场景"""

    def test_quick_action_buttons_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D004: 快捷操作按钮可见

        验证点：
        1. 新建下载按钮可见
        2. 新建转发按钮可见
        3. 新建上传按钮可见
        4. 打开设置按钮可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证快捷下载按钮可见
        assert dashboard_page.is_visible_by_testid(DashboardPage.QUICK_DOWNLOAD_BTN)

        # 验证快捷转发按钮可见
        assert dashboard_page.is_visible_by_testid(DashboardPage.QUICK_FORWARD_BTN)

        # 验证快捷上传按钮可见
        assert dashboard_page.is_visible_by_testid(DashboardPage.QUICK_UPLOAD_BTN)

        # 验证快捷设置按钮可见
        assert dashboard_page.is_visible_by_testid(DashboardPage.QUICK_SETTINGS_BTN)

    def test_quick_download_button_href(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D004-1: 快捷下载按钮链接正确

        验证点：
        1. 按钮包含正确的URL参数
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证快捷下载按钮链接
        href = dashboard_page.get_quick_download_href()
        assert "tasks.html" in href
        assert "action=create" in href
        assert "type=download" in href

    def test_quick_forward_button_href(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D004-2: 快捷转发按钮链接正确

        验证点：
        1. 按钮包含正确的URL参数
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证快捷转发按钮链接
        href = dashboard_page.get_quick_forward_href()
        assert "tasks.html" in href
        assert "action=create" in href
        assert "type=forward" in href

    def test_quick_upload_button_href(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D004-3: 快捷上传按钮链接正确

        验证点：
        1. 按钮包含正确的URL参数
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证快捷上传按钮链接
        href = dashboard_page.get_quick_upload_href()
        assert "tasks.html" in href
        assert "action=create" in href
        assert "type=upload" in href

    def test_quick_settings_button_href(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D004-4: 快捷设置按钮链接正确

        验证点：
        1. 按钮包含正确的URL
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证快捷设置按钮链接
        href = dashboard_page.get_quick_settings_href()
        assert "config.html" in href


class TestNavigationToTasks:
    """D005: 导航到任务管理页场景"""

    def test_navigation_to_tasks_page_via_download_btn(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D005: 通过快捷下载按钮导航到任务管理页

        验证点：
        1. 点击按钮后跳转到任务管理页
        2. URL包含正确的参数
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 点击快捷下载按钮
        dashboard_page.click_quick_download()

        # 等待跳转
        dashboard_page.wait_for_navigation("**/tasks.html*", timeout=10000)

        # 验证URL
        current_url = dashboard_page.get_current_url()
        assert "tasks.html" in current_url
        assert "action=create" in current_url
        assert "type=download" in current_url

    def test_navigation_to_config_page_via_settings_btn(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D005-2: 通过快捷设置按钮导航到配置页

        验证点：
        1. 点击按钮后跳转到配置页
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 点击快捷设置按钮
        dashboard_page.click_quick_settings()

        # 等待跳转
        dashboard_page.wait_for_navigation("**/config.html", timeout=10000)

        # 验证URL
        current_url = dashboard_page.get_current_url()
        assert "config.html" in current_url
