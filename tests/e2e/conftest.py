"""
E2E测试全局Fixture

提供服务连接、认证、浏览器配置等全局测试基础设施。

支持两种模式：
1. 自动启动服务（auto_start_server=true）：自动启动TRMD服务进程
2. 手动启动服务（auto_start_server=false）：连接已运行的服务（推荐）
"""

import os
import subprocess
import time
import pytest
import requests
from playwright.sync_api import Page

from .fixtures.test_config import (
    PROJECT_ROOT,
    E2E_SERVER_URL,
    E2E_SERVER_PORT,
    SERVER_START_TIMEOUT,
    NAVIGATION_TIMEOUT,
    get_test_token,
    PYTHON_EXECUTABLE,
    _get_config_value,
)
from .fixtures.test_data_setup import (  # noqa: F401
    test_download_data,
    test_pagination_tasks,
)


def _is_server_running(base_url: str) -> bool:
    """检查服务是否已运行"""
    health_url = f"{base_url}/web/login.html"
    try:
        resp = requests.get(health_url, timeout=2)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.fixture(scope="session")
def live_server():
    """
    连接TRMD服务（FastAPI + Telegram Client）

    支持两种模式：
    - auto_start_server=true：自动启动服务进程（可能有问题）
    - auto_start_server=false：连接已手动启动的服务（推荐）

    运行测试前，请手动启动服务：
        .venv\\Scripts\\python.exe main.py --port 8000
    """
    base_url = E2E_SERVER_URL

    # 检查是否需要自动启动服务
    auto_start = _get_config_value(
        "auto_start_server", "E2E_AUTO_START_SERVER", "false"
    ).lower() in ("true", "1", "yes")

    if auto_start:
        # 模式1：自动启动服务（可能有问题，不推荐）
        print("\n[E2E] 自动启动服务模式...")
        test_env = os.environ.copy()
        test_env["TRMD_E2E_TEST"] = "1"
        test_env["PYTHONUNBUFFERED"] = "1"

        # 将服务输出重定向到日志文件，便于调试服务崩溃问题
        server_log_path = PROJECT_ROOT / "tests" / "reports" / "server_output.log"
        server_log_path.parent.mkdir(parents=True, exist_ok=True)
        server_log_file = open(server_log_path, "w", encoding="utf-8")

        process = subprocess.Popen(
            [PYTHON_EXECUTABLE, "main.py", "--port", str(E2E_SERVER_PORT)],
            cwd=PROJECT_ROOT,
            env=test_env,
            stdout=server_log_file,
            stderr=subprocess.STDOUT,
        )

        # 等待服务就绪
        started = False
        start_time = time.time()
        for _ in range(SERVER_START_TIMEOUT):
            if _is_server_running(base_url):
                started = True
                elapsed = time.time() - start_time
                print(f"[E2E] 服务启动成功，耗时 {elapsed:.1f}秒")
                time.sleep(2)
                break
            time.sleep(1)

        if not started:
            elapsed = time.time() - start_time
            process.terminate()
            process.wait()
            pytest.fail(f"服务启动超时（{elapsed:.1f}秒）")

        yield base_url

        # 清理：终止进程并关闭日志文件
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        finally:
            server_log_file.close()
    else:
        # 模式2：连接已运行的服务（推荐）
        print("\n[E2E] 连接已运行服务模式...")
        if not _is_server_running(base_url):
            pytest.fail(
                f"服务未运行！请手动启动服务后再运行E2E测试：\n"
                f"  .venv\\Scripts\\python.exe main.py --port {E2E_SERVER_PORT}\n"
                f"  或设置 auto_start_server: true 自动启动（不推荐）"
            )

        print(f"[E2E] 服务已就绪，连接到 {base_url}")
        yield base_url


@pytest.fixture(scope="session")
def test_token(live_server):
    """
    自动获取测试Token

    优先从配置读取，若未配置则调用E2E专用API自动生成。

    :param live_server: 已启动的服务URL
    :return: 测试Token
    """
    # 1. 首先尝试从配置获取
    token = get_test_token()
    if token:
        print("[E2E] 使用配置文件中的Token")
        return token

    # 2. 自动生成Token（调用E2E专用API）
    e2e_token_url = f"{live_server}/api/auth/e2e_token"
    max_retries = 3
    for retry in range(max_retries):
        try:
            resp = requests.post(e2e_token_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # API响应格式：{"code": 0, "message": "...", "data": {...}}
                if data.get("code") == 0 and data.get("data"):
                    token = data["data"]["token"]
                    ttl_hours = data["data"].get("ttl_hours", 1)
                    print(f"[E2E] 自动生成Token成功，有效期 {ttl_hours} 小时")
                    return token
                else:
                    pytest.fail(f"E2E Token生成失败: {data.get('message', '未知错误')}")
            elif resp.status_code == 403:
                pytest.fail(
                    "E2E Token生成被拒绝，请确保服务启动时设置了 TRMD_E2E_TEST=1"
                )
            else:
                if retry < max_retries - 1:
                    print(
                        f"[E2E] Token生成失败（状态码 {resp.status_code}），重试中..."
                    )
                    time.sleep(1)
                    continue
                pytest.fail(f"E2E Token生成API返回错误: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            if retry < max_retries - 1:
                print("[E2E] Token生成请求失败，重试中...")
                time.sleep(1)
                continue
            pytest.fail(f"E2E Token自动生成请求失败: {e}")

    pytest.fail("无法获取测试Token")


@pytest.fixture(scope="session")
def browser():
    """
    Playwright浏览器实例

    使用chromium，支持headless模式。
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu"],
        )
        yield browser
        browser.close()


@pytest.fixture
def context(browser):
    """
    Playwright浏览器上下文

    每个测试使用独立的浏览器上下文。
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
        locale="zh-CN",
    )
    yield context
    context.close()


@pytest.fixture
def page(context):
    """
    Playwright页面

    每个测试使用独立的页面。
    """
    page = context.new_page()
    page.set_default_timeout(NAVIGATION_TIMEOUT)
    yield page
    page.close()


@pytest.fixture
def authenticated_page(page: Page, test_token: str, live_server: str):
    """
    已认证的Playwright页面

    自动通过URL参数Token完成登录，跳转到Dashboard。
    """
    # 使用URL参数Token自动登录
    login_url = f"{live_server}/web/login.html?token={test_token}"
    page.goto(login_url)

    # 等待跳转到Dashboard
    page.wait_for_url("**/index.html", timeout=NAVIGATION_TIMEOUT)

    return page


@pytest.fixture(autouse=True)
def setup_trace(context, request):
    """
    自动启动Playwright trace

    测试失败时保存trace到reports/traces/目录。
    """
    trace_name = request.node.name
    trace_path = PROJECT_ROOT / "tests" / "reports" / "traces" / f"{trace_name}.zip"

    # 确保目录存在
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    context.tracing.start(screenshots=True, snapshots=True)

    yield

    # 仅在测试失败时保存trace
    if request.node.session.testsfailed > 0:
        context.tracing.stop(path=str(trace_path))
    else:
        context.tracing.stop()


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """
    Playwright浏览器启动参数

    配置headless模式、慢动作等。
    """
    args = {
        "headless": True,
        "args": ["--disable-gpu"],
    }

    # 如果设置了慢动作（用于调试）
    if os.environ.get("E2E_SLOWMO"):
        args["slow_mo"] = int(os.environ.get("E2E_SLOWMO", "100"))

    return args


@pytest.fixture(scope="session")
def browser_context_args():
    """
    Playwright浏览器上下文参数

    配置视口大小、忽略HTTPS错误等。
    """
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "locale": "zh-CN",
    }


@pytest.fixture
def test_task(live_server: str, test_token: str):
    """
    自动创建测试任务（下载类型，pending状态）

    通过API创建任务，测试后自动删除。
    用于测试任务详情、启动、取消等需要已有任务的场景。
    """
    headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json",
    }
    source_channel = _get_config_value(
        "test_source_channel", "E2E_TEST_SOURCE_CHANNEL", ""
    )
    if not source_channel:
        pytest.skip("未配置test_source_channel，跳过需要测试任务的用例")

    create_url = f"{live_server}/api/tasks"
    payload = {
        "task_type": "download",
        "params": {
            "source_identifier": source_channel,
            "range_mode": "id_range",
            "min_id": 1,
            "max_id": 1,
        },
    }

    resp = requests.post(create_url, json=payload, headers=headers, timeout=30)
    # POST /api/tasks 创建任务成功返回 201 Created（RESTful 标准）
    if resp.status_code not in (200, 201):
        pytest.skip(f"自动创建测试任务失败: {resp.status_code} {resp.text}")

    data = resp.json()
    task_id = data.get("data", {}).get("id")
    if not task_id:
        pytest.skip(f"无法获取测试任务ID: {data}")

    yield str(task_id)

    # 清理：删除测试任务
    try:
        delete_url = f"{live_server}/api/tasks/{task_id}"
        requests.delete(delete_url, headers=headers, timeout=5)
    except Exception:
        pass


@pytest.fixture(scope="session")
def expired_token():
    """
    过期Token fixture

    从E2E测试配置获取过期Token，用于测试Token过期场景。
    """
    token = _get_config_value("expired_token", "E2E_EXPIRED_TOKEN", "")
    if not token:
        pytest.skip("未配置expired_token，跳过Token过期测试")
    return token
