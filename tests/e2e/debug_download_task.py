# coding=UTF-8
"""调试下载任务的独立脚本"""
import requests
import time
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from tests.e2e.fixtures.test_config import (
    E2E_SERVER_URL,
    get_test_source_channel,
    get_test_download_count,
    get_test_media_types,
)


def get_e2e_token():
    """获取E2E测试Token"""
    resp = requests.post(f"{E2E_SERVER_URL}/api/auth/e2e_token", timeout=10)
    if resp.status_code == 200:
        return resp.json().get("data", {}).get("token", "")
    raise Exception(f"获取Token失败: {resp.status_code} {resp.text}")


def cleanup_all_tasks(token):
    """清理所有任务"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{E2E_SERVER_URL}/api/tasks", headers=headers, params={"limit": 100}, timeout=10)
    if resp.status_code != 200:
        print(f"获取任务列表失败: {resp.status_code}")
        return 0

    tasks = resp.json().get("data", {}).get("items", [])
    print(f"当前任务数: {len(tasks)}")

    cleaned = 0
    for task in tasks:
        task_id = task.get("id")
        status = task.get("status")
        if status in ("running", "queued") and task_id:
            # 先取消
            try:
                requests.post(f"{E2E_SERVER_URL}/api/tasks/{task_id}/cancel", headers=headers, timeout=10)
            except Exception:
                pass
        # 删除
        try:
            resp_del = requests.delete(f"{E2E_SERVER_URL}/api/tasks/{task_id}", headers=headers, timeout=10)
            if resp_del.status_code == 200:
                cleaned += 1
        except Exception as e:
            print(f"删除任务失败: {task_id}, 错误: {e}")

    print(f"已清理 {cleaned} 个任务")
    return cleaned


def create_download_task_debug(token):
    """创建下载任务并调试"""
    source_channel = get_test_source_channel()
    recent_count = get_test_download_count()
    media_types = get_test_media_types()

    print(f"\n=== 下载任务参数 ===")
    print(f"源频道: {source_channel}")
    print(f"最近N条: {recent_count}")
    print(f"媒体类型: {media_types}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "task_type": "download",
        "params": {
            "source_identifier": source_channel,
            "range_mode": "recent",
            "recent_count": recent_count,
            "media_types": media_types,
        },
    }

    print(f"\n=== 请求体 ===")
    import json
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    resp = requests.post(f"{E2E_SERVER_URL}/api/tasks", json=payload, headers=headers, timeout=30)
    print(f"\n=== 创建响应 ===")
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.text}")

    if resp.status_code not in (200, 201):
        raise Exception(f"创建任务失败: {resp.status_code}")

    task_id = resp.json().get("data", {}).get("id")
    print(f"任务ID: {task_id}")
    return task_id


def get_task_details(token, task_id):
    """获取任务详情"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{E2E_SERVER_URL}/api/tasks/{task_id}", headers=headers, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    return {}


def test_different_task_configs(token):
    """测试不同的任务配置"""
    source_channel = get_test_source_channel()
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n{'='*60}")
    print("测试不同任务配置")
    print(f"{'='*60}")

    # 测试1: all 模式，不设置 media_types
    print(f"\n=== 测试1: all 模式 ===")
    payload1 = {
        "task_type": "download",
        "params": {
            "source_identifier": source_channel,
            "range_mode": "all",
        },
    }
    resp1 = requests.post(f"{E2E_SERVER_URL}/api/tasks", json=payload1, headers=headers, timeout=30)
    print(f"创建响应: {resp1.status_code}")
    if resp1.status_code in (200, 201):
        task1_id = resp1.json().get("data", {}).get("id")
        print(f"任务ID: {task1_id}")
        # 启动并监控
        status1, task1 = monitor_task(token, task1_id, timeout=30)
        print(f"结果: {status1}")
        # 删除
        requests.delete(f"{E2E_SERVER_URL}/api/tasks/{task1_id}", headers=headers, timeout=10)
    else:
        print(f"创建失败: {resp1.text}")

    # 测试2: recent 模式，不设置 media_types
    print(f"\n=== 测试2: recent 模式（无media_types）===")
    payload2 = {
        "task_type": "download",
        "params": {
            "source_identifier": source_channel,
            "range_mode": "recent",
            "recent_count": 5,
        },
    }
    resp2 = requests.post(f"{E2E_SERVER_URL}/api/tasks", json=payload2, headers=headers, timeout=30)
    print(f"创建响应: {resp2.status_code}")
    if resp2.status_code in (200, 201):
        task2_id = resp2.json().get("data", {}).get("id")
        print(f"任务ID: {task2_id}")
        status2, task2 = monitor_task(token, task2_id, timeout=30)
        print(f"结果: {status2}")
        requests.delete(f"{E2E_SERVER_URL}/api/tasks/{task2_id}", headers=headers, timeout=10)
    else:
        print(f"创建失败: {resp2.text}")

    # 测试3: recent 模式，设置 media_types
    print(f"\n=== 测试3: recent 模式（有media_types）===")
    payload3 = {
        "task_type": "download",
        "params": {
            "source_identifier": source_channel,
            "range_mode": "recent",
            "recent_count": 5,
            "media_types": ["photo"],
        },
    }
    resp3 = requests.post(f"{E2E_SERVER_URL}/api/tasks", json=payload3, headers=headers, timeout=30)
    print(f"创建响应: {resp3.status_code}")
    if resp3.status_code in (200, 201):
        task3_id = resp3.json().get("data", {}).get("id")
        print(f"任务ID: {task3_id}")
        status3, task3 = monitor_task(token, task3_id, timeout=30)
        print(f"结果: {status3}")
        requests.delete(f"{E2E_SERVER_URL}/api/tasks/{task3_id}", headers=headers, timeout=10)
    else:
        print(f"创建失败: {resp3.text}")


def test_channel_access(token):
    """测试频道访问"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    source_channel = get_test_source_channel()
    print(f"\n=== 测试频道访问 ===")
    print(f"源频道: {source_channel}")

    # 尝试直接调用 API 解析频道
    headers = {"Authorization": f"Bearer {token}"}

    # 创建一个 all 模式的任务来测试频道是否可访问
    payload = {
        "task_type": "download",
        "params": {
            "source_identifier": source_channel,
            "range_mode": "all",
        },
    }

    resp = requests.post(f"{E2E_SERVER_URL}/api/tasks", json=payload, headers=headers, timeout=30)
    if resp.status_code in (200, 201):
        task_id = resp.json().get("data", {}).get("id")
        print(f"创建测试任务成功: {task_id}")

        # 立即删除
        requests.delete(f"{E2E_SERVER_URL}/api/tasks/{task_id}", headers=headers, timeout=10)
        print(f"已删除测试任务")
        return True
    else:
        print(f"创建测试任务失败: {resp.status_code} {resp.text}")
        return False


def monitor_task(token, task_id, timeout=60):
    """监控任务执行"""
    headers = {"Authorization": f"Bearer {token}"}

    # 启动任务
    print(f"\n=== 启动任务 ===")
    resp = requests.post(f"{E2E_SERVER_URL}/api/tasks/{task_id}/start", headers=headers, timeout=10)
    print(f"启动响应: {resp.status_code}")

    start_time = time.time()
    while time.time() - start_time < timeout:
        task = get_task_details(token, task_id)
        status = task.get("status", "unknown")
        progress = task.get("progress", 0)
        message = task.get("message", "")
        total_count = task.get("total_count", 0)
        success_count = task.get("success_count", 0)

        print(f"状态: {status}, 进度: {progress}%, 成功: {success_count}/{total_count}, 消息: {message}")

        if status in ("completed", "failed", "cancelled"):
            return status, task

        time.sleep(3)

    return "timeout", {}


def main():
    print("=" * 60)
    print("下载任务调试脚本")
    print("=" * 60)

    # 1. 检查服务是否运行
    try:
        resp = requests.get(f"{E2E_SERVER_URL}/api/auth/e2e_token", timeout=5)
        print(f"服务状态: 运行中 ({E2E_SERVER_URL})")
    except Exception as e:
        print(f"服务未运行: {e}")
        print("请先启动服务: .venv\\Scripts\\python.exe main.py --port 8000")
        return

    # 2. 获取Token
    token = get_e2e_token()
    print(f"Token: {token[:20]}...")

    # 3. 清理历史任务
    print(f"\n=== 清理历史任务 ===")
    cleanup_all_tasks(token)

    # 4. 等待服务状态稳定
    print("\n等待 3 秒...")
    time.sleep(3)

    # 5. 测试不同的任务配置
    test_different_task_configs(token)

    # 6. 创建下载任务（原流程）
    print(f"\n{'='*60}")
    print("原流程：创建下载任务")
    print(f"{'='*60}")
    task_id = create_download_task_debug(token)

    # 7. 监控任务执行
    print(f"\n=== 监控任务执行 ===")
    final_status, task = monitor_task(token, task_id)

    print(f"\n=== 最终结果 ===")
    print(f"状态: {final_status}")
    print(f"详情: {task}")

    # 7. 如果失败，查看服务日志
    if final_status == "failed":
        print(f"\n=== 建议检查 ===")
        print("1. 查看 tests/reports/server_output.log 获取详细错误")
        print("2. 确认频道 @miaotuya 存在且有图片")
        print("3. 确认 Telegram 客户端已加入该频道")


if __name__ == "__main__":
    main()