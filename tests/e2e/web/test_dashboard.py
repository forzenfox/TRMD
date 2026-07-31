"""
Dashboard页面E2E测试

覆盖Dashboard加载、资源监控、快捷操作等场景。
"""

import pytest
from playwright.sync_api import Page

from ..pages.dashboard_page import DashboardPage


@pytest.fixture
def dashboard_page(authenticated_page: Page) -> DashboardPage:
    """Dashboard页Page Object fixture（已认证）"""
    return DashboardPage(authenticated_page)


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


class TestLogout:
    """D006: 退出登录场景"""

    def test_logout_button_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D006-1: 退出登录按钮可见

        验证点：
        1. 侧边栏中退出登录按钮可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证退出登录按钮可见
        assert dashboard_page.is_logout_btn_visible()

    def test_logout_clears_token_and_redirects(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D006-2: 点击退出登录后Token被清除并跳转到登录页

        验证点：
        1. 点击退出登录按钮
        2. Token被清除（localStorage中无trmd_token）
        3. 跳转到登录页（login.html）
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 点击退出登录按钮
        dashboard_page.click_logout()

        # 等待跳转到登录页
        dashboard_page.wait_for_navigation("**/login.html*", timeout=15000)

        # 验证URL包含login.html
        current_url = dashboard_page.get_current_url()
        assert "login.html" in current_url

        # 验证Token已被清除
        token_after = dashboard_page.evaluate("localStorage.getItem('trmd_token')")
        assert token_after is None


class TestManualRefresh:
    """D007: 手动刷新资源状态场景"""

    def test_refresh_button_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D007-1: 刷新按钮可见

        验证点：
        1. 顶部栏中刷新按钮可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证刷新按钮可见
        assert dashboard_page.is_refresh_btn_visible()

    def test_refresh_shows_notification(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D007-2: 点击刷新按钮后显示"已刷新"通知

        验证点：
        1. 点击刷新按钮
        2. 出现通知消息
        3. 通知内容包含"已刷新"
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 点击刷新按钮
        dashboard_page.click_refresh()

        # 等待通知出现
        assert dashboard_page.is_notification_visible(timeout=10000)

        # 验证通知文本包含"已刷新"
        notification_text = dashboard_page.get_notification_text(timeout=5000)
        assert "已刷新" in notification_text


class TestRecentTasksList:
    """D008: 最近任务列表场景"""

    def test_recent_tasks_container_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D008-1: 最近任务容器可见

        验证点：
        1. 最近任务区域容器可见
        2. 标题包含"最近任务"
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证最近任务容器可见
        assert dashboard_page.is_recent_tasks_container_visible()

        # 验证标题文本
        tasks_text = dashboard_page.get_recent_tasks_text()
        assert "最近任务" in tasks_text

    def test_recent_tasks_empty_state_display(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D008-2: 无任务时显示空状态提示和创建链接

        验证点（当没有任务时）：
        1. 显示"暂无任务"空状态提示
        2. 显示"创建第一个任务"链接
        3. 任务列表表格不可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 等待最近任务区域加载（等待tasksLoading变为false）
        dashboard_page.wait_for_timeout(3000)

        # 检查空状态或任务列表（二选一）
        # 如果有空任务则验证空状态，否则验证任务列表
        is_empty = dashboard_page.is_recent_tasks_empty_state_visible()

        if is_empty:
            # 空状态：验证提示文本和创建链接
            assert dashboard_page.is_create_task_link_visible()
            # 任务表格不应可见
            assert not dashboard_page.is_recent_tasks_table_visible()
        else:
            # 有任务：验证任务列表可见
            assert dashboard_page.is_recent_tasks_table_visible()
            # 空状态提示不应可见
            assert not dashboard_page.is_recent_tasks_empty_state_visible()

    def test_recent_tasks_view_all_link(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D008-3: 最近任务区域包含"查看全部"链接

        验证点：
        1. "查看全部"链接可见
        2. 链接指向tasks.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证"查看全部"链接可见
        view_all_link = dashboard_page.page.locator(
            f'[data-testid="{DashboardPage.RECENT_TASKS_CONTAINER}"] >> text=查看全部'
        )
        assert view_all_link.is_visible()


class TestSidebarNavigation:
    """D009: 侧边栏导航场景"""

    def test_sidebar_tasks_link_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D009-1: 侧边栏"任务管理"链接可见

        验证点：
        1. "任务管理"链接可见
        2. 链接指向tasks.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证"任务管理"链接可见
        assert dashboard_page.is_sidebar_tasks_link_visible()

        # 验证链接地址
        href = dashboard_page.get_sidebar_tasks_href()
        assert "tasks.html" in href

    def test_sidebar_files_link_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D009-2: 侧边栏"文件管理"链接可见

        验证点：
        1. "文件管理"链接可见
        2. 链接指向files.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证"文件管理"链接可见
        assert dashboard_page.is_sidebar_files_link_visible()

        # 验证链接地址
        href = dashboard_page.get_sidebar_files_href()
        assert "files.html" in href

    def test_sidebar_config_link_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D009-3: 侧边栏"系统配置"链接可见

        验证点：
        1. "系统配置"链接可见
        2. 链接指向config.html
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证"系统配置"链接可见
        assert dashboard_page.is_sidebar_config_link_visible()

        # 验证链接地址
        href = dashboard_page.get_sidebar_config_href()
        assert "config.html" in href

    def test_sidebar_all_navigation_links_visible(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """
        D009-4: 侧边栏所有导航链接同时可见

        验证点：
        1. 任务管理链接可见
        2. 文件管理链接可见
        3. 系统配置链接可见
        """
        # 导航到Dashboard
        dashboard_page.navigate(live_server)

        # 等待页面加载
        dashboard_page.wait_for_dashboard()

        # 验证所有导航链接同时可见
        assert dashboard_page.is_sidebar_tasks_link_visible()
        assert dashboard_page.is_sidebar_files_link_visible()
        assert dashboard_page.is_sidebar_config_link_visible()


# ========== P1重要功能补充场景 ==========


class TestClientStatusContent:
    """D053: Client状态文本内容验证"""

    def test_client_status_text_content(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """D053-1: Client状态文本包含状态关键词"""
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 获取Client状态文本
        status_text = dashboard_page.get_client_status()

        # 验证文本非空
        assert len(status_text) > 0, "Client状态文本不应为空"

        # 验证文本包含状态关键词
        status_keywords = ["已连接", "未连接", "连接中", "断开", "连接", "等待"]
        has_keyword = any(keyword in status_text for keyword in status_keywords)
        assert has_keyword, (
            f"Client状态文本应包含状态关键词（如'已连接'/'未连接'/'连接中'），"
            f"实际为'{status_text}'"
        )

        # 通过page.evaluate获取详细状态值（dashboardApp 是组件工厂函数，需通过 Alpine.$data 获取实例）
        detail_status = dashboard_page.page.evaluate(
            "() => { const el = document.querySelector('[x-data]'); return el && window.Alpine ? window.Alpine.$data(el).clientStatus : null; }"
        )
        assert detail_status is not None, "Alpine.$data(el).clientStatus 应返回状态值"


class TestCreateTaskLinkNavigation:
    """D054: 创建任务链接跳转场景"""

    def test_create_task_link_navigation(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """D054-1: 空状态下点击"创建第一个任务"链接跳转到tasks.html"""
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 等待最近任务区域加载
        dashboard_page.wait_for_timeout(3000)

        # 检查是否为空状态
        if not dashboard_page.is_recent_tasks_empty_state_visible():
            pytest.skip("存在任务，无法测试空状态创建链接")

        # 验证"创建第一个任务"链接可见
        assert dashboard_page.is_create_task_link_visible(), (
            "空状态下应显示'创建第一个任务'链接"
        )

        # 点击"创建第一个任务"链接
        create_link = dashboard_page.page.locator("text=创建第一个任务")
        create_link.click()

        # 等待跳转到任务管理页
        dashboard_page.wait_for_navigation("**/tasks.html*", timeout=10000)

        # 验证URL包含tasks.html
        current_url = dashboard_page.get_current_url()
        assert "tasks.html" in current_url, (
            f"点击创建任务链接应跳转到tasks.html，实际URL为'{current_url}'"
        )


# ========== P2辅助场景补充 ==========


class TestNotificationTypeStyle:
    """D064: 通知类型样式场景"""

    def test_notification_type_styles(
        self, dashboard_page: DashboardPage, test_token: str, live_server: str
    ):
        """D064-1: 不同类型通知显示对应的边框颜色样式"""
        # 导航到Dashboard
        dashboard_page.navigate(live_server)
        dashboard_page.wait_for_dashboard()

        # 定义通知类型与对应的边框颜色CSS类
        type_color_map = {
            "info": "border-blue-500",
            "success": "border-green-500",
            "warning": "border-yellow-500",
            "error": "border-red-500",
        }

        for notif_type, border_class in type_color_map.items():
            # 触发通知（dashboardApp 是组件工厂函数，需通过 Alpine.$data 获取实例）
            dashboard_page.page.evaluate(
                f"() => {{ const el = document.querySelector('[x-data]'); window.Alpine.$data(el).addNotification('{notif_type}', '{notif_type}通知'); }}"
            )

            # 等待通知渲染
            dashboard_page.wait_for_timeout(300)

            # 定位通知项
            notification_item = dashboard_page.page.locator(
                '[data-testid="notification-container"] div.border-l-4'
            ).first

            # 验证通知项可见
            assert notification_item.is_visible(), f"{notif_type}类型通知应可见"

            # 获取通知项的class属性
            item_class = notification_item.get_attribute("class") or ""

            # 验证CSS类包含对应的边框颜色
            assert border_class in item_class, (
                f"{notif_type}类型通知应包含'{border_class}'样式类，"
                f"实际class为'{item_class}'"
            )

            # 清除通知，为下一次测试做准备
            dashboard_page.page.evaluate(
                "() => { const el = document.querySelector('[x-data]'); window.Alpine.$data(el).notifications = []; }"
            )
            dashboard_page.wait_for_timeout(300)
