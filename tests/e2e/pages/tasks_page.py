"""
TasksPage - 任务管理页Page Object

封装任务管理页面的交互逻辑，提供稳定的data-testid选择器接口。
"""

from playwright.sync_api import Page, Locator
from .base_page import BasePage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


class TasksPage(BasePage):
    """任务管理页Page Object"""

    # 页面路径
    URL_PATH = "/web/tasks.html"

    # data-testid常量
    # 页面头部按钮
    BTN_REFRESH = "btn-refresh-tasks"
    BTN_CREATE_TASK = "btn-create-task"

    # 状态筛选按钮
    FILTER_STATUS_ALL = "filter-status-all"
    FILTER_STATUS_RUNNING = "filter-status-running"
    FILTER_STATUS_PENDING = "filter-status-pending"
    FILTER_STATUS_COMPLETED = "filter-status-completed"
    FILTER_STATUS_FAILED = "filter-status-failed"
    FILTER_STATUS_CANCELLED = "filter-status-cancelled"

    # 类型筛选按钮
    FILTER_TYPE_ALL = "filter-type-all"
    FILTER_TYPE_DOWNLOAD = "filter-type-download"
    FILTER_TYPE_FORWARD = "filter-type-forward"
    FILTER_TYPE_UPLOAD = "filter-type-upload"
    FILTER_TYPE_LISTEN_DOWNLOAD = "filter-type-listen-download"
    FILTER_TYPE_LISTEN_FORWARD = "filter-type-listen-forward"

    # 任务列表表格
    TASKS_TABLE = "tasks-table"
    TASKS_TABLE_HEADER = "tasks-table-header"
    TASKS_TABLE_BODY = "tasks-table-body"

    # 任务行（动态ID）
    TASK_ROW_PREFIX = "task-row-"
    TASK_ID = "task-id"
    TASK_TYPE = "task-type"
    TASK_STATUS = "task-status"
    TASK_PROGRESS = "task-progress"
    TASK_CREATED_AT = "task-created-at"
    TASK_ACTIONS = "task-actions"

    # 任务行操作按钮
    BTN_TASK_START = "btn-task-start"
    BTN_TASK_CANCEL = "btn-task-cancel"
    BTN_TASK_RETRY = "btn-task-retry"
    BTN_TASK_DETAIL = "btn-task-detail"
    BTN_TASK_DELETE = "btn-task-delete"

    # 任务详情抽屉
    DRAWER_TASK_DETAIL = "drawer-task-detail"
    BTN_CLOSE_DETAIL = "btn-close-detail"
    DETAIL_TASK_ID = "detail-task-id"
    BTN_COPY_TASK_ID = "btn-copy-task-id"

    # 创建任务弹窗
    MODAL_CREATE_TASK = "modal-create-task"
    BTN_CLOSE_CREATE = "btn-close-create"
    BTN_CANCEL_CREATE = "btn-cancel-create"
    BTN_SUBMIT_CREATE = "btn-submit-create"

    # 创建任务表单
    INPUT_TASK_TYPE_DOWNLOAD = "input-task-type-download"
    INPUT_TASK_TYPE_FORWARD = "input-task-type-forward"
    INPUT_TASK_TYPE_UPLOAD = "input-task-type-upload"
    INPUT_TASK_TYPE_LISTEN_DOWNLOAD = "input-task-type-listen-download"
    INPUT_TASK_TYPE_LISTEN_FORWARD = "input-task-type-listen-forward"
    INPUT_TASK_NAME = "input-task-name"
    INPUT_SOURCE_CHAT = "input-source-chat"
    BTN_RESOLVE_SOURCE = "btn-resolve-source"
    INPUT_TARGET_CHAT = "input-target-chat"
    BTN_RESOLVE_TARGET = "btn-resolve-target"

    # 消息范围模式
    INPUT_RANGE_MODE_ID = "input-range-mode-id"
    INPUT_RANGE_MODE_DATE = "input-range-mode-date"
    INPUT_RANGE_MODE_MULTIPLE = "input-range-mode-multiple"
    INPUT_RANGE_MODE_ALL = "input-range-mode-all"
    INPUT_RANGE_MODE_RECENT = "input-range-mode-recent"

    # 消息范围输入
    INPUT_MIN_ID = "input-min-id"
    INPUT_MAX_ID = "input-max-id"
    INPUT_START_DATE = "input-start-date"
    INPUT_END_DATE = "input-end-date"
    INPUT_RAW_ITEMS = "input-raw-items"
    INPUT_RECENT_COUNT = "input-recent-count"

    # 资源保护告警弹窗
    MODAL_RESOURCE_ALERT = "modal-resource-alert"

    def __init__(self, page: Page):
        super().__init__(page)

    # ========== 导航方法 ==========

    def navigate(
        self, base_url: str, action: str = None, task_type: str = None
    ) -> None:
        """
        导航到任务管理页

        Args:
            base_url: 服务基础URL
            action: 可选，URL参数action（如create）
            task_type: 可选，URL参数type（如download）
        """
        url = f"{base_url}{self.URL_PATH}"
        if action or task_type:
            params = []
            if action:
                params.append(f"action={action}")
            if task_type:
                params.append(f"type={task_type}")
            url += "?" + "&".join(params)
        self.page.goto(url)

    def wait_for_page_loaded(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待页面加载完成"""
        # 等待任务列表表格出现
        self.wait_for_selector(self.TASKS_TABLE, timeout)

    # ========== 页面头部操作 ==========

    def click_create_task(self) -> None:
        """点击新建任务按钮"""
        self.click_by_testid(self.BTN_CREATE_TASK)

    def click_refresh(self) -> None:
        """点击刷新按钮"""
        self.click_by_testid(self.BTN_REFRESH)

    def is_refresh_button_disabled(self) -> bool:
        """检查刷新按钮是否禁用"""
        return not self.is_enabled_by_testid(self.BTN_REFRESH)

    # ========== 状态筛选 ==========

    def filter_by_status(self, status: str) -> None:
        """
        按状态筛选任务

        Args:
            status: 状态类型（all/running/pending/completed/failed/cancelled）
        """
        status_map = {
            "all": self.FILTER_STATUS_ALL,
            "running": self.FILTER_STATUS_RUNNING,
            "pending": self.FILTER_STATUS_PENDING,
            "completed": self.FILTER_STATUS_COMPLETED,
            "failed": self.FILTER_STATUS_FAILED,
            "cancelled": self.FILTER_STATUS_CANCELLED,
        }
        testid = status_map.get(status, self.FILTER_STATUS_ALL)
        self.click_by_testid(testid)

    def is_status_filter_active(self, status: str) -> bool:
        """检查状态筛选按钮是否激活（primary样式）"""
        status_map = {
            "all": self.FILTER_STATUS_ALL,
            "running": self.FILTER_STATUS_RUNNING,
            "pending": self.FILTER_STATUS_PENDING,
            "completed": self.FILTER_STATUS_COMPLETED,
            "failed": self.FILTER_STATUS_FAILED,
            "cancelled": self.FILTER_STATUS_CANCELLED,
        }
        testid = status_map.get(status, self.FILTER_STATUS_ALL)
        locator = self.get_by_testid(testid)
        # 检查是否有btn-primary类
        return locator.locator(
            ".btn-primary"
        ).count() > 0 or "btn-primary" in locator.get_attribute("class")

    # ========== 类型筛选 ==========

    def filter_by_type(self, task_type: str) -> None:
        """
        按类型筛选任务

        Args:
            task_type: 任务类型（all/download/forward/upload/listen_download/listen_forward）
        """
        type_map = {
            "all": self.FILTER_TYPE_ALL,
            "download": self.FILTER_TYPE_DOWNLOAD,
            "forward": self.FILTER_TYPE_FORWARD,
            "upload": self.FILTER_TYPE_UPLOAD,
            "listen_download": self.FILTER_TYPE_LISTEN_DOWNLOAD,
            "listen_forward": self.FILTER_TYPE_LISTEN_FORWARD,
        }
        testid = type_map.get(task_type, self.FILTER_TYPE_ALL)
        self.click_by_testid(testid)

    # ========== 任务列表 ==========

    def get_task_count(self) -> int:
        """获取当前任务列表中的任务数量"""
        tbody = self.get_by_testid(self.TASKS_TABLE_BODY)
        # 注意：由于使用template x-for，实际DOM中没有task-row元素
        # 需要通过tbody内的tr元素计数
        return tbody.locator("tr").count()

    def get_task_row(self, task_id: str) -> Locator:
        """
        获取指定任务的行元素

        Args:
            task_id: 任务ID

        Returns:
            Locator对象
        """
        # 使用动态testid
        return self.get_by_testid(f"{self.TASK_ROW_PREFIX}{task_id}")

    def get_task_status_text(self, task_id: str) -> str:
        """获取指定任务的状态文本"""
        row = self.get_task_row(task_id)
        status_cell = row.locator(f'[data-testid="{self.TASK_STATUS}"]')
        return status_cell.text_content() or ""

    def click_task_action(self, task_id: str, action: str) -> None:
        """
        点击任务行中的操作按钮

        Args:
            task_id: 任务ID
            action: 操作类型（start/cancel/retry/detail/delete）
        """
        action_map = {
            "start": self.BTN_TASK_START,
            "cancel": self.BTN_TASK_CANCEL,
            "retry": self.BTN_TASK_RETRY,
            "detail": self.BTN_TASK_DETAIL,
            "delete": self.BTN_TASK_DELETE,
        }
        testid = action_map.get(action)
        if not testid:
            raise ValueError(f"Unknown action: {action}")

        row = self.get_task_row(task_id)
        row.locator(f'[data-testid="{testid}"]').click()

    def click_task_detail(self, task_id: str) -> None:
        """点击任务详情按钮"""
        self.click_task_action(task_id, "detail")

    # ========== 创建任务弹窗 ==========

    def is_create_modal_visible(self) -> bool:
        """检查创建任务弹窗是否可见"""
        return self.is_visible_by_testid(self.MODAL_CREATE_TASK)

    def wait_for_create_modal(self, timeout: int = 10000) -> None:
        """等待创建任务弹窗出现"""
        self.wait_for_selector(self.MODAL_CREATE_TASK, timeout)

    def close_create_modal(self) -> None:
        """关闭创建任务弹窗"""
        self.click_by_testid(self.BTN_CLOSE_CREATE)

    def select_task_type(self, task_type: str) -> None:
        """
        选择任务类型

        Args:
            task_type: 任务类型（download/forward/upload/listen_download/listen_forward）
        """
        type_map = {
            "download": self.INPUT_TASK_TYPE_DOWNLOAD,
            "forward": self.INPUT_TASK_TYPE_FORWARD,
            "upload": self.INPUT_TASK_TYPE_UPLOAD,
            "listen_download": self.INPUT_TASK_TYPE_LISTEN_DOWNLOAD,
            "listen_forward": self.INPUT_TASK_TYPE_LISTEN_FORWARD,
        }
        testid = type_map.get(task_type)
        if not testid:
            raise ValueError(f"Unknown task type: {task_type}")
        self.click_by_testid(testid)

    def fill_task_name(self, name: str) -> None:
        """填写任务名称"""
        self.fill_by_testid(self.INPUT_TASK_NAME, name)

    def fill_source_chat(self, chat: str) -> None:
        """填写源频道"""
        self.fill_by_testid(self.INPUT_SOURCE_CHAT, chat)

    def click_resolve_source(self) -> None:
        """点击解析源频道按钮"""
        self.click_by_testid(self.BTN_RESOLVE_SOURCE)

    def fill_target_chat(self, chat: str) -> None:
        """填写目标频道"""
        self.fill_by_testid(self.INPUT_TARGET_CHAT, chat)

    def click_resolve_target(self) -> None:
        """点击解析目标频道按钮"""
        self.click_by_testid(self.BTN_RESOLVE_TARGET)

    def select_range_mode(self, mode: str) -> None:
        """
        选择消息范围模式

        Args:
            mode: 范围模式（id_range/date_range/multiple_ids/all/recent）
        """
        mode_map = {
            "id_range": self.INPUT_RANGE_MODE_ID,
            "date_range": self.INPUT_RANGE_MODE_DATE,
            "multiple_ids": self.INPUT_RANGE_MODE_MULTIPLE,
            "all": self.INPUT_RANGE_MODE_ALL,
            "recent": self.INPUT_RANGE_MODE_RECENT,
        }
        testid = mode_map.get(mode)
        if not testid:
            raise ValueError(f"Unknown range mode: {mode}")
        self.click_by_testid(testid)

    def fill_min_id(self, min_id: str) -> None:
        """填写最小ID"""
        self.fill_by_testid(self.INPUT_MIN_ID, min_id)

    def fill_max_id(self, max_id: str) -> None:
        """填写最大ID"""
        self.fill_by_testid(self.INPUT_MAX_ID, max_id)

    def fill_start_date(self, date: str) -> None:
        """填写开始日期"""
        self.fill_by_testid(self.INPUT_START_DATE, date)

    def fill_end_date(self, date: str) -> None:
        """填写结束日期"""
        self.fill_by_testid(self.INPUT_END_DATE, date)

    def fill_raw_items(self, items: str) -> None:
        """填写ID列表"""
        self.fill_by_testid(self.INPUT_RAW_ITEMS, items)

    def fill_recent_count(self, count: str) -> None:
        """填写最近N条数量"""
        self.fill_by_testid(self.INPUT_RECENT_COUNT, count)

    def click_submit_create(self) -> None:
        """点击创建任务提交按钮"""
        self.click_by_testid(self.BTN_SUBMIT_CREATE)

    # ========== 任务详情抽屉 ==========

    def is_detail_drawer_visible(self) -> bool:
        """检查任务详情抽屉是否可见"""
        return self.is_visible_by_testid(self.DRAWER_TASK_DETAIL)

    def wait_for_detail_drawer(self, timeout: int = 10000) -> None:
        """等待任务详情抽屉出现"""
        self.wait_for_selector(self.DRAWER_TASK_DETAIL, timeout)

    def close_detail_drawer(self) -> None:
        """关闭任务详情抽屉"""
        self.click_by_testid(self.BTN_CLOSE_DETAIL)

    def get_detail_task_id(self) -> str:
        """获取详情抽屉中的任务ID"""
        return self.get_text_by_testid(self.DETAIL_TASK_ID)

    def click_copy_task_id(self) -> None:
        """点击复制任务ID按钮"""
        self.click_by_testid(self.BTN_COPY_TASK_ID)

    # ========== 资源保护告警弹窗 ==========

    def is_resource_alert_visible(self) -> bool:
        """检查资源保护告警弹窗是否可见"""
        return self.is_visible_by_testid(self.MODAL_RESOURCE_ALERT)

    # ========== 综合操作 ==========

    def create_download_task(
        self,
        source_chat: str,
        range_mode: str = "id_range",
        min_id: str = None,
        max_id: str = None,
        task_name: str = None,
    ) -> None:
        """
        快捷创建下载任务

        Args:
            source_chat: 源频道
            range_mode: 消息范围模式
            min_id: 最小ID（id_range模式）
            max_id: 最大ID（id_range模式）
            task_name: 任务名称（可选）
        """
        # 打开创建弹窗
        self.click_create_task()
        self.wait_for_create_modal()

        # 选择下载类型
        self.select_task_type("download")

        # 填写任务名称（可选）
        if task_name:
            self.fill_task_name(task_name)

        # 填写源频道
        self.fill_source_chat(source_chat)

        # 选择消息范围模式
        self.select_range_mode(range_mode)

        # 根据模式填写参数
        if range_mode == "id_range":
            if min_id:
                self.fill_min_id(min_id)
            if max_id:
                self.fill_max_id(max_id)

        # 提交创建
        self.click_submit_create()
