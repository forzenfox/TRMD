# ruff: noqa: B101, RUF030
# -*- coding: utf-8 -*-
"""测试断言辅助函数。

提供常用的断言函数，简化测试代码。
"""

from typing import Any, Dict, Optional


def assert_success_response(
    response_data: Dict[str, Any],
    expected_code: int = 0,
    expected_message: str = "success",
) -> None:
    """验证成功响应格式。

    Args:
        response_data: 响应数据字典
        expected_code: 期望的 code 值，默认为 0
        expected_message: 期望的 message 值，默认为 "success"

    Raises:
        AssertionError: 如果响应格式不符合预期
    """
    assert "code" in response_data, "响应缺少 code 字段"
    assert "message" in response_data, "响应缺少 message 字段"
    assert "data" in response_data, "响应缺少 data 字段"
    assert response_data["code"] == expected_code, (
        f"code 值错误：期望 {expected_code}，实际 {response_data['code']}"
    )
    assert response_data["message"] == expected_message, (
        f"message 值错误：期望 {expected_message}，实际 {response_data['message']}"
    )


def assert_error_response(
    response_data: Dict[str, Any],
    expected_code: int,
    expected_message: Optional[str] = None,
) -> None:
    """验证错误响应格式。

    Args:
        response_data: 响应数据字典
        expected_code: 期望的 code 值
        expected_message: 期望的 message 值（可选）

    Raises:
        AssertionError: 如果响应格式不符合预期
    """
    assert "code" in response_data, "响应缺少 code 字段"
    assert "message" in response_data, "响应缺少 message 字段"
    assert response_data["code"] == expected_code, (
        f"code 值错误：期望 {expected_code}，实际 {response_data['code']}"
    )
    if expected_message is not None:
        assert response_data["message"] == expected_message, (
            f"message 值错误：期望 {expected_message}，实际 {response_data['message']}"
        )


def assert_task_status(
    task_data: Dict[str, Any],
    expected_status: str,
    expected_task_type: Optional[str] = None,
    expected_chat_id: Optional[int] = None,
) -> None:
    """验证任务状态。

    Args:
        task_data: 任务数据字典
        expected_status: 期望的状态
        expected_task_type: 期望的任务类型（可选）
        expected_chat_id: 期望的频道 ID（可选）

    Raises:
        AssertionError: 如果任务状态不符合预期
    """
    assert "status" in task_data, "任务数据缺少 status 字段"
    assert task_data["status"] == expected_status, (
        f"任务状态错误：期望 {expected_status}，实际 {task_data['status']}"
    )

    if expected_task_type is not None:
        assert "task_type" in task_data, "任务数据缺少 task_type 字段"
        assert task_data["task_type"] == expected_task_type, (
            f"任务类型错误：期望 {expected_task_type}，实际 {task_data['task_type']}"
        )

    if expected_chat_id is not None:
        assert "chat_id" in task_data, "任务数据缺少 chat_id 字段"
        assert task_data["chat_id"] == expected_chat_id, (
            f"频道 ID 错误：期望 {expected_chat_id}，实际 {task_data['chat_id']}"
        )


def assert_pagination_response(
    response_data: Dict[str, Any],
    expected_total: Optional[int] = None,
    expected_limit: Optional[int] = None,
    expected_offset: Optional[int] = None,
) -> None:
    """验证分页响应。

    Args:
        response_data: 响应数据字典
        expected_total: 期望的总数（可选）
        expected_limit: 期望的 limit（可选）
        expected_offset: 期望的 offset（可选）

    Raises:
        AssertionError: 如果分页响应不符合预期
    """
    assert "data" in response_data, "响应缺少 data 字段"
    data = response_data["data"]
    assert "total" in data, "分页数据缺少 total 字段"
    assert "limit" in data, "分页数据缺少 limit 字段"
    assert "offset" in data, "分页数据缺少 offset 字段"
    assert "items" in data, "分页数据缺少 items 字段"

    if expected_total is not None:
        assert data["total"] == expected_total, (
            f"total 值错误：期望 {expected_total}，实际 {data['total']}"
        )

    if expected_limit is not None:
        assert data["limit"] == expected_limit, (
            f"limit 值错误：期望 {expected_limit}，实际 {data['limit']}"
        )

    if expected_offset is not None:
        assert data["offset"] == expected_offset, (
            f"offset 值错误：期望 {expected_offset}，实际 {data['offset']}"
        )

    assert isinstance(data["items"], list), "items 必须是列表"


def assert_token_response(response_data: Dict[str, Any]) -> None:
    """验证 Token 响应。

    Args:
        response_data: 响应数据字典

    Raises:
        AssertionError: 如果 Token 响应不符合预期
    """
    assert_success_response(response_data)
    data = response_data["data"]
    assert "token" in data, "Token 响应缺少 token 字段"
    assert "expires_at" in data, "Token 响应缺少 expires_at 字段"
    assert "created_at" in data, "Token 响应缺少 created_at 字段"
    assert "usage_count" in data, "Token 响应缺少 usage_count 字段"


def assert_file_info(
    file_info: Dict[str, Any],
    expected_name: Optional[str] = None,
    expected_type: Optional[str] = None,
) -> None:
    """验证文件信息。

    Args:
        file_info: 文件信息字典
        expected_name: 期望的文件名（可选）
        expected_type: 期望的文件类型（可选）

    Raises:
        AssertionError: 如果文件信息不符合预期
    """
    assert "name" in file_info, "文件信息缺少 name 字段"
    assert "path" in file_info, "文件信息缺少 path 字段"
    assert "type" in file_info, "文件信息缺少 type 字段"
    assert "size" in file_info, "文件信息缺少 size 字段"

    if expected_name is not None:
        assert file_info["name"] == expected_name, (
            f"文件名错误：期望 {expected_name}，实际 {file_info['name']}"
        )

    if expected_type is not None:
        assert file_info["type"] == expected_type, (
            f"文件类型错误：期望 {expected_type}，实际 {file_info['type']}"
        )


def assert_config_response(
    response_data: Dict[str, Any], check_sensitive_fields: bool = True
) -> None:
    """验证配置响应。

    Args:
        response_data: 响应数据字典
        check_sensitive_fields: 是否检查敏感字段脱敏

    Raises:
        AssertionError: 如果配置响应不符合预期
    """
    assert_success_response(response_data)
    data = response_data["data"]

    # 检查基本配置字段
    assert "api_id" in data, "配置缺少 api_id 字段"
    assert "api_hash" in data, "配置缺少 api_hash 字段"
    assert "bot_token" in data, "配置缺少 bot_token 字段"
    assert "save_directory" in data, "配置缺少 save_directory 字段"

    # 检查敏感字段脱敏
    if check_sensitive_fields:
        assert data["api_id"] == "***", f"api_id 未脱敏：{data['api_id']}"
        assert data["api_hash"] == "***", f"api_hash 未脱敏：{data['api_hash']}"
        assert data["bot_token"] == "***", f"bot_token 未脱敏：{data['bot_token']}"


def assert_list_response(
    response_data: Dict[str, Any],
    expected_min_items: int = 0,
    expected_max_items: Optional[int] = None,
) -> None:
    """验证列表响应。

    Args:
        response_data: 响应数据字典
        expected_min_items: 期望的最小项目数
        expected_max_items: 期望的最大项目数（可选）

    Raises:
        AssertionError: 如果列表响应不符合预期
    """
    assert_success_response(response_data)
    data = response_data["data"]
    assert isinstance(data, list), "data 必须是列表"

    if expected_min_items > 0:
        assert len(data) >= expected_min_items, (
            f"项目数不足：期望至少 {expected_min_items}，实际 {len(data)}"
        )

    if expected_max_items is not None:
        assert len(data) <= expected_max_items, (
            f"项目数过多：期望至多 {expected_max_items}，实际 {len(data)}"
        )
