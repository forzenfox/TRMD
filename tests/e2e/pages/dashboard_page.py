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
        """等待Dashboard页面加载完成"""
        self.wait_for_load_state("networkidle", timeout)

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
