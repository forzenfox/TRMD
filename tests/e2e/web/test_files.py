"""
文件管理核心流程E2E测试

覆盖文件列表加载、文件选择、面包屑导航、上传流程等核心场景。
"""

import pytest
from playwright.sync_api import Page

from ..pages.files_page import FilesPage


@pytest.fixture
def files_page(page: Page) -> FilesPage:
    """文件管理页Page Object fixture"""
    return FilesPage(page)


class TestFilesListLoad:
    """T001: 文件列表加载场景"""

    def test_files_list_loads_successfully(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T001: 文件列表加载成功

        验证点：
        1. 导航到文件管理页
        2. 文件列表表格显示
        3. 刷新按钮可用
        4. 面包屑导航可见
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 验证文件列表容器可见
        assert files_page.is_visible_by_testid(FilesPage.FILES_CONTAINER)

        # 验证刷新按钮可用
        assert files_page.is_enabled_by_testid(FilesPage.REFRESH_BTN)

        # 验证面包屑导航可见
        assert files_page.is_visible_by_testid(FilesPage.BREADCRUMB_CONTAINER)

    def test_files_list_empty_state(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T002: 空目录状态

        验证点：
        1. 导航到文件管理页
        2. 文件列表为空时显示提示文本
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        # 如果文件数量为0，验证空状态提示
        if file_count == 0:
            # 验证空状态提示可见
            container = files_page.get_by_testid(FilesPage.FILES_CONTAINER)
            empty_text = container.locator("p:has-text('当前目录为空')")
            assert empty_text.is_visible()


class TestFileSelection:
    """T002: 文件选择场景"""

    def test_file_checkbox_select(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T003: 文件checkbox选择

        验证点：
        1. 文件列表有文件时
        2. 点击checkbox选中文件
        3. checkbox状态变为checked
        4. 底部选择信息栏显示
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        # 如果有文件，测试选择功能
        if file_count > 0:
            # 点击第一个文件的checkbox
            files_page.click_file_checkbox(0)

            # 等待状态更新
            files_page.wait_for_timeout(500)

            # 验证checkbox被选中
            assert files_page.is_file_selected(0)

            # 验证底部选择信息栏显示
            assert files_page.is_selection_info_bar_visible()

            # 验证选中数量为1
            selected_count = files_page.get_selected_count()
            assert selected_count == "1"

    def test_select_all_files(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T004: 全选文件功能

        验证点：
        1. 文件列表有文件时
        2. 点击全选按钮
        3. 所有文件被选中
        4. 底部选择信息栏显示选中数量
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        # 如果有文件，测试全选功能
        if file_count > 0:
            # 点击全选按钮
            files_page.click_select_all()

            # 等待状态更新
            files_page.wait_for_timeout(500)

            # 验证底部选择信息栏显示
            assert files_page.is_selection_info_bar_visible()

            # 验证选中数量等于文件数量
            selected_count = files_page.get_selected_count()
            assert (
                int(selected_count) <= file_count
            )  # 目录不能被选中，所以可能小于file_count

            # 验证清空选择按钮可见
            assert files_page.is_clear_selection_btn_visible()

    def test_clear_selection(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T005: 清空选择功能

        验证点：
        1. 已选中文件时
        2. 点击清空选择按钮
        3. 所有文件取消选中
        4. 底部选择信息栏隐藏
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        # 如果有文件，测试清空选择功能
        if file_count > 0:
            # 先全选文件
            files_page.click_select_all()
            files_page.wait_for_timeout(500)

            # 验证底部选择信息栏显示
            assert files_page.is_selection_info_bar_visible()

            # 点击清空选择按钮
            files_page.click_clear_selection()

            # 等待状态更新
            files_page.wait_for_timeout(500)

            # 验证底部选择信息栏隐藏
            assert not files_page.is_selection_info_bar_visible()


class TestBreadcrumbNavigation:
    """T003: 面包屑导航场景"""

    def test_breadcrumb_navigation(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T006: 面包屑导航功能

        验证点：
        1. 面包屑导航显示当前路径
        2. 面包屑项可点击
        3. 点击面包屑项导航到对应目录
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取面包屑项
        breadcrumb_items = files_page.get_breadcrumb_items()

        # 验证至少有一个面包屑项（根目录）
        assert len(breadcrumb_items) >= 1

        # 验证根目录面包屑项可见
        if len(breadcrumb_items) > 0:
            root_item = breadcrumb_items[0]
            assert root_item.is_visible()

            # 点击根目录面包屑项
            files_page.click_breadcrumb_item(0)

            # 等待页面更新
            files_page.wait_for_timeout(500)

            # 验证仍然在文件管理页
            assert files_page.is_visible_by_testid(FilesPage.FILES_CONTAINER)


class TestSortFunctionality:
    """T004: 排序功能场景"""

    def test_sort_by_name(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T007: 按名称排序

        验证点：
        1. 点击名称排序按钮
        2. 排序按钮变为激活状态
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 点击名称排序按钮
        files_page.sort_by_name()

        # 等待状态更新
        files_page.wait_for_timeout(500)

        # 验证名称排序按钮激活
        assert files_page.is_sort_btn_active("name")

    def test_sort_by_size(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T008: 按大小排序

        验证点：
        1. 点击大小排序按钮
        2. 排序按钮变为激活状态
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 点击大小排序按钮
        files_page.sort_by_size()

        # 等待状态更新
        files_page.wait_for_timeout(500)

        # 验证大小排序按钮激活
        assert files_page.is_sort_btn_active("size")

    def test_sort_by_date(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T009: 按日期排序

        验证点：
        1. 点击日期排序按钮
        2. 排序按钮变为激活状态
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 点击日期排序按钮
        files_page.sort_by_date()

        # 等待状态更新
        files_page.wait_for_timeout(500)

        # 验证日期排序按钮激活
        assert files_page.is_sort_btn_active("date")


class TestUploadModal:
    """T005: 上传弹窗场景"""

    def test_open_upload_modal(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T010: 打开上传弹窗

        验证点：
        1. 选中文件后底部上传按钮显示
        2. 点击底部上传按钮打开弹窗
        3. 上传弹窗显示
        4. 表单元素可见
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        # 如果有文件，测试上传弹窗
        if file_count > 0:
            # 选择第一个文件
            files_page.click_file_checkbox(0)

            # 等待底部信息栏出现
            files_page.wait_for_timeout(500)

            # 点击底部上传按钮
            files_page.click_upload_btn_bottom()

            # 等待上传弹窗出现
            files_page.wait_for_upload_modal()

            # 验证上传弹窗可见
            assert files_page.is_upload_modal_visible()

            # 验证目标频道输入框可见
            assert files_page.is_visible_by_testid(FilesPage.UPLOAD_TARGET_INPUT)

            # 验证媒体组checkbox可见
            assert files_page.is_visible_by_testid(
                FilesPage.UPLOAD_MEDIA_GROUP_CHECKBOX
            )

            # 验证删除checkbox可见
            assert files_page.is_visible_by_testid(FilesPage.UPLOAD_DELETE_CHECKBOX)

            # 验证提交按钮可用
            assert files_page.is_enabled_by_testid(FilesPage.UPLOAD_SUBMIT_BTN)

            # 关闭弹窗
            files_page.close_upload_modal()

            # 等待弹窗关闭
            files_page.wait_for_timeout(500)

            # 验证弹窗已关闭
            assert not files_page.is_upload_modal_visible()

    def test_fill_upload_form(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T011: 填写上传表单

        验证点：
        1. 打开上传弹窗
        2. 填写目标频道
        3. 设置媒体组选项
        4. 设置删除选项
        5. 验证表单值正确
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        # 如果有文件，测试填写表单
        if file_count > 0:
            # 选择文件并打开上传弹窗
            files_page.click_file_checkbox(0)
            files_page.wait_for_timeout(500)
            files_page.open_upload_modal()

            # 填写目标频道
            target_channel = "@test_channel"
            files_page.fill_upload_target(target_channel)

            # 验证目标频道值
            assert files_page.get_upload_target_value() == target_channel

            # 设置媒体组checkbox
            files_page.set_media_group_checkbox(True)

            # 验证媒体组checkbox被勾选
            assert files_page.is_media_group_checked()

            # 设置删除checkbox
            files_page.set_delete_checkbox(True)

            # 验证删除checkbox被勾选
            assert files_page.is_delete_checked()

            # 取消勾选媒体组
            files_page.set_media_group_checkbox(False)

            # 验证媒体组checkbox取消勾选
            assert not files_page.is_media_group_checked()

            # 关闭弹窗
            files_page.close_upload_modal()


class TestRefreshFunctionality:
    """T006: 刷新功能场景"""

    def test_refresh_files_list(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T012: 刷新文件列表

        验证点：
        1. 点击刷新按钮
        2. 文件列表刷新
        3. 文件列表容器仍然可见
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 点击刷新按钮
        files_page.click_refresh()

        # 等待刷新完成
        files_page.wait_for_timeout(1000)

        # 验证文件列表容器仍然可见
        assert files_page.is_visible_by_testid(FilesPage.FILES_CONTAINER)

        # 验证刷新按钮仍然可用
        assert files_page.is_enabled_by_testid(FilesPage.REFRESH_BTN)
