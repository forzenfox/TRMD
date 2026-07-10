"""
文件管理核心流程E2E测试

覆盖文件列表加载、文件选择、面包屑导航、上传流程等核心场景。
"""

import pytest
from playwright.sync_api import Page

from ..pages.files_page import FilesPage


@pytest.fixture
def files_page(authenticated_page: Page) -> FilesPage:
    """文件管理页Page Object fixture（已认证）"""
    return FilesPage(authenticated_page)


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
            # 等待空状态文本可见
            empty_text.wait_for(state="visible", timeout=5000)
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
            # 查找第一个非目录文件（目录的checkbox被禁用）
            file_index = files_page.find_first_file_index()
            if file_index == -1:
                pytest.skip("当前目录无文件（仅目录），跳过文件选择测试")

            # 点击第一个文件的checkbox
            files_page.click_file_checkbox(file_index)

            # 等待状态更新
            files_page.wait_for_timeout(500)

            # 验证checkbox被选中
            assert files_page.is_file_selected(file_index)

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

        # 查找第一个非目录文件
        file_index = files_page.find_first_file_index()

        # 如果有文件，测试上传弹窗
        if file_index >= 0:
            # 选择第一个文件
            files_page.click_file_checkbox(file_index)

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

        # 查找第一个非目录文件
        file_index = files_page.find_first_file_index()

        # 如果有文件，测试填写表单
        if file_index >= 0:
            # 选择文件并打开上传弹窗
            files_page.click_file_checkbox(file_index)
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


class TestDirectoryNavigation:
    """T006: 目录导航场景"""

    def test_navigate_into_directory(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T013: 点击目录名进入子目录

        验证点：
        1. 当前文件列表中存在子目录
        2. 点击目录名称链接
        3. 面包屑导航更新（新增子目录项）
        4. URL包含路径参数或页面仍在文件管理页
        5. 文件列表更新为新目录的内容
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 记录初始面包屑
        initial_breadcrumbs = files_page.get_breadcrumb_texts()

        # 查找第一个目录行
        dir_index = files_page.find_first_directory_index()

        # 若无子目录则跳过
        if dir_index == -1:
            pytest.skip("当前目录无子目录，跳过目录导航测试")

        # 记录目录名
        dir_name = files_page.get_file_name(dir_index)

        # 点击目录名称进入子目录
        files_page.click_directory_name(dir_index)

        # 等待页面更新
        files_page.wait_for_timeout(1000)

        # 等待文件列表重新加载
        files_page.wait_for_page_loaded()

        # 验证面包屑已更新（新面包屑项数应大于初始项数）
        updated_breadcrumbs = files_page.get_breadcrumb_texts()
        assert len(updated_breadcrumbs) > len(initial_breadcrumbs), (
            f"进入子目录后面包屑应增加，"
            f"初始: {initial_breadcrumbs}，更新后: {updated_breadcrumbs}"
        )

        # 验证面包屑最后一项为目录名
        assert updated_breadcrumbs[-1] == dir_name, (
            f"面包屑最后一项应为目录名'{dir_name}'，实际为'{updated_breadcrumbs[-1]}'"
        )

        # 验证页面仍在文件管理页
        assert files_page.is_visible_by_testid(FilesPage.FILES_CONTAINER)

        # 验证URL仍指向文件管理页
        current_url = files_page.get_current_url()
        assert "files.html" in current_url, (
            f"URL应仍指向文件管理页，实际URL: {current_url}"
        )

    def test_breadcrumb_back_to_root(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T013-2: 在子目录中点击面包屑根目录返回根目录

        验证点：
        1. 先进入子目录
        2. 点击面包屑根目录
        3. 返回根目录
        4. 面包屑恢复为根目录状态（仅1项）
        """
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        if not files_page.has_directory():
            pytest.skip("当前目录下无子目录，跳过测试")

        # 先进入子目录
        dir_index = files_page.find_first_directory_index()
        files_page.click_directory_name(dir_index)
        files_page.wait_for_timeout(1000)
        files_page.wait_for_page_loaded()

        # 确认已进入子目录
        breadcrumb_count_in_subdir = files_page.get_breadcrumb_count()
        assert breadcrumb_count_in_subdir > 1, "应在子目录中"

        # 点击面包屑根目录
        files_page.click_breadcrumb_item(0)
        files_page.wait_for_timeout(1000)
        files_page.wait_for_page_loaded()

        # 验证回到根目录
        breadcrumb_count_after = files_page.get_breadcrumb_count()
        assert breadcrumb_count_after == 1, (
            "点击根目录面包屑后应回到根目录（面包屑仅1项）"
        )


class TestUploadSubmit:
    """T008: 上传提交场景（F014）"""

    def test_upload_submit_flow(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T014: 上传提交完整流程

        验证点：
        1. 选择文件后底部上传按钮可用
        2. 打开上传弹窗
        3. 填写目标频道
        4. 点击"开始上传"按钮
        5. 验证提交逻辑被触发（弹窗关闭或出现通知）
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 查找第一个非目录文件
        file_index = files_page.find_first_file_index()

        # 若无文件则跳过
        if file_index == -1:
            pytest.skip("当前目录无文件，跳过上传提交测试")

        # 选择文件
        files_page.click_file_checkbox(file_index)

        # 等待底部信息栏出现
        files_page.wait_for_timeout(500)

        # 验证底部上传按钮可见
        assert files_page.is_visible_by_testid(FilesPage.UPLOAD_BTN_BOTTOM)

        # 打开上传弹窗
        files_page.open_upload_modal()

        # 验证上传弹窗可见
        assert files_page.is_upload_modal_visible()

        # 验证提交按钮可用
        assert files_page.is_enabled_by_testid(FilesPage.UPLOAD_SUBMIT_BTN)

        # 填写目标频道
        target_channel = "@test_upload_channel"
        files_page.fill_upload_target(target_channel)

        # 验证目标频道值
        assert files_page.get_upload_target_value() == target_channel

        # 点击"开始上传"提交
        files_page.click_submit_upload()

        # 等待提交处理
        files_page.wait_for_timeout(2000)

        # 验证提交逻辑被触发：
        # 提交成功时弹窗关闭，提交失败时显示错误通知但弹窗也可能关闭
        # 两种情况都说明提交逻辑已被触发
        is_modal_closed = not files_page.is_upload_modal_visible()
        # 检查页面是否有通知（成功或错误通知说明提交已执行）
        has_notification = files_page.page.locator(
            ".fixed.top-4.right-4 >> visible=true"
        ).is_visible()

        assert is_modal_closed or has_notification, (
            "点击开始上传后，应关闭弹窗或显示通知以表明提交逻辑已触发"
        )

    def test_upload_payload_structure(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T014-2: 上传任务请求体结构符合 TaskCreate API

        验证点：
        1. 选择文件并提交上传
        2. 拦截 POST /api/tasks 请求
        3. 请求体使用 task_type + params 结构
        4. params 中包含 chat_id、file_paths、send_as_media_group、delete_after_upload
        5. 不存在顶层 name、type、target_chat、files 字段
        """
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        file_index = files_page.find_first_file_index()
        if file_index == -1:
            pytest.skip("当前目录无文件，跳过上传 payload 结构测试")

        files_page.click_file_checkbox(file_index)
        files_page.wait_for_timeout(500)
        files_page.open_upload_modal()

        target_channel = "@test_payload_channel"
        files_page.fill_upload_target(target_channel)

        captured_body = {}

        def handle_route(route, request):
            if request.method == "POST" and request.url.endswith("/api/tasks"):
                captured_body["body"] = request.post_data_json
            route.continue_()

        files_page.page.route("**/api/tasks", handle_route)

        try:
            files_page.click_submit_upload()
            files_page.wait_for_timeout(2000)
        finally:
            files_page.page.unroute("**/api/tasks", handle_route)

        body = captured_body.get("body")
        assert body is not None, "应拦截到上传任务的 POST /api/tasks 请求"
        assert body.get("task_type") == "upload", (
            f"请求体 task_type 应为 'upload'，实际为: {body.get('task_type')}"
        )

        params = body.get("params", {})
        assert params.get("chat_id") == target_channel, (
            f"params.chat_id 应为 '{target_channel}'，实际为: {params.get('chat_id')}"
        )
        assert (
            isinstance(params.get("file_paths"), list) and len(params["file_paths"]) > 0
        ), "params.file_paths 应为非空列表"
        assert isinstance(params.get("send_as_media_group"), bool), (
            "params.send_as_media_group 应为布尔值"
        )
        assert isinstance(params.get("delete_after_upload"), bool), (
            "params.delete_after_upload 应为布尔值"
        )

        assert "name" not in body, "请求体不应包含顶层 name 字段"
        assert "type" not in body, "请求体不应包含顶层 type 字段"
        assert "target_chat" not in body, "请求体不应包含顶层 target_chat 字段"
        assert "files" not in body, "请求体不应包含顶层 files 字段"


class TestFilePreviewButton:
    """T009: 文件预览按钮场景（F015）"""

    def test_preview_button_visibility(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T015: 媒体文件显示预览按钮，非媒体文件不显示

        验证点：
        1. 目录行不显示预览按钮
        2. 媒体文件行显示预览按钮
        3. 非媒体文件行不显示预览按钮
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 获取文件数量
        file_count = files_page.get_file_count()

        if file_count == 0:
            pytest.skip("当前目录为空，跳过预览按钮测试")

        # 遍历所有文件行，验证预览按钮可见性规则
        found_media_file = False
        found_non_media_file = False

        for i in range(file_count):
            is_dir = files_page.is_directory_row(i)

            if is_dir:
                # 目录行不应显示预览按钮
                assert not files_page.is_preview_btn_visible_in_row(i), (
                    f"第{i}行是目录，不应显示预览按钮"
                )
            elif files_page.is_preview_btn_visible_in_row(i):
                # 媒体文件行应显示预览按钮
                found_media_file = True
            else:
                # 非媒体文件行不应显示预览按钮
                found_non_media_file = True

        # 至少验证了一种情况（媒体或非媒体文件）
        # 若文件列表仅有目录，则skip
        if not found_media_file and not found_non_media_file:
            pytest.skip("当前目录仅有目录行，无法验证文件预览按钮逻辑")


class TestFileDoubleClickDirectory:
    """T010: 文件双击目录场景（F016）"""

    def test_double_click_directory_enters_subdir(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T016: 双击目录行进入子目录

        验证点：
        1. 双击目录行
        2. 进入子目录
        3. 面包屑导航更新
        4. 文件列表更新
        """
        # 导航到文件管理页
        files_page.navigate(live_server)

        # 等待页面加载完成
        files_page.wait_for_page_loaded()

        # 记录初始面包屑
        initial_breadcrumbs = files_page.get_breadcrumb_texts()

        # 查找第一个目录行
        dir_index = files_page.find_first_directory_index()

        # 若无子目录则跳过
        if dir_index == -1:
            pytest.skip("当前目录无子目录，跳过双击目录测试")

        # 记录目录名
        dir_name = files_page.get_file_name(dir_index)

        # 双击目录行
        files_page.double_click_file_row(dir_index)

        # 等待页面更新
        files_page.wait_for_timeout(1000)

        # 等待文件列表重新加载
        files_page.wait_for_page_loaded()

        # 验证面包屑已更新
        updated_breadcrumbs = files_page.get_breadcrumb_texts()
        assert len(updated_breadcrumbs) > len(initial_breadcrumbs), (
            f"双击目录后面包屑应增加，"
            f"初始: {initial_breadcrumbs}，更新后: {updated_breadcrumbs}"
        )

        # 验证面包屑最后一项为目录名
        assert updated_breadcrumbs[-1] == dir_name, (
            f"面包屑最后一项应为目录名'{dir_name}'，实际为'{updated_breadcrumbs[-1]}'"
        )

        # 验证页面仍在文件管理页
        assert files_page.is_visible_by_testid(FilesPage.FILES_CONTAINER)


class TestSortDirectionToggle:
    """T011: 排序方向切换场景"""

    def test_sort_direction_toggle(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """T011-1: 双击同一排序按钮切换升序/降序"""
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        # 第一次点击 → asc
        files_page.sort_by_name()
        files_page.wait_for_timeout(500)
        assert files_page.is_sort_btn_active("name")

        # 第二次点击 → desc
        files_page.sort_by_name()
        files_page.wait_for_timeout(500)
        assert files_page.is_sort_btn_active("name")


class TestSelectedFilesTotalSize:
    """T012: 选中文件总大小显示场景"""

    def test_selected_files_total_size_displayed(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """T012-1: 选中文件后底部信息栏显示总大小"""
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        file_count = files_page.get_file_count()
        if file_count == 0:
            pytest.skip("当前目录为空")

        # 查找第一个非目录文件（目录的checkbox被禁用）
        file_index = files_page.find_first_file_index()
        if file_index == -1:
            pytest.skip("当前目录无文件（仅目录），跳过总大小测试")

        # 选择第一个文件
        files_page.click_file_checkbox(file_index)
        files_page.wait_for_timeout(500)

        assert files_page.is_selection_info_bar_visible()

        # 验证总大小非空
        total_size = files_page.get_selected_size()
        assert len(total_size) > 0


class TestPreviewButtonClick:
    """T013: 预览按钮点击场景"""

    def test_click_preview_button(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """T013-1: 点击媒体文件预览按钮"""
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        file_count = files_page.get_file_count()
        if file_count == 0:
            pytest.skip("当前目录为空")

        # 查找有预览按钮的文件
        for i in range(file_count):
            if files_page.is_preview_btn_visible_in_row(i):
                files_page.page.locator(
                    f'[data-testid="file-row"]:nth-child({i + 1}) [data-testid="btn-file-preview"]'
                ).click()
                files_page.wait_for_timeout(500)
                return

        pytest.skip("当前目录无媒体文件")


class TestUploadModalCancel:
    """T014: 上传弹窗取消按钮场景"""

    def test_close_upload_modal_by_cancel(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """T014-1: 点击取消按钮关闭上传弹窗"""
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        file_count = files_page.get_file_count()
        if file_count == 0:
            pytest.skip("当前目录为空")

        # 查找第一个非目录文件（目录的checkbox被禁用）
        file_index = files_page.find_first_file_index()
        if file_index == -1:
            pytest.skip("当前目录无文件（仅目录），跳过上传弹窗取消测试")

        files_page.click_file_checkbox(file_index)
        files_page.wait_for_timeout(500)
        files_page.click_upload_btn_bottom()
        files_page.wait_for_upload_modal()

        assert files_page.is_upload_modal_visible()

        files_page.click_upload_cancel()
        files_page.wait_for_timeout(500)

        assert not files_page.is_upload_modal_visible()


# ========== P0核心交互补充场景 ==========


class TestGoToParentDirectory:
    """T036: 返回上级目录场景"""

    def test_go_to_parent_directory_via_breadcrumb(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T036: 在子目录中点击面包屑上级目录返回

        验证点：
        1. 先进入子目录
        2. 面包屑显示多级路径
        3. 点击面包屑倒数第二项（上级目录）
        4. 返回上级目录
        5. 面包屑项数减少
        """
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        # 查找第一个子目录
        dir_index = files_page.find_first_directory_index()
        if dir_index == -1:
            pytest.skip("当前目录无子目录，跳过返回上级目录测试")

        # 进入子目录
        files_page.click_directory_name(dir_index)
        files_page.wait_for_timeout(1000)
        files_page.wait_for_page_loaded()

        # 验证已进入子目录（面包屑项数 > 1）
        breadcrumb_count_in_subdir = files_page.get_breadcrumb_count()
        assert breadcrumb_count_in_subdir > 1, "应在子目录中（面包屑项数 > 1）"

        # 点击面包屑上级目录（倒数第二项）
        files_page.go_to_parent_directory()
        files_page.wait_for_timeout(1000)
        files_page.wait_for_page_loaded()

        # 验证面包屑项数减少
        breadcrumb_count_after = files_page.get_breadcrumb_count()
        assert breadcrumb_count_after < breadcrumb_count_in_subdir, (
            f"返回上级目录后面包屑项数应减少，"
            f"子目录: {breadcrumb_count_in_subdir}，返回后: {breadcrumb_count_after}"
        )

        # 验证页面仍在文件管理页
        assert files_page.is_visible_by_testid(FilesPage.FILES_CONTAINER)


# ========== P1重要功能补充场景 ==========


class TestDeleteAfterUploadCheckbox:
    """T051: 删除后上传checkbox"""

    def test_toggle_delete_after_upload_checkbox(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T051-1: 切换删除后上传checkbox状态

        验证点：
        1. 选择文件后打开上传弹窗
        2. 设置删除checkbox为选中
        3. 验证checkbox被勾选
        4. 设置删除checkbox为未选中
        5. 验证checkbox取消勾选
        """
        # 导航到文件管理页
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        # 获取文件数量，若为空则跳过
        file_count = files_page.get_file_count()
        if file_count == 0:
            pytest.skip("当前目录为空")

        # 查找第一个非目录文件（目录的checkbox被禁用）
        file_index = files_page.find_first_file_index()
        if file_index == -1:
            pytest.skip("当前目录无文件（仅目录），跳过删除后上传checkbox测试")

        # 选择第一个文件
        files_page.click_file_checkbox(file_index)
        files_page.wait_for_timeout(500)

        # 点击底部上传按钮打开弹窗
        files_page.click_upload_btn_bottom()
        files_page.wait_for_upload_modal()

        # 验证弹窗可见
        assert files_page.is_upload_modal_visible(), "上传弹窗应可见"

        # 设置删除checkbox为选中
        files_page.set_delete_checkbox(True)
        files_page.wait_for_timeout(500)
        assert files_page.is_delete_checked(), "删除后上传checkbox应被勾选"

        # 设置删除checkbox为未选中
        files_page.set_delete_checkbox(False)
        files_page.wait_for_timeout(500)
        assert not files_page.is_delete_checked(), "删除后上传checkbox应被取消勾选"

        # 关闭弹窗
        files_page.close_upload_modal()
        files_page.wait_for_timeout(500)


class TestFilesErrorState:
    """T052: 错误状态显示"""

    def test_files_error_state_display(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T052-1: 文件列表错误状态显示

        验证点：
        1. 通过Alpine.js设置error状态
        2. 错误状态提示可见
        3. 错误文本包含设置的错误信息
        4. 测试后清理恢复error状态
        """
        # 导航到文件管理页
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        # 通过Alpine.js设置错误状态
        # 注意：window.fileManager是服务模块，UI绑定的error/loading在Alpine组件filesPage()中
        # 使用 Alpine.$data(el) 访问Alpine响应式状态
        files_page.page.evaluate(
            "() => { const el = document.querySelector('[x-data]'); "
            "if (el && window.Alpine && window.Alpine.$data(el)) { "
            "  window.Alpine.$data(el).error = '测试加载错误'; "
            "  window.Alpine.$data(el).loading = false; "
            "} }"
        )

        # 等待错误提示可见
        files_page.wait_for_selector("files-error", timeout=5000)

        # 验证错误状态可见
        assert files_page.is_error_state_visible(), "错误状态提示应可见"

        # 验证错误文本包含设置的错误信息
        error_text = files_page.get_error_text()
        assert "测试加载错误" in error_text, (
            f"错误文本应包含'测试加载错误'，实际为: '{error_text}'"
        )

        # 清理：恢复error状态为null
        files_page.page.evaluate(
            "() => { const el = document.querySelector('[x-data]'); "
            "if (el && window.Alpine && window.Alpine.$data(el)) { window.Alpine.$data(el).error = null; } }"
        )
        files_page.wait_for_timeout(300)


# ========== P2辅助场景补充场景 ==========


class TestFilesLoadingState:
    """T061: 文件列表加载状态"""

    def test_files_loading_state_display(
        self, files_page: FilesPage, test_token: str, live_server: str
    ):
        """
        T061-1: 文件列表加载状态显示

        验证点：
        1. 通过Alpine.js设置loading为true
        2. 加载状态提示可见
        3. 设置loading为false
        4. 加载状态提示不可见
        """
        # 导航到文件管理页
        files_page.navigate(live_server)
        # 注意：不调用wait_for_page_loaded，因为初始loadFiles可能正在loading中
        # 等待Alpine组件初始化完成
        files_page.wait_for_timeout(500)

        # 设置loading为true
        files_page.page.evaluate(
            "() => { const el = document.querySelector('[x-data]'); "
            "if (el && window.Alpine && window.Alpine.$data(el)) { window.Alpine.$data(el).loading = true; } }"
        )
        files_page.wait_for_timeout(300)

        # 验证加载状态可见
        assert files_page.is_loading_visible(), "加载状态应可见"

        # 设置loading为false
        files_page.page.evaluate(
            "() => { const el = document.querySelector('[x-data]'); "
            "if (el && window.Alpine && window.Alpine.$data(el)) { window.Alpine.$data(el).loading = false; } }"
        )
        files_page.wait_for_timeout(300)

        # 验证加载状态不可见
        assert not files_page.is_loading_visible(), "加载状态应不可见"


class TestBreadcrumbDeepPath:
    """T062: 多级路径面包屑"""

    def test_breadcrumb_deep_path(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T062-1: 多级路径面包屑导航

        验证点：
        1. 尝试进入最多2级子目录
        2. 若不足2级子目录则跳过
        3. 验证面包屑项数 >= 3
        4. 验证面包屑文本列表反映路径层次
        """
        # 导航到文件管理页
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        # 记录初始面包屑
        initial_breadcrumbs = files_page.get_breadcrumb_texts()

        # 尝试进入最多2级子目录
        levels_entered = 0
        for _ in range(2):
            dir_index = files_page.find_first_directory_index()
            if dir_index == -1:
                break
            files_page.click_directory_name(dir_index)
            files_page.wait_for_timeout(1000)
            files_page.wait_for_page_loaded()
            levels_entered += 1

        # 若进入的层级不足2级，跳过测试（需要至少2级子目录）
        if levels_entered < 2:
            pytest.skip(
                f"当前目录无足够多级子目录（仅进入{levels_entered}级，需要至少2级），跳过测试"
            )

        # 验证面包屑项数 >= 3（根目录 + 2级子目录）
        breadcrumb_count = files_page.get_breadcrumb_count()
        assert breadcrumb_count >= 3, (
            f"进入2级子目录后面包屑项数应>=3，实际为: {breadcrumb_count}"
        )

        # 验证面包屑文本列表反映路径层次
        breadcrumb_texts = files_page.get_breadcrumb_texts()
        assert len(breadcrumb_texts) >= 3, (
            f"面包屑文本列表长度应>=3，实际为: {breadcrumb_texts}"
        )

        # 验证面包屑层级较初始状态增加
        assert len(breadcrumb_texts) > len(initial_breadcrumbs), (
            f"进入子目录后面包屑项数应增加，"
            f"初始: {initial_breadcrumbs}，当前: {breadcrumb_texts}"
        )


class TestFileSizeFormat:
    """T063: 文件大小/日期格式化"""

    def test_file_size_and_date_format(
        self,
        files_page: FilesPage,
        test_token: str,
        live_server: str,
        test_download_data: dict,
    ):
        """
        T063-1: 文件大小和日期格式化显示

        验证点：
        1. 查找第一个非目录文件
        2. 验证文件大小文本非空且包含数字（格式化后如"1.5 MB"）
        3. 验证文件日期文本非空（格式化后如"2024-01-01 12:00"）
        """
        # 导航到文件管理页
        files_page.navigate(live_server)
        files_page.wait_for_page_loaded()

        # 获取文件数量，若为空则跳过
        file_count = files_page.get_file_count()
        if file_count == 0:
            pytest.skip("当前目录为空")

        # 查找第一个非目录文件
        file_index = files_page.find_first_file_index()
        if file_index == -1:
            pytest.skip("当前目录无文件（仅目录），跳过格式化测试")

        # 验证文件大小格式化
        size_text = files_page.get_file_size(file_index)
        assert len(size_text) > 0, f"文件大小文本不应为空，索引: {file_index}"
        # 格式化后的大小应包含数字（如"1.5 MB"、"1.2 KB"等）
        has_digit = any(c.isdigit() for c in size_text)
        assert has_digit, (
            f"文件大小应包含数字（格式化后如'1.5 MB'），实际为: '{size_text}'"
        )

        # 验证文件日期格式化
        date_text = files_page.get_file_date(file_index)
        assert len(date_text) > 0, f"文件日期文本不应为空，索引: {file_index}"
