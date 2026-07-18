"""
任务详情页配置信息展示 E2E 测试。

验证任务详情抽屉中能够正确展示各类任务的配置参数。
"""

import os
import tempfile

import pytest
import requests
from playwright.sync_api import Page

from ..pages.tasks_page import TasksPage
from ..fixtures.test_config import (
    E2E_SERVER_URL,
    get_test_source_channel,
    get_test_target_channel,
    get_test_message_id_range,
)
from ..fixtures.task_helpers import cleanup_multiple_tasks


@pytest.fixture
def tasks_page(authenticated_page: Page) -> TasksPage:
    """任务管理页 Page Object fixture（已认证）"""
    return TasksPage(authenticated_page)


@pytest.fixture
def test_upload_file():
    """创建一个临时测试文件用于上传任务"""
    temp_dir = tempfile.gettempdir()
    temp_path = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        dir=temp_dir,
        delete=False,
    )
    temp_path.write("TRMD upload test file")
    temp_path.close()
    yield temp_path.name
    try:
        os.unlink(temp_path.name)
    except OSError:
        pass


class TestTaskDetailConfigDisplay:
    """TD-CFG: 任务详情配置展示"""

    def _create_task_via_api(self, test_token: str, payload: dict) -> str:
        """通过 API 创建任务并返回任务 ID"""
        headers = {
            "Authorization": f"Bearer {test_token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{E2E_SERVER_URL}/api/tasks",
            json=payload,
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 201, f"创建任务失败: {resp.status_code} {resp.text}"
        data = resp.json()
        task_id = data.get("data", {}).get("id")
        assert task_id, f"无法获取任务 ID: {data}"
        return str(task_id)

    def _open_task_detail(
        self, tasks_page: TasksPage, live_server: str, task_id: str
    ) -> None:
        """导航到任务页并打开指定任务详情抽屉"""
        tasks_page.navigate(live_server)
        tasks_page.wait_for_page_loaded()
        tasks_page.click_task_detail(task_id)
        tasks_page.wait_for_detail_drawer()

    def test_download_task_id_range_config(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
    ):
        """
        TD-CFG-001: 下载任务 ID 范围配置展示。

        验证详情页显示源频道、范围模式"ID范围"、最小/最大 ID、类型过滤。
        """
        source_channel = get_test_source_channel()
        if not source_channel:
            pytest.skip("未配置 test_source_channel")

        id_range = get_test_message_id_range()
        if not id_range:
            pytest.skip("未配置 test_message_id_range")

        payload = {
            "task_type": "download",
            "params": {
                "source_identifier": source_channel,
                "range_mode": "id_range",
                "min_id": id_range["min_id"],
                "max_id": id_range["max_id"],
                "filter_types": ["photo", "video"],
                "min_size": 1048576,
                "max_size": 1073741824,
            },
        }
        task_id = self._create_task_via_api(test_token, payload)
        try:
            self._open_task_detail(tasks_page, live_server, task_id)

            assert tasks_page.is_detail_config_visible()
            assert source_channel in tasks_page.get_detail_source_identifier()
            assert "ID范围" in tasks_page.get_detail_range_mode_text()
            range_detail = tasks_page.get_detail_range_detail()
            assert str(id_range["min_id"]) in range_detail
            assert str(id_range["max_id"]) in range_detail
            type_filter = tasks_page.get_detail_type_filter()
            assert "图片" in type_filter
            assert "视频" in type_filter
            size_filter = tasks_page.get_detail_size_filter()
            assert "1.0 MB" in size_filter
            assert "1.0 GB" in size_filter
        finally:
            cleanup_multiple_tasks(test_token, [task_id])

    def test_forward_task_date_range_config(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
    ):
        """
        TD-CFG-002: 转发任务日期范围配置展示。

        验证详情页显示源频道、目标频道、开始/结束日期。
        """
        source_channel = get_test_source_channel()
        target_channel = get_test_target_channel()
        if not source_channel or not target_channel:
            pytest.skip("未配置 test_source_channel 或 test_target_channel")

        payload = {
            "task_type": "forward",
            "params": {
                "source_identifier": source_channel,
                "forward_target": target_channel,
                "range_mode": "date_range",
                "start_date": "2026-07-01",
                "end_date": "2026-07-18",
            },
        }
        task_id = self._create_task_via_api(test_token, payload)
        try:
            self._open_task_detail(tasks_page, live_server, task_id)

            assert tasks_page.is_detail_config_visible()
            assert source_channel in tasks_page.get_detail_source_identifier()
            target_text = tasks_page.get_detail_target_identifier()
            assert target_text and target_text != "-"
            assert "日期范围" in tasks_page.get_detail_range_mode_text()
            range_detail = tasks_page.get_detail_range_detail()
            assert "2026-07-01" in range_detail
            assert "2026-07-18" in range_detail
        finally:
            cleanup_multiple_tasks(test_token, [task_id])

    def test_upload_task_config(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
        test_upload_file,
    ):
        """
        TD-CFG-003: 上传任务配置展示。

        验证详情页显示目标频道、已选文件数量、上传后删除选项。
        """
        target_channel = get_test_target_channel()
        if not target_channel:
            pytest.skip("未配置 test_target_channel")

        payload = {
            "task_type": "upload",
            "params": {
                "chat_id": target_channel,
                "file_paths": [test_upload_file],
                "delete_after_upload": True,
            },
        }
        task_id = self._create_task_via_api(test_token, payload)
        try:
            self._open_task_detail(tasks_page, live_server, task_id)

            assert target_channel in tasks_page.get_detail_target_identifier()
            assert "1" in tasks_page.get_detail_file_count()
            delete_text = tasks_page.get_detail_delete_after_upload()
            assert "是" in delete_text or "启用" in delete_text
        finally:
            cleanup_multiple_tasks(test_token, [task_id])

    def test_multiple_ids_truncation(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
    ):
        """
        TD-CFG-004: 消息 ID 列表截断展示。

        验证 multiple_ids 模式下最多显示 5 个 ID，并提示总数。
        """
        source_channel = get_test_source_channel()
        if not source_channel:
            pytest.skip("未配置 test_source_channel")

        message_ids = [100, 101, 102, 103, 104, 105, 106]
        payload = {
            "task_type": "download",
            "params": {
                "source_identifier": source_channel,
                "range_mode": "multiple_ids",
                "message_list": message_ids,
            },
        }
        task_id = self._create_task_via_api(test_token, payload)
        try:
            self._open_task_detail(tasks_page, live_server, task_id)

            assert "消息列表" in tasks_page.get_detail_range_mode_text()
            range_detail = tasks_page.get_detail_range_detail()
            assert "100" in range_detail
            assert "104" in range_detail
            # 第 6 个 ID 不应直接展示
            assert "105" not in range_detail
            assert "等 7 条" in range_detail
        finally:
            cleanup_multiple_tasks(test_token, [task_id])

    def test_listen_forward_task_config(
        self,
        tasks_page: TasksPage,
        test_token: str,
        live_server: str,
    ):
        """
        TD-CFG-005: 监听转发任务配置展示。

        验证详情页显示源频道、目标频道、监听媒体类型。
        """
        source_channel = get_test_source_channel()
        target_channel = get_test_target_channel()
        if not source_channel or not target_channel:
            pytest.skip("未配置 test_source_channel 或 test_target_channel")

        payload = {
            "task_type": "listen_forward",
            "params": {
                "source_identifier": source_channel,
                "target_identifier": target_channel,
                "media_types": ["photo", "document"],
            },
        }
        task_id = self._create_task_via_api(test_token, payload)
        try:
            self._open_task_detail(tasks_page, live_server, task_id)

            assert tasks_page.is_detail_config_visible()
            assert source_channel in tasks_page.get_detail_source_identifier()
            assert target_channel in tasks_page.get_detail_target_identifier()
            media_types = tasks_page.get_detail_media_types()
            assert "图片" in media_types
            assert "文档" in media_types
        finally:
            cleanup_multiple_tasks(test_token, [task_id])
