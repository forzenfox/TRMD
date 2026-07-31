"""
ConfigPage - 配置页Page Object

封装配置页面的交互逻辑，提供稳定的data-testid选择器接口。
"""

from playwright.sync_api import Page
from .base_page import BasePage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


class ConfigPage(BasePage):
    """配置页Page Object"""

    # 页面路径
    URL_PATH = "/web/config.html"

    # data-testid常量
    # 标签页
    TAB_BASIC = "tab-basic"
    TAB_DOWNLOAD = "tab-download"
    TAB_UPLOAD = "tab-upload"
    TAB_PROXY = "tab-proxy"
    TAB_NOTIFICATION = "tab-notification"
    TAB_RESOURCE = "tab-resource"

    # 标签页内容面板
    PANEL_BASIC = "panel-basic"
    PANEL_DOWNLOAD = "tab-content-download"
    PANEL_UPLOAD = "tab-content-upload"
    PANEL_PROXY = "tab-content-proxy"
    PANEL_NOTIFICATION = "tab-content-notification"
    PANEL_RESOURCE = "tab-content-resource"

    # 基础配置输入
    INPUT_API_ID = "input-api-id"
    INPUT_API_HASH = "input-api-hash"
    INPUT_BOT_TOKEN = "input-bot-token"
    INPUT_WORK_DIR = "input-work-dir"

    # 下载配置输入
    INPUT_MAX_DOWNLOAD_TASK = "input-max-download-task"
    INPUT_RETRY_COUNT = "input-retry-count"

    # 上传配置输入
    INPUT_MAX_UPLOAD_TASK = "input-max-upload-task"
    INPUT_MEDIA_GROUP_SIZE = "input-media-group-size"
    SELECT_SEND_METHOD = "select-send-method"

    # 代理配置
    CHECKBOX_PROXY_ENABLED = "checkbox-proxy-enabled"
    SELECT_PROXY_TYPE = "select-proxy-type"
    INPUT_PROXY_HOST = "input-proxy-host"
    INPUT_PROXY_PORT = "input-proxy-port"
    INPUT_PROXY_USERNAME = "input-proxy-username"
    INPUT_PROXY_PASSWORD = "input-proxy-password"

    # 通知配置
    CHECKBOX_NOTIFICATION_ENABLED = "checkbox-notification-enabled"
    CHECKBOX_ERROR_NOTIFICATION = "checkbox-error-notification"

    # 资源限制
    INPUT_MAX_CONCURRENT_TASKS = "input-max-concurrent-tasks"
    INPUT_TASK_SIZE_WARNING = "input-task-size-warning"
    INPUT_TASK_SIZE_MAX = "input-task-size-max"
    INPUT_MIN_DISK_SPACE = "input-min-disk-space"

    # 操作按钮
    SAVE_BTN = "save-btn"
    RESET_BTN = "reset-btn"

    # 状态提示
    CONFIG_SUCCESS = "config-success"
    CONFIG_ERROR = "config-error"

    # 加载状态
    LOADING_INDICATOR = "loading-indicator"

    # 所有标签页
    ALL_TABS = [
        TAB_BASIC,
        TAB_DOWNLOAD,
        TAB_UPLOAD,
        TAB_PROXY,
        TAB_NOTIFICATION,
        TAB_RESOURCE,
    ]

    # 标签页与面板的映射
    TAB_PANEL_MAP = {
        TAB_BASIC: PANEL_BASIC,
        TAB_DOWNLOAD: PANEL_DOWNLOAD,
        TAB_UPLOAD: PANEL_UPLOAD,
        TAB_PROXY: PANEL_PROXY,
        TAB_NOTIFICATION: PANEL_NOTIFICATION,
        TAB_RESOURCE: PANEL_RESOURCE,
    }

    def __init__(self, page: Page):
        super().__init__(page)

    def navigate(self, base_url: str) -> None:
        """
        导航到配置页

        Args:
            base_url: 服务基础URL
        """
        self.page.goto(f"{base_url}{self.URL_PATH}")

    def wait_for_page_loaded(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """
        等待配置页加载完成

        策略：先等待网络空闲（API调用完成），再等待基础配置标签页可见。
        这确保Alpine.js已获取配置数据并完成渲染。
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass  # networkidle可能超时，继续等待元素可见
        self.page.locator(f'[data-testid="{self.TAB_BASIC}"]').wait_for(
            state="visible", timeout=timeout
        )

    # ========== 标签页切换 ==========

    def switch_tab(self, tab: str, timeout: int = 5000) -> None:
        """
        切换到指定标签页

        Args:
            tab: 标签页testid常量（如TAB_BASIC）
            timeout: 等待超时时间（毫秒）
        """
        self.click_by_testid(tab)
        # 等待对应面板显示
        panel = self.TAB_PANEL_MAP.get(tab)
        if panel:
            self.page.locator(f'[data-testid="{panel}"]').wait_for(
                state="visible", timeout=timeout
            )

    def is_tab_visible(self, tab: str) -> bool:
        """
        检查标签页是否可见

        Args:
            tab: 标签页testid常量

        Returns:
            是否可见
        """
        return self.is_visible_by_testid(tab)

    def is_tab_active(self, tab: str) -> bool:
        """
        检查标签页是否处于激活状态

        Args:
            tab: 标签页testid常量

        Returns:
            是否激活（包含active类）
        """
        locator = self.get_by_testid(tab)
        classes = locator.get_attribute("class") or ""
        return "active" in classes

    def is_panel_visible(self, panel: str) -> bool:
        """
        检查面板是否可见

        Args:
            panel: 面板testid常量

        Returns:
            是否可见
        """
        return self.is_visible_by_testid(panel)

    def get_all_tabs_visible(self) -> list:
        """获取所有可见的标签页列表"""
        visible_tabs = []
        for tab in self.ALL_TABS:
            if self.is_visible_by_testid(tab):
                visible_tabs.append(tab)
        return visible_tabs

    # ========== 配置值读取与修改 ==========

    def get_input_value(self, testid: str) -> str:
        """
        获取输入框的值

        Args:
            testid: 输入框的data-testid

        Returns:
            输入框的值
        """
        return self.get_value_by_testid(testid)

    def set_input_value(self, testid: str, value: str) -> None:
        """
        设置输入框的值（通过Playwright fill触发Alpine.js事件处理）

        Config页面使用:value绑定和@input="configManager.updateConfigValue(key, value); _tu()"
        来跟踪变更。使用fill()模拟用户输入是最可靠的方式，它会：
        1. 更新DOM输入框的值
        2. 触发input事件，进而触发@input处理器
        3. @input处理器调用configManager.updateConfigValue()更新配置状态
        4. _tu()递增_ut触发器，使Alpine重新评估依赖configManager的表达式

        Args:
            testid: 输入框的data-testid
            value: 要设置的值
        """
        # 从data-testid推断配置key名（保留映射供未来使用和一致性检查）
        testid_to_key = {
            self.INPUT_API_ID: "api_id",
            self.INPUT_API_HASH: "api_hash",
            self.INPUT_BOT_TOKEN: "bot_token",
            self.INPUT_WORK_DIR: "work_dir",
            self.INPUT_MAX_DOWNLOAD_TASK: "max_download_task",
            self.INPUT_RETRY_COUNT: "retry_count",
            self.INPUT_MAX_UPLOAD_TASK: "max_upload_task",
            self.INPUT_MEDIA_GROUP_SIZE: "media_group_size",
            self.INPUT_PROXY_HOST: "proxy_host",
            self.INPUT_PROXY_PORT: "proxy_port",
            self.INPUT_PROXY_USERNAME: "proxy_username",
            self.INPUT_PROXY_PASSWORD: "proxy_password",
            self.INPUT_MAX_CONCURRENT_TASKS: "max_concurrent_tasks",
            self.INPUT_MIN_DISK_SPACE: "min_disk_space_gb",
            self.INPUT_TASK_SIZE_WARNING: "task_size_warning_gb",
            self.INPUT_TASK_SIZE_MAX: "task_size_max_gb",
        }

        config_key = testid_to_key.get(testid)
        locator = self.get_by_testid(testid)

        if config_key:
            # 使用fill()触发Alpine.js的:value绑定和@input事件处理器
            # 这确保DOM更新和configManager变更检测都正常工作
            locator.fill(value)
        else:
            # fallback：使用fill + dispatchEvent
            locator.fill(value)
            locator.evaluate(
                "el => { el.dispatchEvent(new Event('input', { bubbles: true })); }"
            )

    def get_api_id_value(self) -> str:
        """获取API ID输入框的值"""
        return self.get_input_value(self.INPUT_API_ID)

    def set_api_id_value(self, value: str) -> None:
        """设置API ID输入框的值"""
        self.set_input_value(self.INPUT_API_ID, value)

    # ========== 保存/重置操作 ==========

    def click_save(self) -> None:
        """点击保存配置按钮（等待按钮可见）"""
        self.page.locator(f'[data-testid="{self.SAVE_BTN}"]').wait_for(
            state="visible", timeout=5000
        )
        self.click_by_testid(self.SAVE_BTN)

    def click_reset(self) -> None:
        """点击重置配置按钮（等待按钮可见）"""
        self.page.locator(f'[data-testid="{self.RESET_BTN}"]').wait_for(
            state="visible", timeout=5000
        )
        self.click_by_testid(self.RESET_BTN)

    def is_save_btn_visible(self) -> bool:
        """检查保存按钮是否可见"""
        return self.is_visible_by_testid(self.SAVE_BTN)

    def is_reset_btn_visible(self) -> bool:
        """检查重置按钮是否可见"""
        return self.is_visible_by_testid(self.RESET_BTN)

    # ========== 变更状态检查 ==========

    def has_changes(self, timeout: int = 3000) -> bool:
        """
        检查是否有未保存的配置变更

        通过检查Alpine.js的configManager.hasChanges状态判断。
        等待一段时间让Alpine.js响应DOM变更。

        Args:
            timeout: 等待超时时间（毫秒）

        Returns:
            是否有变更
        """
        try:
            self.page.wait_for_function(
                "() => window.configManager && window.configManager.hasChanges === true",
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    # ========== 状态提示检查 ==========

    def is_success_visible(self, timeout: int = 5000) -> bool:
        """
        检查保存成功提示是否可见

        Args:
            timeout: 等待超时时间（毫秒）

        Returns:
            是否可见
        """
        try:
            self.page.locator(f'[data-testid="{self.CONFIG_SUCCESS}"]').wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def is_error_visible(self, timeout: int = 5000) -> bool:
        """
        检查错误提示是否可见

        Args:
            timeout: 等待超时时间（毫秒）

        Returns:
            是否可见
        """
        try:
            self.page.locator(f'[data-testid="{self.CONFIG_ERROR}"]').wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def get_error_text(self) -> str:
        """
        获取错误提示的文本内容

        Returns:
            错误提示文本
        """
        return self.get_text_by_testid(self.CONFIG_ERROR)

    # ========== 加载状态 ==========

    def is_loading_visible(self) -> bool:
        """检查加载指示器是否可见"""
        return self.is_visible_by_testid(self.LOADING_INDICATOR)

    def wait_for_loading_complete(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待加载完成（加载指示器消失）"""
        try:
            self.page.locator(f'[data-testid="{self.LOADING_INDICATOR}"]').wait_for(
                state="hidden", timeout=timeout
            )
        except Exception:
            pass  # 可能加载很快已经消失

    # ========== 代理/下载类型交互 ==========

    def toggle_proxy_enabled(self) -> None:
        """切换代理启用checkbox"""
        self.click_by_testid(self.CHECKBOX_PROXY_ENABLED)

    def is_proxy_fields_visible(self) -> bool:
        """检查代理字段是否可见（启用代理后可见）"""
        return self.is_visible_by_testid(self.INPUT_PROXY_HOST)

    def toggle_download_type(self, type_value: str) -> None:
        """切换下载类型checkbox"""
        self.page.evaluate(
            f"() => window.configManager.toggleDownloadType('{type_value}')"
        )

    def is_download_type_selected(self, type_value: str) -> bool:
        """检查下载类型是否选中"""
        return bool(
            self.page.evaluate(
                f"() => window.configManager.isDownloadTypeSelected('{type_value}')"
            )
        )

    def set_checkbox_by_testid(self, testid: str, checked: bool) -> None:
        """设置checkbox状态"""
        self.set_checked_by_testid(testid, checked)

    # ========== 通知配置交互 ==========

    def toggle_notification_enabled(self) -> None:
        """切换启用完成通知checkbox"""
        self.click_by_testid(self.CHECKBOX_NOTIFICATION_ENABLED)

    def is_notification_enabled(self) -> bool:
        """检查启用完成通知checkbox是否勾选"""
        return self.is_checked_by_testid(self.CHECKBOX_NOTIFICATION_ENABLED)

    def set_notification_enabled(self, checked: bool) -> None:
        """设置启用完成通知checkbox状态"""
        self.set_checked_by_testid(self.CHECKBOX_NOTIFICATION_ENABLED, checked)

    def toggle_error_notification(self) -> None:
        """切换启用错误通知checkbox"""
        self.click_by_testid(self.CHECKBOX_ERROR_NOTIFICATION)

    def is_error_notification_checked(self) -> bool:
        """检查启用错误通知checkbox是否勾选"""
        return self.is_checked_by_testid(self.CHECKBOX_ERROR_NOTIFICATION)

    def set_error_notification(self, checked: bool) -> None:
        """设置启用错误通知checkbox状态"""
        self.set_checked_by_testid(self.CHECKBOX_ERROR_NOTIFICATION, checked)
