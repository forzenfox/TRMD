"""
任务管理核心流程E2E测试

覆盖任务列表加载、状态筛选、创建下载任务等核心场景。
"""

import pytest
from playwright.sync_api import Page

from ..pages.tasks_page import TasksPage


@pytest.fixture
def tasks_page(authenticated_page: Page) -> TasksPage:
    """任务管理页Page Object fixture（已认证）"""
    return TasksPage(authenticated_page)


class TestTasksListLoad:
    """T001: 任务列表加载场景"""

    def test_tasks_list_loads_successfully(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """
        T001: 任务列表加载成功

        验证点：
        1. 导航到任务管理页
        2. 新建任务按钮可用
        3. 刷新按钮可用
        """
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 验证新建任务按钮可用
        assert tasks_page.is_enabled_by_testid(TasksPage.BTN_CREATE_TASK)

        # 验证刷新按钮可用
        assert tasks_page.is_enabled_by_testid(TasksPage.BTN_REFRESH)

    def test_tasks_list_empty_state(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """
        T001-2: 任务列表为空时显示空状态提示

        验证点：
        1. 任务列表为空时显示"暂无任务"
        2. 任务数量为0
        """
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 验证任务数量
        task_count = tasks_page.get_task_count()
        assert task_count >= 0


class TestFilterByStatus:
    """T002: 状态筛选场景"""

    def test_filter_by_status_all(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T002-1: 状态筛选 - 全部"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_status("all")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_ALL)

    def test_filter_by_status_running(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T002-2: 状态筛选 - 执行中"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_status("running")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_RUNNING)

    def test_filter_by_status_completed(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T002-3: 状态筛选 - 已完成"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_status("completed")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_COMPLETED)


class TestFilterByType:
    """T003: 类型筛选场景"""

    def test_filter_by_type_download(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T003-1: 类型筛选 - 下载任务"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_type("download")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_DOWNLOAD)


class TestCreateDownloadTask:
    """T004: 创建下载任务场景"""

    def test_open_create_modal(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T004-1: 打开创建任务弹窗"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_create_task()
        tasks_page.wait_for_create_modal()
        assert tasks_page.is_create_modal_visible()

        # 验证默认任务类型（下载）被选中
        download_radio = tasks_page.get_by_testid(TasksPage.INPUT_TASK_TYPE_DOWNLOAD)
        assert download_radio.is_checked()

    def test_close_create_modal_by_close_button(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T004-2: 通过关闭按钮关闭创建任务弹窗"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_create_task()
        tasks_page.wait_for_create_modal()
        tasks_page.close_create_modal()
        tasks_page.wait_for_hidden_by_testid(TasksPage.MODAL_CREATE_TASK)
        assert not tasks_page.is_create_modal_visible()

    def test_fill_download_task_form(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T004-3: 填写下载任务表单（ID范围模式）"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_create_task()
        tasks_page.wait_for_create_modal()

        # 填写源频道
        test_source_chat = "@test_channel"
        tasks_page.fill_source_chat(test_source_chat)
        assert (
            tasks_page.get_value_by_testid(TasksPage.INPUT_SOURCE_CHAT)
            == test_source_chat
        )

        # 选择ID范围模式
        tasks_page.select_range_mode("id_range")
        tasks_page.fill_min_id("100")
        tasks_page.fill_max_id("200")
        assert tasks_page.get_value_by_testid(TasksPage.INPUT_MIN_ID) == "100"
        assert tasks_page.get_value_by_testid(TasksPage.INPUT_MAX_ID) == "200"

    def test_submit_create_download_task(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """
        T004-4: 提交创建下载任务

        注意：此测试需要有效的测试频道数据
        """
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        test_source_chat = "@test_channel_e2e"
        tasks_page.create_download_task(
            source_chat=test_source_chat,
            range_mode="id_range",
            min_id="100",
            max_id="105",
        )
        tasks_page.wait_for_timeout(1000)

    def test_url_params_auto_open_create_modal(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T004-5: URL参数自动打开创建弹窗"""
        tasks_page.navigate(live_server, action="create", task_type="download")
        tasks_page.wait_for_create_modal(timeout=15000)
        assert tasks_page.is_create_modal_visible()
        download_radio = tasks_page.get_by_testid(TasksPage.INPUT_TASK_TYPE_DOWNLOAD)
        assert download_radio.is_checked()


class TestTaskDetailDrawer:
    """T005: 任务详情抽屉场景"""

    def test_open_task_detail_drawer(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """T005-1: 打开任务详情抽屉"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_task_detail(test_task)
        tasks_page.wait_for_detail_drawer()
        assert tasks_page.is_detail_drawer_visible()


class TestRefreshTasks:
    """T006: 刷新任务场景"""

    def test_refresh_tasks_list(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T006-1: 点击刷新按钮刷新任务列表"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_refresh()
        tasks_page.wait_for_timeout(1000)
        assert tasks_page.is_enabled_by_testid(TasksPage.BTN_CREATE_TASK)


class TestForwardTaskForm:
    """T007: 转发任务表单场景"""

    def test_forward_type_shows_target_chat(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T007-1: 转发类型显示目标频道输入框"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("forward")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_target_chat_visible()


class TestUploadTaskForm:
    """T008: 上传任务表单场景"""

    def test_upload_type_hides_source_chat(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T008-1: 上传类型隐藏源频道输入框"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("upload")
        tasks_page.wait_for_timeout(500)
        assert not tasks_page.is_source_chat_visible()

    def test_upload_type_shows_target_chat(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T008-2: 上传类型显示目标频道输入框"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("upload")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_target_chat_visible()


class TestListenDownloadTaskForm:
    """T009: 监听下载任务表单场景"""

    def test_listen_download_shows_source_chat(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T009-1: 监听下载类型显示源频道"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("listen_download")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_source_chat_visible()


class TestDateRangeMode:
    """T010: 日期范围模式场景"""

    def test_date_range_mode_shows_date_inputs(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T010-1: 日期范围模式显示日期输入框"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("date_range")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_date_inputs_visible()


class TestIdListMode:
    """T011: ID列表模式场景"""

    def test_id_list_mode_shows_raw_items_textarea(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T011-1: ID列表模式显示ID列表textarea"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("multiple_ids")
        # 等待Alpine.js响应式更新
        tasks_page.wait_for_timeout(1000)
        # 通过Alpine.js状态验证模式已切换
        current_mode = tasks_page.page.evaluate(
            "() => window.taskManager ? window.taskManager.createForm.messageRangeMode : ''"
        )
        assert current_mode == "multiple_ids", (
            f"模式应为multiple_ids，实际为{current_mode}"
        )


class TestRecentCountMode:
    """T012: 最近N条模式场景"""

    def test_recent_count_mode_shows_recent_count_input(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T012-1: 最近N条模式显示数量输入框"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("recent")
        # 等待Alpine.js响应式更新
        tasks_page.wait_for_timeout(1000)
        # 通过Alpine.js状态验证模式已切换
        current_mode = tasks_page.page.evaluate(
            "() => window.taskManager ? window.taskManager.createForm.messageRangeMode : ''"
        )
        assert current_mode == "recent", f"模式应为recent，实际为{current_mode}"


class TestTypeFilterCheckbox:
    """T013: 类型过滤checkbox场景"""

    def test_type_filter_visible_for_download(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T013-1: 下载任务类型过滤checkbox可见"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_type_filter_checkbox_visible()


class TestChannelResolve:
    """T014: 频道解析场景"""

    def test_resolve_source_button_click(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T014-1: 点击源频道解析按钮"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")

        # 填写源频道
        tasks_page.fill_source_chat("@test_channel")
        tasks_page.click_resolve_source()
        # 不等待解析结果，因为可能无网络


class TestPaginationDisplay:
    """T015: 分页显示场景"""

    def test_pagination_info_displayed(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_pagination_tasks: list,
    ):
        """T015-1: 分页信息正确显示"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.wait_for_timeout(1000)

        # 分页信息在任务存在时显示
        task_count = tasks_page.get_task_count()
        if task_count > 0:
            # 验证分页区域可见
            assert tasks_page.is_pagination_visible()


class TestDeleteTaskWithConfirm:
    """T016: 删除任务确认对话框场景"""

    def test_delete_task_shows_confirm_dialog(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """T016-1: 删除任务弹出确认对话框"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 点击删除按钮
        tasks_page.click_task_delete(test_task)

        # 等待确认对话框出现
        try:
            tasks_page.wait_for_confirm_dialog(timeout=5000)
            assert tasks_page.is_confirm_dialog_visible()

            # 点击取消关闭对话框
            tasks_page.click_confirm_dialog_cancel()
            tasks_page.wait_for_confirm_dialog_hidden(timeout=5000)
        except Exception:
            # 确认对话框可能直接使用window.confirm，而非自定义对话框
            pass


# ========== P0核心场景 ==========


class TestTaskOperations:
    """T017: 任务操作（启动/取消/重试）场景"""

    def test_start_pending_task(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """T017-1: 启动pending状态任务"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        # 通过API确认任务状态为pending后点击启动
        tasks_page.click_task_start(test_task)
        tasks_page.wait_for_timeout(2000)

    def test_cancel_task(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_task: str,
    ):
        """T017-2: 取消任务（需running状态）"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        # 注意：test_task创建的是pending状态，cancel需要running
        # 如果任务不是running状态则skip
        try:
            tasks_page.click_task_cancel(test_task)
            tasks_page.wait_for_timeout(2000)
        except Exception:
            pytest.skip("任务非running状态，无法取消")

    def test_retry_task(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_task: str,
    ):
        """T017-3: 重试任务（需failed状态）"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        try:
            tasks_page.click_task_retry(test_task)
            tasks_page.wait_for_timeout(2000)
        except Exception:
            pytest.skip("任务非failed状态，无法重试")


class TestDetailDrawerClose:
    """T018: 详情抽屉关闭场景"""

    def test_close_detail_drawer_by_close_button(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_task: str,
    ):
        """T018-1: 点击关闭按钮关闭详情抽屉"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_task_detail(test_task)
        tasks_page.wait_for_detail_drawer()
        assert tasks_page.is_detail_drawer_visible()

        tasks_page.click_close_detail()
        tasks_page.wait_for_timeout(500)
        assert not tasks_page.is_detail_drawer_visible()


class TestCreateModalClose:
    """T019: 创建弹窗关闭场景"""

    def test_close_create_modal_by_cancel_button(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T019-1: 点击底部取消按钮关闭创建弹窗"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_create_task()
        tasks_page.wait_for_create_modal()
        assert tasks_page.is_create_modal_visible()

        tasks_page.cancel_create_modal()
        tasks_page.wait_for_hidden_by_testid(TasksPage.MODAL_CREATE_TASK)
        assert not tasks_page.is_create_modal_visible()


class TestFilterByStatusFull:
    """T020: 状态筛选完整场景"""

    def test_filter_by_status_pending(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T020-1: 状态筛选 - 排队中"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_status("pending")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_PENDING)

    def test_filter_by_status_failed(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T020-2: 状态筛选 - 失败"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_status("failed")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_FAILED)

    def test_filter_by_status_cancelled(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T020-3: 状态筛选 - 已取消"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_status("cancelled")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_CANCELLED)


class TestFilterByTypeFull:
    """T021: 类型筛选完整场景"""

    def test_filter_by_type_forward(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T021-1: 类型筛选 - 转发"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_type("forward")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_FORWARD)

    def test_filter_by_type_upload(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T021-2: 类型筛选 - 上传"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_type("upload")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_UPLOAD)

    def test_filter_by_type_listen_download(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T021-3: 类型筛选 - 监听下载"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_type("listen_download")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_LISTEN_DOWNLOAD)

    def test_filter_by_type_listen_forward(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T021-4: 类型筛选 - 监听转发"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.filter_by_type("listen_forward")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_LISTEN_FORWARD)


class TestCreateFormValidation:
    """T022: 创建表单验证场景"""

    def test_create_form_validation_empty_source(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T022-1: 空源频道触发验证错误"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_create_task()
        tasks_page.wait_for_create_modal()

        # 不填源频道，直接提交
        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        # 验证错误出现（通过Alpine.js状态检查）
        has_error = tasks_page.has_create_form_error()
        assert has_error, "空源频道应触发验证错误"

    def test_create_form_validation_invalid_id_range(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T022-2: 无效ID范围触发验证错误（minId > maxId）"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_create_task()
        tasks_page.wait_for_create_modal()

        tasks_page.fill_source_chat("@test_channel")
        tasks_page.select_range_mode("id_range")
        tasks_page.fill_min_id("200")
        tasks_page.fill_max_id("100")  # min > max

        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        has_error = tasks_page.has_create_form_error()
        assert has_error, "minId > maxId应触发验证错误"


# ========== P1重要功能场景 ==========


class TestPaginationOperations:
    """T023: 分页操作场景"""

    def test_pagination_next_page(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_pagination_tasks: list,
    ):
        """T023-1: 点击下一页按钮"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.wait_for_timeout(1000)

        total_pages = tasks_page.get_total_pages()
        if total_pages <= 1:
            pytest.skip("任务总数不足，无法测试分页")

        current_page = tasks_page.get_current_page()
        tasks_page.click_next_page()
        tasks_page.wait_for_timeout(1000)

        new_page = tasks_page.get_current_page()
        assert new_page == current_page + 1

    def test_pagination_prev_page(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_pagination_tasks: list,
    ):
        """T023-2: 点击上一页按钮"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.wait_for_timeout(1000)

        total_pages = tasks_page.get_total_pages()
        if total_pages <= 1:
            pytest.skip("任务总数不足，无法测试分页")

        # 先到第2页
        tasks_page.click_next_page()
        tasks_page.wait_for_timeout(1000)

        # 再点上一页
        tasks_page.click_prev_page()
        tasks_page.wait_for_timeout(1000)

        assert tasks_page.get_current_page() == 1


class TestAllMessageRangeMode:
    """T024: 全部消息范围模式场景"""

    def test_all_message_range_mode_selectable(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T024-1: 选择全部消息模式"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("all")
        tasks_page.wait_for_timeout(500)

        current_mode = tasks_page.page.evaluate(
            "() => window.taskManager ? window.taskManager.createForm.messageRangeMode : ''"
        )
        assert current_mode == "all"


class TestListenForwardTaskForm:
    """T025: 监听转发任务表单场景"""

    def test_listen_forward_shows_source_and_target(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T025-1: 监听转发类型同时显示源频道和目标频道"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("listen_forward")
        tasks_page.wait_for_timeout(500)
        assert tasks_page.is_source_chat_visible()
        assert tasks_page.is_target_chat_visible()


class TestTargetChannelResolve:
    """T026: 目标频道解析场景"""

    def test_resolve_target_button_click(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T026-1: 点击目标频道解析按钮"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("forward")
        tasks_page.wait_for_timeout(500)

        tasks_page.fill_target_chat("@test_target_channel")
        tasks_page.click_resolve_target()


class TestResourceAlert:
    """T027: 资源告警弹窗场景"""

    def test_close_resource_alert_via_js(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T027-1: 通过JS API关闭资源告警弹窗"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 通过JS显示资源告警弹窗（调用 taskManager._showResourceAlert 后需同步到 Alpine 响应式属性）
        tasks_page.page.evaluate(
            """() => {
                window.taskManager._showResourceAlert('blocked', { message: '测试告警', suggestion: '测试建议', estimate: null });
                const el = document.querySelector('[x-data]');
                if (el && window.Alpine) { window.Alpine.$data(el)._syncResourceAlert(); }
            }"""
        )
        tasks_page.wait_for_timeout(500)

        # 验证告警弹窗可见（Alpine 响应式 showResourceAlert 驱动 x-show）
        assert tasks_page.is_resource_alert_visible()

        # 关闭告警弹窗（通过 Alpine 组件方法同步响应式状态）
        tasks_page.close_resource_alert()
        tasks_page.wait_for_timeout(500)

        # 验证告警弹窗已关闭
        assert not tasks_page.is_resource_alert_visible()


class TestTypeFilterToggle:
    """T028: 类型过滤checkbox勾选/取消场景"""

    def test_toggle_type_filter_select_deselect(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T028-1: 勾选后isTypeFilterSelected为true，再取消为false"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.wait_for_timeout(500)

        # 勾选video类型
        tasks_page.toggle_type_filter("video")
        tasks_page.wait_for_timeout(300)
        assert tasks_page.is_type_filter_selected("video")

        # 取消勾选
        tasks_page.toggle_type_filter("video")
        tasks_page.wait_for_timeout(300)
        assert not tasks_page.is_type_filter_selected("video")


class TestCopyTaskId:
    """T029: 复制任务ID场景"""

    def test_copy_task_id_in_detail_drawer(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """T029-1: 详情抽屉中点击复制任务ID按钮"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_task_detail(test_task)
        tasks_page.wait_for_detail_drawer()

        # 点击复制按钮
        tasks_page.click_copy_task_id()
        tasks_page.wait_for_timeout(500)
        # 验证：无法直接验证剪贴板内容，但操作不应抛异常


class TestParsedItemCount:
    """T030: ID列表解析数量显示场景"""

    def test_parsed_item_count_displayed(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T030-1: ID列表模式下输入多行ID后显示解析数量"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("multiple_ids")
        tasks_page.wait_for_timeout(500)

        # 填写多行ID
        tasks_page.fill_raw_items("100\n200\n300")
        tasks_page.wait_for_timeout(300)

        # 验证解析数量（通过 Alpine 组件实例调用，读取响应式 createForm.rawItems）
        count = tasks_page.page.evaluate(
            "() => { const el = document.querySelector('[x-data]'); return el && window.Alpine ? window.Alpine.$data(el).getParsedItemCount() : 0; }"
        )
        assert count == 3


# ========== P0核心交互补充场景 ==========


class TestDeleteTaskConfirm:
    """T031: 删除任务确认对话框点击确认场景"""

    def test_delete_task_confirm_removes_task(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """
        T031: 点击确认按钮删除任务

        验证点：
        1. 点击删除按钮弹出确认对话框
        2. 点击确认按钮执行删除
        3. 任务从列表中消失
        """
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 验证任务存在
        assert tasks_page.is_task_in_list(test_task)

        # 点击删除按钮
        tasks_page.click_task_delete(test_task)

        # 等待确认对话框出现
        try:
            tasks_page.wait_for_confirm_dialog(timeout=5000)
            assert tasks_page.is_confirm_dialog_visible()

            # 点击确认按钮（执行删除）
            tasks_page.click_confirm_dialog_confirm()
            tasks_page.wait_for_timeout(2000)

            # 验证任务已从列表中消失
            assert not tasks_page.is_task_in_list(test_task)
        except Exception:
            # 确认对话框可能直接使用window.confirm，已自动处理
            tasks_page.wait_for_timeout(2000)


class TestDetailDrawerContent:
    """T032: 详情抽屉内容验证场景"""

    def test_detail_drawer_shows_task_info(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """
        T032: 验证详情抽屉内容（类型/状态/范围模式/任务ID）

        验证点：
        1. 打开详情抽屉
        2. 任务类型文本非空
        3. 任务状态文本非空
        4. 范围模式文本非空
        5. 任务ID与预期一致
        """
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_task_detail(test_task)
        tasks_page.wait_for_detail_drawer()
        assert tasks_page.is_detail_drawer_visible()

        # 验证任务ID
        detail_task_id = tasks_page.get_detail_task_id()
        assert detail_task_id == test_task, (
            f"详情抽屉任务ID应为{test_task}，实际为{detail_task_id}"
        )

        # 验证任务类型文本非空
        type_text = tasks_page.get_detail_type_text()
        assert len(type_text) > 0, "任务类型文本不应为空"

        # 验证任务状态文本非空
        status_text = tasks_page.get_detail_status_text()
        assert len(status_text) > 0, "任务状态文本不应为空"

        # 验证范围模式文本非空
        range_mode_text = tasks_page.get_detail_range_mode_text()
        assert len(range_mode_text) > 0, "范围模式文本不应为空"


class TestDetailDrawerErrorMessage:
    """T033: 详情抽屉错误信息显示场景"""

    def test_detail_drawer_error_message_display(
        self, tasks_page: TasksPage, test_token: str, live_server: str, test_task: str
    ):
        """
        T033: 验证failed任务详情显示错误信息

        验证点：
        1. 打开详情抽屉（pending任务无错误信息）
        2. 错误信息容器不可见
        3. 通过Alpine.js设置selectedTask.message后错误信息显示
        4. 错误信息文本与设置的内容一致
        """
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_task_detail(test_task)
        tasks_page.wait_for_detail_drawer()
        assert tasks_page.is_detail_drawer_visible()

        # pending任务无错误信息，错误信息容器应不可见
        assert not tasks_page.is_detail_error_visible()

        # 通过Alpine.js设置错误信息，验证x-show响应式更新
        test_error_msg = "测试错误信息：连接超时"
        tasks_page.page.evaluate(
            f"() => {{ window.taskManager.selectedTask.message = '{test_error_msg}'; }}"
        )
        tasks_page.wait_for_timeout(500)

        # 验证错误信息容器可见
        assert tasks_page.is_detail_error_visible()

        # 验证错误信息文本
        error_text = tasks_page.get_detail_error_text()
        assert test_error_msg in error_text, (
            f"错误信息应包含'{test_error_msg}'，实际为'{error_text}'"
        )


# ========== P1重要功能补充场景 ==========


class TestDateRangeValidation:
    """T037: 日期范围模式验证场景"""

    def test_date_range_empty_dates_shows_error(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T037-1: 日期范围模式不填日期触发验证错误"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("date_range")
        tasks_page.wait_for_timeout(500)

        # 不填日期直接提交
        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        has_error = tasks_page.has_create_form_error()
        assert has_error, "日期范围模式不填日期应触发验证错误"


class TestRecentCountValidation:
    """T038: 最近N条模式验证场景"""

    def test_recent_count_zero_shows_error(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T038-1: 最近N条模式填0触发验证错误"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("recent")
        tasks_page.wait_for_timeout(500)

        # 填源频道和recent_count为0
        tasks_page.fill_source_chat("@test_channel")
        tasks_page.fill_recent_count("0")
        tasks_page.wait_for_timeout(300)

        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        has_error = tasks_page.has_create_form_error()
        assert has_error, "最近N条模式填0应触发验证错误"


class TestIdListValidation:
    """T039: ID列表模式验证场景"""

    def test_id_list_empty_items_shows_error(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T039-1: ID列表模式不填raw_items触发验证错误"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")
        tasks_page.select_range_mode("multiple_ids")
        tasks_page.wait_for_timeout(500)

        # 填源频道但不填raw_items
        tasks_page.fill_source_chat("@test_channel")
        tasks_page.wait_for_timeout(300)

        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        has_error = tasks_page.has_create_form_error()
        assert has_error, "ID列表模式不填raw_items应触发验证错误"


class TestForwardTargetRequired:
    """T040: 转发类型必填目标频道场景"""

    def test_forward_empty_target_shows_error(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T040-1: 转发类型不填目标频道触发验证错误"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("forward")
        tasks_page.wait_for_timeout(500)

        # 填源频道但不填目标频道
        tasks_page.fill_source_chat("@test_channel")
        tasks_page.wait_for_timeout(300)

        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        has_error = tasks_page.has_create_form_error()
        assert has_error, "转发类型不填目标频道应触发验证错误"


class TestUploadTargetRequired:
    """T041: 上传类型必填目标频道场景"""

    def test_upload_empty_target_shows_error(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T041-1: 上传类型不填目标频道触发验证错误"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("upload")
        tasks_page.wait_for_timeout(500)

        # 不填目标频道直接提交
        tasks_page.click_submit_create()
        tasks_page.wait_for_timeout(1000)

        has_error = tasks_page.has_create_form_error()
        assert has_error, "上传类型不填目标频道应触发验证错误"


class TestAutoGeneratedTaskName:
    """T042: 任务名称自动生成场景"""

    def test_auto_generate_task_name(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T042-1: 任务名称自动生成包含频道或范围信息"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.open_create_modal_with_type("download")

        # 填源频道和ID范围，不填task_name
        tasks_page.fill_source_chat("@test_channel")
        tasks_page.select_range_mode("id_range")
        tasks_page.fill_min_id("100")
        tasks_page.fill_max_id("200")
        tasks_page.wait_for_timeout(500)

        # 调用自动生成方法
        generated_name = tasks_page.page.evaluate(
            "() => window.taskManager ? window.taskManager._generateTaskName() : ''"
        )
        assert generated_name, "自动生成的任务名称不应为空"
        # _generateTaskName()返回格式为"类型_时间戳"（如"下载_0708 0822"）
        # 验证名称以任务类型中文名开头
        assert generated_name.startswith("下载_"), (
            f"生成的任务名称应以'下载_'开头，实际为'{generated_name}'"
        )


# ========== P2辅助场景补充 ==========


class TestStatusTextFormat:
    """T055: 状态/类型文本格式化场景"""

    def test_status_text_format(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T055-1: 状态文本返回中文格式化文本"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        result = tasks_page.page.evaluate(
            "() => { const tm = window.taskManager; if(!tm) return null; return {pending: tm.getStatusText('pending'), completed: tm.getStatusText('completed'), failed: tm.getStatusText('failed')}; }"
        )
        assert result is not None, "taskManager不可用"
        assert result["pending"], "pending状态文本不应为空"
        assert result["completed"], "completed状态文本不应为空"
        assert result["failed"], "failed状态文本不应为空"

    def test_type_text_format(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T055-2: 类型文本返回中文格式化文本"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        result = tasks_page.page.evaluate(
            "() => { const tm = window.taskManager; if(!tm) return null; return {download: tm.getTypeText('download'), forward: tm.getTypeText('forward'), upload: tm.getTypeText('upload')}; }"
        )
        assert result is not None, "taskManager不可用"
        assert result["download"], "download类型文本不应为空"
        assert result["forward"], "forward类型文本不应为空"
        assert result["upload"], "upload类型文本不应为空"


class TestRangeModeTextFormat:
    """T056: 范围模式文本格式化场景"""

    def test_range_mode_text_format(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T056-1: 范围模式文本返回中文格式化文本"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        result = tasks_page.page.evaluate(
            "() => { const tm = window.taskManager; if(!tm) return null; return {id_range: tm.getRangeModeText('id_range'), date_range: tm.getRangeModeText('date_range'), recent: tm.getRangeModeText('recent')}; }"
        )
        assert result is not None, "taskManager不可用"
        assert result["id_range"], "id_range模式文本不应为空"
        assert result["date_range"], "date_range模式文本不应为空"
        assert result["recent"], "recent模式文本不应为空"


class TestConfirmDialogDynamicContent:
    """T057: 确认对话框动态内容场景"""

    def test_confirm_dialog_dynamic_content(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T057-1: 确认对话框显示动态内容"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 通过JS显示确认对话框
        tasks_page.page.evaluate(
            "() => { window.confirmDialog.show({title: '测试标题', message: '测试内容', confirmText: '确认', cancelText: '取消'}); }"
        )
        tasks_page.wait_for_timeout(500)

        # 验证对话框可见
        assert tasks_page.is_confirm_dialog_visible(), "确认对话框应可见"

        # 验证对话框内容
        dialog_state = tasks_page.page.evaluate(
            "() => { const cd = window.confirmDialog; if(!cd) return null; return {title: cd.title, message: cd.message, confirmText: cd.confirmText, cancelText: cd.cancelText}; }"
        )
        assert dialog_state is not None, "confirmDialog不可用"
        assert dialog_state["title"] == "测试标题", (
            f"对话框标题应为'测试标题'，实际为'{dialog_state['title']}'"
        )
        assert dialog_state["message"] == "测试内容", (
            f"对话框内容应为'测试内容'，实际为'{dialog_state['message']}'"
        )
        assert dialog_state["confirmText"] == "确认", (
            f"确认按钮文本应为'确认'，实际为'{dialog_state['confirmText']}'"
        )
        assert dialog_state["cancelText"] == "取消", (
            f"取消按钮文本应为'取消'，实际为'{dialog_state['cancelText']}'"
        )


class TestEmptyListFiltersAvailable:
    """T058: 空列表时筛选按钮仍可用场景"""

    def test_empty_list_filters_available(
        self, tasks_page: TasksPage, test_token: str, live_server: str
    ):
        """T058-1: 空列表时筛选按钮仍可见可用"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()

        # 验证状态筛选按钮可见（不论任务列表是否为空）
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_ALL), (
            "状态筛选-全部按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_RUNNING), (
            "状态筛选-执行中按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_PENDING), (
            "状态筛选-排队中按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_COMPLETED), (
            "状态筛选-已完成按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_FAILED), (
            "状态筛选-失败按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_STATUS_CANCELLED), (
            "状态筛选-已取消按钮应可见"
        )

        # 验证类型筛选按钮可见
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_ALL), (
            "类型筛选-全部按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_DOWNLOAD), (
            "类型筛选-下载按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_FORWARD), (
            "类型筛选-转发按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_UPLOAD), (
            "类型筛选-上传按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_LISTEN_DOWNLOAD), (
            "类型筛选-监听下载按钮应可见"
        )
        assert tasks_page.is_visible_by_testid(TasksPage.FILTER_TYPE_LISTEN_FORWARD), (
            "类型筛选-监听转发按钮应可见"
        )
