"""
E2E测试全局Fixture

提供服务启动、认证、浏览器配置等全局测试基础设施。
"""

import os
import subprocess
import time
import pytest
import requests
from playwright.sync_api import Page, BrowserContext

from .fixtures.test_config import (
    PROJECT_ROOT,
    E2E_SERVER_URL,
    SERVER_START_TIMEOUT,
    NAVIGATION_TIMEOUT,
    get_test_token,
)


@pytest.fixture(scope="session")
def live_server():
    """
    启动完整TRMD服务（FastAPI + Telegram Client）

    使用子进程启动main.py，等待服务就绪后返回base_url。
    """
    # 准备测试环境变量
    test_env = os.environ.copy()
    test_env["TRMD_E2E_TEST"] = "1"
    test_env["PYTHONUNBUFFERED"] = "1"

    # 启动服务进程
    process = subprocess.Popen(
        ["python", "main.py"],
        cwd=PROJECT_ROOT,
        env=test_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 等待服务就绪
    base_url = E2E_SERVER_URL
    health_url = f"{base_url}/api/monitor/stats"

    started = False
    for _ in range(SERVER_START_TIMEOUT):
        try:
            resp = requests.get(health_url, timeout=1)
            if resp.status_code == 200:
                started = True
                break
        except requests.exceptions.RequestException:
            time.sleep(1)

    if not started:
        process.terminate()
        process.wait()
        pytest.fail(f"服务启动超时（{SERVER_START_TIMEOUT}秒）")

    yield base_url

    # 清理：终止进程
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture(scope="session")
def test_token(live_server):
    """
    获取测试用的认证Token

    从环境变量TRMD_TEST_TOKEN读取。
    """
    return get_test_token()


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
def setup_trace(browser_context: BrowserContext, request):
    """
    自动启动Playwright trace

    测试失败时保存trace到reports/traces/目录。
    """
    trace_name = request.node.name
    trace_path = PROJECT_ROOT / "tests" / "reports" / "traces" / f"{trace_name}.zip"

    # 确保目录存在
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    browser_context.tracing.start(screenshots=True, snapshots=True)

    yield

    # 仅在测试失败时保存trace
    if request.node.session.testsfailed > 0:
        browser_context.tracing.stop(path=str(trace_path))
    else:
        browser_context.tracing.stop()


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """
    Playwright浏览器启动参数

    配置headless模式、慢动作等。
    """
    args = {
        "headless": True,  # 默认无头模式
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
