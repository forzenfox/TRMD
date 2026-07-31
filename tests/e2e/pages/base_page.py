"""
BasePage - Page Object基类

提供统一的data-testid选择器接口和通用页面操作方法。
"""

from typing import Optional
from playwright.sync_api import Page, Locator, Response


class BasePage:
    """所有Page Object的基类"""

    def __init__(self, page: Page):
        self.page = page

    # ========== testid选择器方法 ==========

    def wait_for_selector(self, testid: str, timeout: int = 10000) -> Locator:
        """等待并返回指定testid的元素"""
        return self.page.wait_for_selector(f'[data-testid="{testid}"]', timeout=timeout)

    def get_by_testid(self, testid: str) -> Locator:
        """获取指定testid的Locator（不等待）"""
        return self.page.locator(f'[data-testid="{testid}"]')

    def click_by_testid(self, testid: str) -> None:
        """点击指定testid的元素"""
        self.page.click(f'[data-testid="{testid}"]')

    def fill_by_testid(self, testid: str, value: str) -> None:
        """填充指定testid的输入框"""
        self.page.fill(f'[data-testid="{testid}"]', value)

    def get_text_by_testid(self, testid: str) -> str:
        """获取指定testid元素的文本内容"""
        locator = self.page.locator(f'[data-testid="{testid}"]')
        return locator.text_content() or ""

    def get_value_by_testid(self, testid: str) -> str:
        """获取指定testid输入框的值"""
        return self.page.input_value(f'[data-testid="{testid}"]')

    def is_visible_by_testid(self, testid: str) -> bool:
        """检查指定testid元素是否可见"""
        return self.page.locator(f'[data-testid="{testid}"]').is_visible()

    def is_enabled_by_testid(self, testid: str) -> bool:
        """检查指定testid元素是否可交互"""
        return self.page.locator(f'[data-testid="{testid}"]').is_enabled()

    def wait_for_hidden_by_testid(self, testid: str, timeout: int = 10000) -> None:
        """等待指定testid元素消失"""
        self.page.locator(f'[data-testid="{testid}"]').wait_for(
            state="hidden", timeout=timeout
        )

    # ========== 表单操作方法 ==========

    def select_option_by_testid(self, testid: str, value: str) -> None:
        """选择下拉框选项"""
        self.page.select_option(f'[data-testid="{testid}"]', value)

    def check_by_testid(self, testid: str) -> None:
        """勾选checkbox"""
        self.page.check(f'[data-testid="{testid}"]')

    def uncheck_by_testid(self, testid: str) -> None:
        """取消勾选checkbox"""
        self.page.uncheck(f'[data-testid="{testid}"]')

    def is_checked_by_testid(self, testid: str) -> bool:
        """检查checkbox是否被勾选"""
        return self.page.locator(f'[data-testid="{testid}"]').is_checked()

    def set_checked_by_testid(self, testid: str, checked: bool) -> None:
        """设置checkbox状态"""
        if checked:
            self.check_by_testid(testid)
        else:
            self.uncheck_by_testid(testid)

    # ========== 导航和等待方法 ==========

    def navigate(self, base_url: str, path: str) -> None:
        """导航到指定路径"""
        self.page.goto(f"{base_url}{path}")

    def wait_for_navigation(self, url_pattern: str, timeout: int = 15000) -> None:
        """等待页面跳转到匹配URL"""
        self.page.wait_for_url(url_pattern, timeout=timeout)

    def wait_for_load_state(
        self, state: str = "networkidle", timeout: int = 30000
    ) -> None:
        """等待页面加载状态"""
        self.page.wait_for_load_state(state, timeout=timeout)

    def wait_for_response(
        self, url_pattern: str, timeout: int = 15000
    ) -> Optional[Response]:
        """等待特定API响应"""
        with self.page.expect_response(url_pattern, timeout=timeout) as response_info:
            return response_info.value

    # ========== 通用辅助方法 ==========

    def take_screenshot(self, path: str) -> None:
        """截图保存到指定路径"""
        self.page.screenshot(path=path)

    def wait_for_timeout(self, timeout: int) -> None:
        """等待指定时间（毫秒）"""
        self.page.wait_for_timeout(timeout)

    def evaluate(self, expression: str) -> any:
        """在页面中执行JavaScript"""
        return self.page.evaluate(expression)

    def get_current_url(self) -> str:
        """获取当前URL"""
        return self.page.url

    def reload(self) -> None:
        """刷新页面"""
        self.page.reload()
