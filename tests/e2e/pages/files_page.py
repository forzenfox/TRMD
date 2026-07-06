"""
FilesPage - 文件管理页Page Object

封装文件管理页面的交互逻辑，提供稳定的data-testid选择器接口。
"""

from playwright.sync_api import Page, Locator
from .base_page import BasePage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


class FilesPage(BasePage):
    """文件管理页Page Object"""

    # 页面路径
    URL_PATH = "/web/files.html"

    # data-testid常量
    # 页面头部按钮
    REFRESH_BTN = "refresh-btn"
    UPLOAD_SELECTED_BTN = "upload-selected-btn"

    # 面包屑导航
    BREADCRUMB_CONTAINER = "breadcrumb-container"
    BREADCRUMB_ITEM = "breadcrumb-item"

    # 工具栏
    TOOLBAR = "toolbar"
    SELECT_ALL_BTN = "select-all-btn"
    CLEAR_SELECTION_BTN = "clear-selection-btn"
    SORT_NAME_BTN = "sort-name-btn"
    SORT_SIZE_BTN = "sort-size-btn"
    SORT_DATE_BTN = "sort-date-btn"

    # 文件列表
    FILES_CONTAINER = "files-container"
    FILES_TABLE = "files-table"
    FILE_ROW = "file-row"
    FILE_CHECKBOX = "file-checkbox"
    FILE_NAME = "file-name"
    FILE_SIZE = "file-size"
    FILE_DATE = "file-date"

    # 底部选择信息栏
    SELECTION_INFO_BAR = "selection-info-bar"
    SELECTED_COUNT = "selected-count"
    SELECTED_SIZE = "selected-size"
    UPLOAD_BTN_BOTTOM = "upload-btn-bottom"

    # 上传弹窗
    UPLOAD_MODAL = "upload-modal"
    MODAL_CLOSE_BTN = "modal-close-btn"
    UPLOAD_TARGET_INPUT = "upload-target-input"
    UPLOAD_MEDIA_GROUP_CHECKBOX = "upload-media-group-checkbox"
    UPLOAD_DELETE_CHECKBOX = "upload-delete-checkbox"
    UPLOAD_FILE_PREVIEW = "upload-file-preview"
    UPLOAD_CANCEL_BTN = "upload-cancel-btn"
    UPLOAD_SUBMIT_BTN = "upload-submit-btn"

    def __init__(self, page: Page):
        super().__init__(page)

    # ========== 导航方法 ==========

    def navigate(self, base_url: str) -> None:
        """导航到文件管理页"""
        url = f"{base_url}{self.URL_PATH}"
        self.page.goto(url)

    def wait_for_page_loaded(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待页面加载完成"""
        # 等待文件列表容器出现
        self.wait_for_selector(self.FILES_CONTAINER, timeout)

    # ========== 页面头部操作 ==========

    def click_refresh(self) -> None:
        """点击刷新按钮"""
        self.click_by_testid(self.REFRESH_BTN)

    def click_upload_selected(self) -> None:
        """点击上传选中文件按钮"""
        self.click_by_testid(self.UPLOAD_SELECTED_BTN)

    def is_upload_selected_btn_visible(self) -> bool:
        """检查上传选中按钮是否可见"""
        return self.is_visible_by_testid(self.UPLOAD_SELECTED_BTN)

    # ========== 面包屑导航 ==========

    def get_breadcrumb_items(self) -> list[Locator]:
        """获取面包屑导航项列表"""
        return self.get_by_testid(self.BREADCRUMB_ITEM).all()

    def click_breadcrumb_item(self, index: int) -> None:
        """点击指定索引的面包屑项"""
        items = self.get_breadcrumb_items()
        if index < len(items):
            items[index].click()

    def navigate_directory(self, path: str) -> None:
        """
        通过面包屑导航到指定目录

        Args:
            path: 目录路径
        """
        items = self.get_breadcrumb_items()
        for item in items:
            text = item.text_content()
            if text and text.strip() == path:
                item.click()
                break

    # ========== 工具栏操作 ==========

    def click_select_all(self) -> None:
        """点击全选按钮"""
        self.click_by_testid(self.SELECT_ALL_BTN)

    def click_clear_selection(self) -> None:
        """点击清空选择按钮"""
        self.click_by_testid(self.CLEAR_SELECTION_BTN)

    def is_clear_selection_btn_visible(self) -> bool:
        """检查清空选择按钮是否可见"""
        return self.is_visible_by_testid(self.CLEAR_SELECTION_BTN)

    def sort_by_name(self) -> None:
        """点击名称排序按钮"""
        self.click_by_testid(self.SORT_NAME_BTN)

    def sort_by_size(self) -> None:
        """点击大小排序按钮"""
        self.click_by_testid(self.SORT_SIZE_BTN)

    def sort_by_date(self) -> None:
        """点击日期排序按钮"""
        self.click_by_testid(self.SORT_DATE_BTN)

    def is_sort_btn_active(self, sort_type: str) -> bool:
        """检查排序按钮是否激活"""
        sort_map = {
            "name": self.SORT_NAME_BTN,
            "size": self.SORT_SIZE_BTN,
            "date": self.SORT_DATE_BTN,
        }
        testid = sort_map.get(sort_type)
        if not testid:
            return False
        locator = self.get_by_testid(testid)
        return "btn-primary" in locator.get_attribute("class")

    # ========== 文件列表 ==========

    def get_file_count(self) -> int:
        """获取当前文件列表中的文件数量"""
        tbody = self.get_by_testid(self.FILES_TABLE).locator("tbody")
        return tbody.locator("tr").count()

    def get_file_rows(self) -> list[Locator]:
        """获取所有文件行"""
        return self.get_by_testid(self.FILE_ROW).all()

    def get_file_row(self, index: int) -> Locator:
        """获取指定索引的文件行"""
        rows = self.get_file_rows()
        if index < len(rows):
            return rows[index]
        raise IndexError(f"File row index {index} out of range")

    def click_file_checkbox(self, index: int) -> None:
        """点击指定索引文件的checkbox"""
        row = self.get_file_row(index)
        checkbox = row.locator(f'[data-testid="{self.FILE_CHECKBOX}"]')
        checkbox.click()

    def is_file_selected(self, index: int) -> bool:
        """检查指定索引文件是否被选中"""
        row = self.get_file_row(index)
        checkbox = row.locator(f'[data-testid="{self.FILE_CHECKBOX}"]')
        return checkbox.is_checked()

    def get_file_name(self, index: int) -> str:
        """获取指定索引文件的名称"""
        row = self.get_file_row(index)
        name_element = row.locator(f'[data-testid="{self.FILE_NAME}"]')
        return name_element.text_content() or ""

    def get_file_size(self, index: int) -> str:
        """获取指定索引文件的大小"""
        row = self.get_file_row(index)
        size_element = row.locator(f'[data-testid="{self.FILE_SIZE}"]')
        return size_element.text_content() or ""

    def get_file_date(self, index: int) -> str:
        """获取指定索引文件的修改时间"""
        row = self.get_file_row(index)
        date_element = row.locator(f'[data-testid="{self.FILE_DATE}"]')
        return date_element.text_content() or ""

    def click_directory_name(self, index: int) -> None:
        """点击目录名称以进入该目录"""
        row = self.get_file_row(index)
        name_link = row.locator(f'a[data-testid="{self.FILE_NAME}"]')
        if name_link.count() > 0:
            name_link.click()

    # ========== 底部选择信息栏 ==========

    def is_selection_info_bar_visible(self) -> bool:
        """检查底部选择信息栏是否可见"""
        return self.is_visible_by_testid(self.SELECTION_INFO_BAR)

    def get_selected_count(self) -> str:
        """获取已选文件数量文本"""
        return self.get_text_by_testid(self.SELECTED_COUNT)

    def get_selected_size(self) -> str:
        """获取已选文件总大小文本"""
        return self.get_text_by_testid(self.SELECTED_SIZE)

    def click_upload_btn_bottom(self) -> None:
        """点击底部上传按钮"""
        self.click_by_testid(self.UPLOAD_BTN_BOTTOM)

    # ========== 上传弹窗 ==========

    def is_upload_modal_visible(self) -> bool:
        """检查上传弹窗是否可见"""
        return self.is_visible_by_testid(self.UPLOAD_MODAL)

    def wait_for_upload_modal(self, timeout: int = 10000) -> None:
        """等待上传弹窗出现"""
        self.wait_for_selector(self.UPLOAD_MODAL, timeout)

    def close_upload_modal(self) -> None:
        """关闭上传弹窗"""
        self.click_by_testid(self.MODAL_CLOSE_BTN)

    def fill_upload_target(self, target: str) -> None:
        """填写上传目标频道"""
        self.fill_by_testid(self.UPLOAD_TARGET_INPUT, target)

    def get_upload_target_value(self) -> str:
        """获取上传目标频道的值"""
        return self.get_value_by_testid(self.UPLOAD_TARGET_INPUT)

    def set_media_group_checkbox(self, checked: bool) -> None:
        """设置媒体组checkbox状态"""
        self.set_checked_by_testid(self.UPLOAD_MEDIA_GROUP_CHECKBOX, checked)

    def is_media_group_checked(self) -> bool:
        """检查媒体组checkbox是否勾选"""
        return self.is_checked_by_testid(self.UPLOAD_MEDIA_GROUP_CHECKBOX)

    def set_delete_checkbox(self, checked: bool) -> None:
        """设置删除后上传checkbox状态"""
        self.set_checked_by_testid(self.UPLOAD_DELETE_CHECKBOX, checked)

    def is_delete_checked(self) -> bool:
        """检查删除后上传checkbox是否勾选"""
        return self.is_checked_by_testid(self.UPLOAD_DELETE_CHECKBOX)

    def click_upload_cancel(self) -> None:
        """点击取消上传按钮"""
        self.click_by_testid(self.UPLOAD_CANCEL_BTN)

    def click_submit_upload(self) -> None:
        """点击开始上传按钮"""
        self.click_by_testid(self.UPLOAD_SUBMIT_BTN)

    # ========== 综合操作 ==========

    def open_upload_modal(self) -> None:
        """打开上传弹窗（点击底部上传按钮）"""
        self.click_upload_btn_bottom()
        self.wait_for_upload_modal()

    def fill_upload_form(
        self,
        target: str,
        media_group: bool = True,
        delete_after: bool = False,
    ) -> None:
        """填写上传表单"""
        self.fill_upload_target(target)
        self.set_media_group_checkbox(media_group)
        self.set_delete_checkbox(delete_after)

    def select_files(self, indices: list[int]) -> None:
        """选择多个文件"""
        for index in indices:
            self.click_file_checkbox(index)

    def upload_files(
        self,
        indices: list[int],
        target: str,
        media_group: bool = True,
        delete_after: bool = False,
    ) -> None:
        """
        快捷上传文件流程

        Args:
            indices: 文件索引列表
            target: 目标频道
            media_group: 是否发送为媒体组
            delete_after: 是否上传后删除
        """
        # 选择文件
        self.select_files(indices)

        # 等待底部信息栏出现
        self.page.wait_for_timeout(500)

        # 打开上传弹窗
        self.open_upload_modal()

        # 填写表单
        self.fill_upload_form(target, media_group, delete_after)

        # 提交上传
        self.click_submit_upload()
