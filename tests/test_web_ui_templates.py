# coding=UTF-8
"""Web UI 静态模板逻辑测试。

直接解析 module/web/*.html，验证 Alpine.js 状态驱动逻辑与预期一致，
无需启动浏览器或后端服务。
"""

import re
from pathlib import Path

import pytest


@pytest.fixture
def tasks_html_text() -> str:
    """加载任务页面 HTML 文本。"""
    html_path = Path(__file__).parent.parent / "module" / "web" / "tasks.html"
    assert html_path.exists(), f"tasks.html 不存在: {html_path}"
    return html_path.read_text(encoding="utf-8")


def _get_button_xshow(html_text: str, testid: str) -> str:
    """根据 data-testid 获取按钮的 x-show 属性值。"""
    # 匹配 <button ... data-testid="{testid}" ... x-show="..." ...>
    pattern = re.compile(
        rf'<button\b[^>]*\bdata-testid="{re.escape(testid)}"[^>]*\bx-show="([^"]*)"[^>]*>',
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(html_text)
    if match is None:
        raise AssertionError(f"找不到按钮 {testid} 的 x-show 属性")
    return match.group(1).strip()


class TestTasksPageActions:
    """任务列表操作按钮显隐逻辑测试。"""

    def test_start_button_only_for_pending(self, tasks_html_text: str):
        """启动按钮仅对 pending 状态显示，不应包含 failed。"""
        xshow = _get_button_xshow(tasks_html_text, "btn-task-start")
        assert "task.status === 'pending'" in xshow
        assert "task.status === 'failed'" not in xshow, (
            "失败任务不应显示启动按钮，请使用重试按钮"
        )

    def test_retry_button_for_failed(self, tasks_html_text: str):
        """重试按钮对 failed 状态显示。"""
        xshow = _get_button_xshow(tasks_html_text, "btn-task-retry")
        assert "task.status === 'failed'" in xshow

    def test_delete_button_includes_failed(self, tasks_html_text: str):
        """删除按钮对 failed 状态可用。"""
        xshow = _get_button_xshow(tasks_html_text, "btn-task-delete")
        assert "task.status === 'failed'" in xshow


class TestUploadTaskForm:
    """上传任务表单 UI 测试。"""

    def test_upload_form_has_file_list_container(self, tasks_html_text: str):
        """上传任务类型下应显示文件列表容器（非 textarea）。"""
        # 查找文件列表容器
        pattern = re.compile(
            r'<div\b[^>]*data-testid="file-list-container"[^>]*>',
            re.DOTALL | re.IGNORECASE,
        )
        assert pattern.search(tasks_html_text), (
            "上传任务表单缺少文件列表容器 (data-testid='file-list-container')"
        )

    def test_upload_form_no_textarea(self, tasks_html_text: str):
        """上传任务表单不应使用 textarea 输入文件路径。"""
        # 在上传任务区域内不应有 textarea
        upload_section = re.search(
            r'x-show="createForm\.taskType\s*===\s*[\'"]upload[\'"]"\s*>(.*?)</div>\s*<!--\s*消息范围',
            tasks_html_text,
            re.DOTALL | re.IGNORECASE,
        )
        if upload_section:
            assert "<textarea" not in upload_section.group(1), (
                "上传任务表单不应使用 textarea，应使用文件列表 + 复选框"
            )

    def test_upload_file_list_visible_only_for_upload(self, tasks_html_text: str):
        """文件列表容器仅在上传任务类型下显示。"""
        pattern = re.compile(
            r'<div\s+class="form-group"\s+x-show="createForm\.taskType\s*===\s*[\'"]upload[\'"]"\s*>',
            re.DOTALL | re.IGNORECASE,
        )
        assert pattern.search(tasks_html_text), (
            "文件列表容器应仅在 taskType === 'upload' 时显示"
        )

    def test_upload_form_no_message_range(self, tasks_html_text: str):
        """上传任务不应显示消息范围选择区域。"""
        pattern = re.compile(
            r'x-show="createForm\.taskType\s*!==\s*[\'"]upload[\'"]\s*&&\s*!createForm\.taskType\.startsWith\([\'"]listen_[\'"]\)"',
            re.DOTALL | re.IGNORECASE,
        )
        assert pattern.search(tasks_html_text), "消息范围区域应排除上传任务类型"
