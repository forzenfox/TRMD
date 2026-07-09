# coding=UTF-8
"""测试数据准备 fixture。

提供 session 级别的测试数据准备，自动下载真实文件供测试使用。
"""

import pytest

from .test_config import (
    is_prepare_test_data,
    get_test_source_channel,
    get_pagination_task_count,
)
from .task_helpers import (
    create_download_task,
    start_task,
    wait_for_task_completion,
    get_downloaded_files,
    cleanup_test_data,
    create_multiple_tasks,
    start_multiple_tasks,
    cleanup_multiple_tasks,
    cleanup_residual_tasks,
)


@pytest.fixture(scope="session")
def test_download_data(test_token: str):
    """
    Session 级别的测试数据准备。

    自动创建下载任务，等待完成，提供下载的文件信息。
    测试结束后根据配置清理数据。

    Yields:
        dict: 包含 task_id, files, download_dir 的字典
    """
    # 检查是否需要准备测试数据
    if not is_prepare_test_data():
        pytest.skip("未启用 prepare_test_data，跳过需要真实数据的测试")

    # 检查是否配置了源频道
    source_channel = get_test_source_channel()
    if not source_channel:
        pytest.skip("未配置 test_source_channel，跳过需要真实数据的测试")

    print("\n[E2E] 开始准备测试数据...")

    # 清理残留的 running/queued 任务，避免占用并发名额
    cleanup_residual_tasks(test_token)

    # 创建下载任务
    task_id = create_download_task(test_token)
    print(f"[E2E] 已创建下载任务: {task_id}")

    # 启动任务
    start_task(test_token, task_id)
    print(f"[E2E] 已启动任务: {task_id}")

    # 等待任务完成
    try:
        status = wait_for_task_completion(test_token, task_id)
        print(f"[E2E] 任务结束，状态: {status}")
    except TimeoutError as e:
        print(f"[E2E] 任务超时: {e}")
        pytest.skip(f"下载任务超时，跳过需要真实数据的测试: {e}")

    # 任务失败时跳过（可能是频道无消息、网络问题等）
    if status != "completed":
        pytest.skip(f"下载任务未成功完成（状态: {status}），跳过需要真实数据的测试")

    # 获取下载的文件
    files = get_downloaded_files(test_token, task_id)
    print(f"[E2E] 已下载 {len(files)} 个文件")

    # 获取下载目录
    from .task_helpers import get_save_directory

    download_dir = get_save_directory()

    # 提供给测试使用
    yield {
        "task_id": task_id,
        "files": files,
        "download_dir": download_dir,
    }

    # 清理测试数据
    cleanup_test_data(test_token, task_id, files)
    print("[E2E] 测试数据准备完成")


@pytest.fixture(scope="session")
def test_pagination_tasks(test_token: str):
    """
    Session 级别的分页测试数据准备。

    创建多个任务（默认25个），用于测试分页功能。
    分页需要任务数量超过单页显示数量（默认20）。

    Yields:
        list: 任务 ID 列表
    """
    # 检查是否需要准备测试数据
    if not is_prepare_test_data():
        pytest.skip("未启用 prepare_test_data，跳过分页测试")

    # 检查是否配置了源频道
    source_channel = get_test_source_channel()
    if not source_channel:
        pytest.skip("未配置 test_source_channel，跳过分页测试")

    # 获取需要创建的任务数量
    task_count = get_pagination_task_count()
    print(f"\n[E2E] 开始准备分页测试数据，创建 {task_count} 个任务...")

    # 创建多个任务
    task_ids = create_multiple_tasks(test_token, task_count)
    print(f"[E2E] 已创建 {len(task_ids)} 个任务")

    if len(task_ids) < 21:
        pytest.skip(f"任务数量不足（{len(task_ids)} < 21），无法测试分页")

    # 启动所有任务
    start_multiple_tasks(test_token, task_ids)
    print(f"[E2E] 已启动 {len(task_ids)} 个任务")

    # 等待所有任务完成（不等待也可以，任务存在即可测试分页）
    # 这里只等待一小段时间确保任务已创建
    import time

    time.sleep(2)

    # 提供给测试使用
    yield task_ids

    # 清理测试数据
    cleanup_multiple_tasks(test_token, task_ids)
    print("[E2E] 分页测试数据清理完成")
