# coding=UTF-8
"""任务操作辅助函数。

提供任务创建、启动、等待完成、获取下载文件、清理等辅助功能。
"""

import os
import time
from typing import Optional

import requests

from .test_config import (
    E2E_SERVER_URL,
    get_test_source_channel,
    get_test_download_count,
    get_test_media_types,
    get_test_download_timeout,
    is_cleanup_test_data,
    get_test_message_id_range,
    PROJECT_ROOT,
)


def create_download_task(
    test_token: str,
    source_channel: Optional[str] = None,
    recent_count: Optional[int] = None,
    media_types: Optional[list] = None,
    message_id_range: Optional[dict] = None,
) -> str:
    """
    创建下载任务。

    Args:
        test_token: 认证 Token
        source_channel: 源频道标识符，默认从配置读取
        recent_count: 下载最近 N 条消息（仅当 message_id_range 为空时使用）
        media_types: 媒体类型过滤列表，默认从配置读取
        message_id_range: 消息ID范围 {min_id: int, max_id: int}，默认从配置读取

    Returns:
        任务 ID

    Raises:
        AssertionError: 创建失败时抛出
    """
    source_channel = source_channel or get_test_source_channel()
    media_types = media_types or get_test_media_types()

    # 优先使用消息ID范围（避免 FloodWait）
    if message_id_range is None:
        message_id_range = get_test_message_id_range()

    if not source_channel:
        raise ValueError("未配置 test_source_channel，无法创建下载任务")

    headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json",
    }

    # 构建任务参数：优先使用 id_range 模式
    if message_id_range and "min_id" in message_id_range and "max_id" in message_id_range:
        # id_range 模式（避免 FloodWait）
        payload = {
            "task_type": "download",
            "params": {
                "source_identifier": source_channel,
                "range_mode": "id_range",
                "min_id": message_id_range["min_id"],
                "max_id": message_id_range["max_id"],
                "media_types": media_types,
            },
        }
        print(f"[E2E] 使用 id_range 模式，范围: {message_id_range['min_id']}-{message_id_range['max_id']}")
    else:
        # recent 模式（可能触发 FloodWait）
        recent_count = recent_count or get_test_download_count()
        payload = {
            "task_type": "download",
            "params": {
                "source_identifier": source_channel,
                "range_mode": "recent",
                "recent_count": recent_count,
                "media_types": media_types,
            },
        }
        print(f"[E2E] 使用 recent 模式，数量: {recent_count}")

    resp = requests.post(
        f"{E2E_SERVER_URL}/api/tasks",
        json=payload,
        headers=headers,
        timeout=30,
    )

    assert resp.status_code == 201, f"创建下载任务失败: {resp.status_code} {resp.text}"

    data = resp.json()
    task_id = data.get("data", {}).get("id")
    assert task_id, f"无法获取任务 ID: {data}"

    return str(task_id)


def start_task(test_token: str, task_id: str) -> None:
    """
    启动任务。

    Args:
        test_token: 认证 Token
        task_id: 任务 ID

    Raises:
        AssertionError: 启动失败时抛出
    """
    headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        f"{E2E_SERVER_URL}/api/tasks/{task_id}/start",
        headers=headers,
        timeout=10,
    )

    assert resp.status_code == 200, f"启动任务失败: {resp.status_code} {resp.text}"


def get_task_status(test_token: str, task_id: str) -> str:
    """
    获取任务状态。

    Args:
        test_token: 认证 Token
        task_id: 任务 ID

    Returns:
        任务状态字符串
    """
    headers = {
        "Authorization": f"Bearer {test_token}",
    }

    resp = requests.get(
        f"{E2E_SERVER_URL}/api/tasks/{task_id}",
        headers=headers,
        timeout=10,
    )

    if resp.status_code != 200:
        return "unknown"

    data = resp.json()
    return data.get("data", {}).get("status", "unknown")


def wait_for_task_completion(
    test_token: str,
    task_id: str,
    timeout: Optional[int] = None,
    poll_interval: int = 3,
) -> str:
    """
    等待任务完成。

    Args:
        test_token: 认证 Token
        task_id: 任务 ID
        timeout: 超时时间（秒），默认动态计算
        poll_interval: 轮询间隔（秒）

    Returns:
        最终任务状态

    Raises:
        TimeoutError: 超时时抛出
    """
    # 动态计算超时时间
    if timeout is None:
        from .test_config import calculate_download_timeout
        timeout = calculate_download_timeout()

    start_time = time.time()

    while True:
        status = get_task_status(test_token, task_id)

        if status in ("completed", "failed", "cancelled"):
            return status

        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(
                f"任务 {task_id} 在 {timeout} 秒内未完成，当前状态: {status}"
            )

        time.sleep(poll_interval)


def get_downloaded_files(test_token: str, task_id: str) -> list[dict]:
    """
    获取任务下载的文件列表。

    Args:
        test_token: 认证 Token
        task_id: 任务 ID

    Returns:
        文件信息列表，每项包含 name, path, type, size 等
    """
    headers = {
        "Authorization": f"Bearer {test_token}",
    }

    # 先获取任务详情，确定下载目录
    resp = requests.get(
        f"{E2E_SERVER_URL}/api/tasks/{task_id}",
        headers=headers,
        timeout=10,
    )

    if resp.status_code != 200:
        return []

    # 从配置获取下载目录
    from .test_config import _get_config_value

    save_directory = _get_config_value("save_directory", default="downloads")
    if not os.path.isabs(save_directory):
        save_directory = os.path.join(PROJECT_ROOT, save_directory)

    # 获取文件列表
    resp = requests.get(
        f"{E2E_SERVER_URL}/api/files",
        headers=headers,
        params={"path": save_directory, "recursive": "true"},
        timeout=10,
    )

    if resp.status_code != 200:
        return []

    data = resp.json()
    items = data.get("data", {}).get("items", [])

    # 过滤出文件（排除目录）
    files = [item for item in items if item.get("type") == "file"]

    return files


def get_save_directory() -> str:
    """
    获取下载目录路径。

    Returns:
        下载目录绝对路径
    """
    from .test_config import _get_config_value

    save_directory = _get_config_value("save_directory", default="downloads")
    if not os.path.isabs(save_directory):
        save_directory = os.path.join(PROJECT_ROOT, save_directory)
    return save_directory


def create_multiple_tasks(
    test_token: str,
    task_count: int,
    source_channel: Optional[str] = None,
    recent_count: Optional[int] = None,
    media_types: Optional[list] = None,
) -> list[str]:
    """
    创建多个下载任务（用于分页测试）。

    Args:
        test_token: 认证 Token
        task_count: 任务数量
        source_channel: 源频道标识符，默认从配置读取
        recent_count: 下载最近 N 条消息，默认从配置读取
        media_types: 媒体类型过滤列表，默认从配置读取

    Returns:
        任务 ID 列表
    """
    task_ids = []
    for i in range(task_count):
        try:
            task_id = create_download_task(
                test_token, source_channel, recent_count, media_types
            )
            task_ids.append(task_id)
            print(f"[E2E] 已创建任务 {i + 1}/{task_count}: {task_id}")
        except Exception as e:
            print(f"[E2E] 创建任务 {i + 1}/{task_count} 失败: {e}")
    return task_ids


def start_multiple_tasks(test_token: str, task_ids: list[str]) -> None:
    """
    启动多个任务。

    Args:
        test_token: 认证 Token
        task_ids: 任务 ID 列表
    """
    for i, task_id in enumerate(task_ids):
        try:
            start_task(test_token, task_id)
            print(f"[E2E] 已启动任务 {i + 1}/{len(task_ids)}: {task_id}")
        except Exception as e:
            print(f"[E2E] 启动任务 {i + 1}/{len(task_ids)} 失败: {e}")


def wait_for_multiple_tasks_completion(
    test_token: str,
    task_ids: list[str],
    timeout: Optional[int] = None,
    poll_interval: int = 3,
) -> dict[str, str]:
    """
    等待多个任务完成。

    Args:
        test_token: 认证 Token
        task_ids: 任务 ID 列表
        timeout: 超时时间（秒），默认从配置读取
        poll_interval: 轮询间隔（秒）

    Returns:
        任务状态字典 {task_id: status}
    """
    timeout = timeout or get_test_download_timeout()
    start_time = time.time()
    task_statuses = {}

    while True:
        all_completed = True

        for task_id in task_ids:
            if task_id in task_statuses:
                continue

            status = get_task_status(test_token, task_id)

            if status in ("completed", "failed", "cancelled"):
                task_statuses[task_id] = status
                print(f"[E2E] 任务完成: {task_id}, 状态: {status}")
            else:
                all_completed = False

        if all_completed or len(task_statuses) == len(task_ids):
            break

        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"[E2E] 等待任务完成超时 ({timeout}秒)")
            break

        time.sleep(poll_interval)

    return task_statuses


def cleanup_multiple_tasks(test_token: str, task_ids: list[str]) -> None:
    """
    清理多个测试任务。

    Args:
        test_token: 认证 Token
        task_ids: 任务 ID 列表
    """
    if not is_cleanup_test_data():
        print(f"[E2E] 保留测试数据: {len(task_ids)} 个任务")
        return

    headers = {
        "Authorization": f"Bearer {test_token}",
    }

    deleted_count = 0
    for task_id in task_ids:
        try:
            resp = requests.delete(
                f"{E2E_SERVER_URL}/api/tasks/{task_id}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                deleted_count += 1
        except Exception as e:
            print(f"[E2E] 删除任务失败: {task_id}, 错误: {e}")

    print(f"[E2E] 已清理测试数据: {deleted_count}/{len(task_ids)} 个任务")


def cleanup_test_data(test_token: str, task_id: str, files: list[dict]) -> None:
    """
    清理测试数据。

    Args:
        test_token: 认证 Token
        task_id: 任务 ID
        files: 文件列表
    """
    if not is_cleanup_test_data():
        print(f"[E2E] 保留测试数据: 任务 {task_id}, {len(files)} 个文件")
        return

    headers = {
        "Authorization": f"Bearer {test_token}",
    }

    # 删除任务
    try:
        requests.delete(
            f"{E2E_SERVER_URL}/api/tasks/{task_id}",
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"[E2E] 删除任务失败: {e}")

    # 删除下载的文件
    save_directory = get_save_directory()
    if os.path.exists(save_directory):
        try:
            # 只删除文件，保留目录结构
            for file_info in files:
                file_path = file_info.get("path")
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)

            # 尝试删除空目录
            for root, dirs, filenames in os.walk(save_directory, topdown=False):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        os.rmdir(dir_path)
                    except OSError:
                        pass  # 目录非空，跳过
        except Exception as e:
            print(f"[E2E] 删除文件失败: {e}")

    print(f"[E2E] 已清理测试数据: 任务 {task_id}, {len(files)} 个文件")


def cleanup_residual_tasks(test_token: str) -> int:
    """
    清理残留的 running/queued 任务，释放并发名额。

    测试环境可能因上次测试异常退出而残留 running 状态的任务，
    这些任务会占用 max_concurrent_tasks 名额导致新任务一直排队。

    Args:
        test_token: 认证 Token

    Returns:
        清理的任务数量
    """
    headers = {
        "Authorization": f"Bearer {test_token}",
    }

    # 获取所有任务
    try:
        resp = requests.get(
            f"{E2E_SERVER_URL}/api/tasks",
            headers=headers,
            params={"limit": 100},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[E2E] 获取任务列表失败: {resp.status_code}")
            return 0
    except Exception as e:
        print(f"[E2E] 获取任务列表异常: {e}")
        return 0

    tasks = resp.json().get("data", {}).get("items", [])
    cleaned = 0

    for task in tasks:
        task_id = task.get("id")
        status = task.get("status")
        if status in ("running", "queued") and task_id:
            # 先尝试取消，再删除
            try:
                requests.post(
                    f"{E2E_SERVER_URL}/api/tasks/{task_id}/cancel",
                    headers=headers,
                    timeout=10,
                )
            except Exception:
                pass
            try:
                resp_del = requests.delete(
                    f"{E2E_SERVER_URL}/api/tasks/{task_id}",
                    headers=headers,
                    timeout=10,
                )
                if resp_del.status_code == 200:
                    cleaned += 1
            except Exception as e:
                print(f"[E2E] 清理残留任务失败: {task_id}, 错误: {e}")

    if cleaned > 0:
        print(f"[E2E] 已清理 {cleaned} 个残留 running/queued 任务")

    return cleaned
