"""
DashboardPage - Dashboard页Page Object

封装Dashboard页面的交互逻辑，提供稳定的data-testid选择器接口。
"""

from playwright.sync_api import Page
from .base_page import BasePage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


class DashboardPage(BasePage):
    """Dashboard页Page Object"""

    # 页面路径
    URL_PATH = "/web/index.html"

    # data-testid常量
    # 资源卡片
    DISK_CARD = "disk-card"
    MEMORY_CARD = "memory-card"
    CPU_CARD = "cpu-card"
    RUNNING_TASKS_CARD = "running-tasks-card"

    # 状态指示器
    CLIENT_STATUS_INDICATOR = "client-status-indicator"

    # 快捷操作按钮
    QUICK_DOWNLOAD_BTN = "quick-download-btn"
    QUICK_FORWARD_BTN = "quick-forward-btn"
    QUICK_UPLOAD_BTN = "quick-upload-btn"
    QUICK_SETTINGS_BTN = "quick-settings-btn"

    # 其他按钮
    REFRESH_BTN = "refresh-btn"
    LOGOUT_BTN = "logout-btn"

    # 通知
    NOTIFICATION_CONTAINER = "notification-container"

    # 最近任务
    RECENT_TASKS_CONTAINER = "recent-tasks-container"

    # 侧边栏导航
    SIDEBAR_NAV = "sidebar-nav"
    SIDEBAR_DASHBOARD_LINK = "sidebar-dashboard-link"
    SIDEBAR_TASKS_LINK = "sidebar-tasks-link"
    SIDEBAR_FILES_LINK = "sidebar-files-link"
    SIDEBAR_CONFIG_LINK = "sidebar-config-link"

    def __init__(self, page: Page):
        super().__init__(page)

    def navigate(self, base_url: str) -> None:
        """
        导航到Dashboard页

        Args:
            base_url: 服务基础URL
        """
        self.page.goto(f"{base_url}{self.URL_PATH}")

    def get_disk_card_text(self) -> str:
        """获取磁盘卡片的文本内容"""
        return self.get_text_by_testid(self.DISK_CARD)

    def get_memory_card_text(self) -> str:
        """获取内存卡片的文本内容"""
        return self.get_text_by_testid(self.MEMORY_CARD)

    def get_cpu_card_text(self) -> str:
        """获取CPU卡片的文本内容"""
        return self.get_text_by_testid(self.CPU_CARD)

    def get_running_tasks_count(self) -> str:
        """获取运行任务卡片中的任务数量文本"""
        return self.get_text_by_testid(self.RUNNING_TASKS_CARD)

    def get_client_status(self) -> str:
        """获取Client状态指示器的文本内容"""
        return self.get_text_by_testid(self.CLIENT_STATUS_INDICATOR)

    def click_quick_download(self) -> None:
        """点击快捷下载按钮"""
        self.click_by_testid(self.QUICK_DOWNLOAD_BTN)

    def click_quick_forward(self) -> None:
        """点击快捷转发按钮"""
        self.click_by_testid(self.QUICK_FORWARD_BTN)

    def click_quick_upload(self) -> None:
        """点击快捷上传按钮"""
        self.click_by_testid(self.QUICK_UPLOAD_BTN)

    def click_quick_settings(self) -> None:
        """点击快捷设置按钮"""
        self.click_by_testid(self.QUICK_SETTINGS_BTN)

    def click_refresh(self) -> None:
        """点击刷新按钮"""
        self.click_by_testid(self.REFRESH_BTN)

    def is_disk_card_visible(self) -> bool:
        """检查磁盘卡片是否可见"""
        return self.is_visible_by_testid(self.DISK_CARD)

    def is_memory_card_visible(self) -> bool:
        """检查内存卡片是否可见"""
        return self.is_visible_by_testid(self.MEMORY_CARD)

    def is_cpu_card_visible(self) -> bool:
        """检查CPU卡片是否可见"""
        return self.is_visible_by_testid(self.CPU_CARD)

    def is_running_tasks_card_visible(self) -> bool:
        """检查运行任务卡片是否可见"""
        return self.is_visible_by_testid(self.RUNNING_TASKS_CARD)

    def is_client_status_visible(self) -> bool:
        """检查Client状态指示器是否可见"""
        return self.is_visible_by_testid(self.CLIENT_STATUS_INDICATOR)

    def is_refresh_btn_visible(self) -> bool:
        """检查刷新按钮是否可见"""
        return self.is_visible_by_testid(self.REFRESH_BTN)

    def wait_for_stats_loaded(self, timeout: int = 15000) -> None:
        """等待资源统计数据加载完成（等待资源卡片可见）"""
        self.wait_for_selector(self.DISK_CARD, timeout)
        self.wait_for_selector(self.MEMORY_CARD, timeout)
        self.wait_for_selector(self.CPU_CARD, timeout)
        self.wait_for_selector(self.RUNNING_TASKS_CARD, timeout)

    def wait_for_dashboard(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待Dashboard页面加载完成

        策略：先等待网络空闲（API调用完成），再等待刷新按钮可见。
        这确保Alpine.js已获取数据并完成渲染。
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass  # networkidle可能超时，继续等待元素可见
        self.page.locator(f'[data-testid="{self.REFRESH_BTN}"]').wait_for(
            state="visible", timeout=timeout
        )

    def get_quick_download_href(self) -> str:
        """获取快捷下载按钮的链接地址"""
        locator = self.get_by_testid(self.QUICK_DOWNLOAD_BTN)
        return locator.get_attribute("href") or ""

    def get_quick_forward_href(self) -> str:
        """获取快捷转发按钮的链接地址"""
        locator = self.get_by_testid(self.QUICK_FORWARD_BTN)
        return locator.get_attribute("href") or ""

    def get_quick_upload_href(self) -> str:
        """获取快捷上传按钮的链接地址"""
        locator = self.get_by_testid(self.QUICK_UPLOAD_BTN)
        return locator.get_attribute("href") or ""

    def get_quick_settings_href(self) -> str:
        """获取快捷设置按钮的链接地址"""
        locator = self.get_by_testid(self.QUICK_SETTINGS_BTN)
        return locator.get_attribute("href") or ""

    # ========== 退出登录（D006） ==========

    def click_logout(self) -> None:
        """点击退出登录按钮"""
        self.click_by_testid(self.LOGOUT_BTN)

    def is_logout_btn_visible(self) -> bool:
        """检查退出登录按钮是否可见"""
        return self.is_visible_by_testid(self.LOGOUT_BTN)

    # ========== 通知相关（D007） ==========

    def _get_notification_item_locator(self):
        """获取通知项的Locator（容器内border-l-4样式的通知条目）"""
        return self.page.locator(
            f'[data-testid="{self.NOTIFICATION_CONTAINER}"] div.border-l-4'
        ).first

    def wait_for_notification(self, timeout: int = 5000) -> None:
        """
        等待通知消息出现

        通知容器内会渲染包含border-l-4样式的通知项。
        使用data-testid定位通知容器，再查找其中的通知项。
        """
        self._get_notification_item_locator().wait_for(state="visible", timeout=timeout)

    def is_notification_visible(self, timeout: int = 5000) -> bool:
        """
        检查通知消息是否可见

        Args:
            timeout: 等待超时时间（毫秒）

        Returns:
            True如果通知项可见，否则False
        """
        try:
            self._get_notification_item_locator().wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def get_notification_text(self, timeout: int = 5000) -> str:
        """
        获取第一条通知消息的文本内容

        Args:
            timeout: 等待超时时间（毫秒）

        Returns:
            通知文本，未找到时返回空字符串
        """
        try:
            notification_text_locator = self.page.locator(
                f'[data-testid="{self.NOTIFICATION_CONTAINER}"] div.border-l-4 p'
            ).first
            notification_text_locator.wait_for(state="visible", timeout=timeout)
            return notification_text_locator.text_content() or ""
        except Exception:
            return ""

    # ========== 最近任务相关（D008） ==========

    def is_recent_tasks_visible(self) -> bool:
        """检查最近任务区域是否可见"""
        return self.is_visible_by_testid(self.RECENT_TASKS_CONTAINER)

    def is_recent_tasks_container_visible(self) -> bool:
        """检查最近任务容器是否可见（别名方法）"""
        return self.is_visible_by_testid(self.RECENT_TASKS_CONTAINER)

    def get_recent_tasks_text(self) -> str:
        """获取最近任务容器的文本内容"""
        return self.get_text_by_testid(self.RECENT_TASKS_CONTAINER)

    def is_recent_tasks_empty_state_visible(self) -> bool:
        """
        检查最近任务空状态提示是否可见

        空状态在Alpine.js中通过 x-show="!tasksLoading && recentTasks.length === 0" 控制，
        显示"暂无任务"文本。
        """
        try:
            locator = self.page.locator(
                f'[data-testid="{self.RECENT_TASKS_CONTAINER}"] >> text=暂无任务'
            )
            return locator.is_visible()
        except Exception:
            return False

    def is_recent_tasks_table_visible(self) -> bool:
        """
        检查最近任务列表表格是否可见

        任务列表在Alpine.js中通过 x-show="!tasksLoading && recentTasks.length > 0" 控制。
        """
        try:
            locator = self.page.locator(
                f'[data-testid="{self.RECENT_TASKS_CONTAINER}"] table.table'
            )
            return locator.is_visible()
        except Exception:
            return False

    def is_create_task_link_visible(self) -> bool:
        """
        检查"创建第一个任务"链接是否可见

        空状态下会显示"创建第一个任务"引导链接。
        """
        try:
            locator = self.page.locator(
                f'[data-testid="{self.RECENT_TASKS_CONTAINER}"] >> text=创建第一个任务'
            )
            return locator.is_visible()
        except Exception:
            return False

    # ========== 侧边栏导航相关（D009） ==========

    def is_sidebar_nav_visible(self) -> bool:
        """检查侧边栏导航容器是否可见"""
        return self.is_visible_by_testid(self.SIDEBAR_NAV)

    def is_sidebar_tasks_link_visible(self) -> bool:
        """检查侧边栏"任务管理"链接是否可见"""
        return self.is_visible_by_testid(self.SIDEBAR_TASKS_LINK)

    def is_sidebar_files_link_visible(self) -> bool:
        """检查侧边栏"文件管理"链接是否可见"""
        return self.is_visible_by_testid(self.SIDEBAR_FILES_LINK)

    def is_sidebar_config_link_visible(self) -> bool:
        """检查侧边栏"系统配置"链接是否可见"""
        return self.is_visible_by_testid(self.SIDEBAR_CONFIG_LINK)

    def get_sidebar_tasks_href(self) -> str:
        """获取侧边栏"任务管理"链接地址"""
        locator = self.get_by_testid(self.SIDEBAR_TASKS_LINK)
        return locator.get_attribute("href") or ""

    def get_sidebar_files_href(self) -> str:
        """获取侧边栏"文件管理"链接地址"""
        locator = self.get_by_testid(self.SIDEBAR_FILES_LINK)
        return locator.get_attribute("href") or ""

    def get_sidebar_config_href(self) -> str:
        """获取侧边栏"系统配置"链接地址"""
        locator = self.get_by_testid(self.SIDEBAR_CONFIG_LINK)
        return locator.get_attribute("href") or ""
