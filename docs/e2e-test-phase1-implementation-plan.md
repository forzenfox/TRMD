# E2E测试 Phase 1 实施计划：基础设施搭建 + 登录流程

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立E2E测试基础设施，验证Playwright技术可行性，完成登录流程的E2E测试覆盖。

**Architecture:** 使用pytest-playwright作为测试框架，采用Page Object Model封装页面交互，通过子进程启动完整TRMD服务进行真实服务测试。

**Tech Stack:** Python 3.12, pytest, pytest-playwright, Playwright (Python), subprocess

---

## 文件结构

### 新建文件

```
tests/
├── e2e/
│   ├── __init__.py                    # E2E模块初始化
│   ├── conftest.py                    # E2E全局fixture
│   ├── pages/
│   │   ├── __init__.py                # Page Object模块初始化
│   │   ├── base_page.py               # 基础页面类
│   │   └── login_page.py              # 登录页Page Object
│   └── web/
│   │   ├── __init__.py                # Web测试模块初始化
│   │   └ test_login.py                # 登录流程测试
│   └ fixtures/
│   │   ├── __init__.py                # 测试数据模块初始化
│   │   └ test_config.py               # 测试配置
└── reports/
    ├── .gitkeep                       # 保持reports目录
```

### 修改文件

```
pyproject.toml                         # 新增E2E测试依赖
module/web/login.html                  # 添加data-testid属性
```

---

## Task 1: 环境准备与依赖配置

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 在pyproject.toml中添加E2E测试依赖**

在 `[project.optional-dependencies]` 部分添加e2e组：

```toml
[project.optional-dependencies]
e2e = [
    "pytest-playwright>=0.4.0",
    "playwright>=1.40.0",
]
```

- [ ] **Step 2: 创建reports目录并添加.gitkeep**

运行命令创建目录：

```powershell
mkdir tests\reports -Force; echo "" > tests\reports\.gitkeep
```

- [ ] **Step 3: 安装E2E依赖**

激活虚拟环境后运行：

```powershell
pip install -e ".[e2e]"
playwright install chromium
```

Expected: 成功安装pytest-playwright和playwright，下载Chromium浏览器

- [ ] **Step 4: 验证Playwright安装**

运行：

```powershell
python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

Expected: 输出 `OK`

- [ ] **Step 5: 提交环境配置**

```powershell
git add pyproject.toml tests/reports/.gitkeep
git commit -m "build(e2e): add E2E test dependencies and reports directory"
```

---

## Task 2: 创建E2E测试目录结构

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/pages/__init__.py`
- Create: `tests/e2e/web/__init__.py`
- Create: `tests/e2e/fixtures/__init__.py`

- [ ] **Step 1: 创建tests/e2e/__init__.py**

```python
"""
E2E测试模块

基于Playwright的端到端浏览器自动化测试，覆盖Web UI核心交互流程。
"""
```

- [ ] **Step 2: 创建tests/e2e/pages/__init__.py**

```python
"""
Page Object模块

封装页面交互逻辑，提供稳定的data-testid选择器接口。
"""
from .base_page import BasePage
from .login_page import LoginPage

__all__ = ["BasePage", "LoginPage"]
```

- [ ] **Step 3: 创建tests/e2e/web/__init__.py**

```python
"""
Web UI E2E测试模块

覆盖登录、Dashboard、任务管理、文件管理等核心页面交互。
"""
```

- [ ] **Step 4: 创建tests/e2e/fixtures/__init__.py**

```python
"""
E2E测试数据模块

提供测试凭证、测试频道配置等测试数据。
"""
```

- [ ] **Step 5: 提交目录结构**

```powershell
git add tests/e2e/
git commit -m "test(e2e): create E2E test directory structure"
```

---

## Task 3: 编写测试配置文件

**Files:**
- Create: `tests/e2e/fixtures/test_config.py`

- [ ] **Step 1: 创建测试配置文件**

```python
"""
E2E测试配置

定义测试凭证、测试频道、超时配置等。
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 服务配置
E2E_SERVER_HOST = "localhost"
E2E_SERVER_PORT = 8800
E2E_SERVER_URL = f"http://{E2E_SERVER_HOST}:{E2E_SERVER_PORT}"

# 超时配置（毫秒）
DEFAULT_TIMEOUT = 10000
NAVIGATION_TIMEOUT = 15000
API_RESPONSE_TIMEOUT = 15000
SERVER_START_TIMEOUT = 30  # 秒

# 测试凭证（从环境变量读取）
def get_test_token() -> str:
    """获取测试Token"""
    token = os.environ.get("TRMD_TEST_TOKEN")
    if not token:
        raise ValueError("请设置环境变量 TRMD_TEST_TOKEN")
    return token

def get_test_api_id() -> str:
    """获取Telegram API ID"""
    api_id = os.environ.get("TG_API_ID")
    if not api_id:
        raise ValueError("请设置环境变量 TG_API_ID")
    return api_id

def get_test_api_hash() -> str:
    """获取Telegram API Hash"""
    api_hash = os.environ.get("TG_API_HASH")
    if not api_hash:
        raise ValueError("请设置环境变量 TG_API_HASH")
    return api_hash

# 测试频道配置
TEST_DOWNLOAD_SOURCE = os.environ.get("E2E_TEST_SOURCE_CHANNEL", "")
TEST_FORWARD_TARGET = os.environ.get("E2E_TEST_TARGET_CHANNEL", "")
```

- [ ] **Step 2: 提交测试配置**

```powershell
git add tests/e2e/fixtures/test_config.py
git commit -m "test(e2e): add E2E test configuration module"
```

---

## Task 4: 编写E2E全局Fixture

**Files:**
- Create: `tests/e2e/conftest.py`

- [ ] **Step 1: 创建conftest.py - 导入和常量**

```python
"""
E2E测试全局Fixture

提供服务启动、认证、浏览器配置等全局测试基础设施。
"""
import os
import subprocess
import time
import pytest
import requests
from pathlib import Path
from playwright.sync_api import Page, BrowserContext, Playwright

from .fixtures.test_config import (
    PROJECT_ROOT,
    E2E_SERVER_URL,
    E2E_SERVER_PORT,
    SERVER_START_TIMEOUT,
    get_test_token,
)
```

- [ ] **Step 2: 创建live_server fixture**

```python
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
```

- [ ] **Step 3: 创建test_token fixture**

```python
@pytest.fixture(scope="session")
def test_token(live_server):
    """
    获取测试用的认证Token
    
    从环境变量TRMD_TEST_TOKEN读取。
    """
    return get_test_token()
```

- [ ] **Step 4: 创建authenticated_page fixture**

```python
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
```

- [ ] **Step 5: 创建trace fixture**

```python
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
```

- [ ] **Step 6: 添加Playwright配置fixture**

```python
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
```

- [ ] **Step 7: 提交conftest.py**

```powershell
git add tests/e2e/conftest.py
git commit -m "test(e2e): add E2E global fixtures (live_server, authenticated_page, trace)"
```

---

## Task 5: 编写BasePage基类

**Files:**
- Create: `tests/e2e/pages/base_page.py`

- [ ] **Step 1: 创建BasePage类定义**

```python
"""
BasePage - Page Object基类

提供统一的data-testid选择器接口和通用页面操作方法。
"""
from typing import Optional
from playwright.sync_api import Page, Locator, Response


class BasePage:
    """所有Page Object的基类"""
    
    def __init__(self, page: Page):
        self.page = page
```

- [ ] **Step 2: 添加testid选择器方法**

```python
    def wait_for_selector(self, testid: str, timeout: int = 10000) -> Locator:
        """等待并返回指定testid的元素"""
        return self.page.wait_for_selector(
            f'[data-testid="{testid}"]',
            timeout=timeout
        )
    
    def get_by_testid(self, testid: str) -> Locator:
        """获取指定testid的Locator（不等待）"""
        return self.page.locator(f'[data-testid="{testid}"]')
    
    def click_by_testid(self, testid: str) -> None:
        """点击指定testid的元素"""
        self.page.click(f'[data-testid="{testid}"]')
    
    def fill_by_testid(self, testid: str, value: str) -> None:
        """填充指定testid的输入框"""
        self.page.fill(f'[data-testid="{testid}"]', value)
    
    def get_text_by_testid(self, testid: str) -> str:
        """获取指定testid元素的文本内容"""
        locator = self.page.locator(f'[data-testid="{testid}"]')
        return locator.text_content() or ""
    
    def get_value_by_testid(self, testid: str) -> str:
        """获取指定testid输入框的值"""
        return self.page.input_value(f'[data-testid="{testid}"]')
    
    def is_visible_by_testid(self, testid: str) -> bool:
        """检查指定testid元素是否可见"""
        return self.page.locator(f'[data-testid="{testid}"]').is_visible()
    
    def is_enabled_by_testid(self, testid: str) -> bool:
        """检查指定testid元素是否可交互"""
        return self.page.locator(f'[data-testid="{testid}"]').is_enabled()
    
    def wait_for_hidden_by_testid(self, testid: str, timeout: int = 10000) -> None:
        """等待指定testid元素消失"""
        self.page.locator(f'[data-testid="{testid}"]').wait_for(
            state="hidden", timeout=timeout
        )
```

- [ ] **Step 3: 添加表单操作方法**

```python
    def select_option_by_testid(self, testid: str, value: str) -> None:
        """选择下拉框选项"""
        self.page.select_option(f'[data-testid="{testid}"]', value)
    
    def check_by_testid(self, testid: str) -> None:
        """勾选checkbox"""
        self.page.check(f'[data-testid="{testid}"]')
    
    def uncheck_by_testid(self, testid: str) -> None:
        """取消勾选checkbox"""
        self.page.uncheck(f'[data-testid="{testid}"]')
    
    def is_checked_by_testid(self, testid: str) -> bool:
        """检查checkbox是否被勾选"""
        return self.page.locator(f'[data-testid="{testid}"]').is_checked()
    
    def set_checked_by_testid(self, testid: str, checked: bool) -> None:
        """设置checkbox状态"""
        if checked:
            self.check_by_testid(testid)
        else:
            self.uncheck_by_testid(testid)
```

- [ ] **Step 4: 添加导航和等待方法**

```python
    def navigate(self, base_url: str, path: str) -> None:
        """导航到指定路径"""
        self.page.goto(f"{base_url}{path}")
    
    def wait_for_navigation(self, url_pattern: str, timeout: int = 15000) -> None:
        """等待页面跳转到匹配URL"""
        self.page.wait_for_url(url_pattern, timeout=timeout)
    
    def wait_for_load_state(self, state: str = "networkidle", timeout: int = 30000) -> None:
        """等待页面加载状态"""
        self.page.wait_for_load_state(state, timeout=timeout)
    
    def wait_for_response(
        self, url_pattern: str, timeout: int = 15000
    ) -> Optional[Response]:
        """等待特定API响应"""
        with self.page.expect_response(url_pattern, timeout=timeout) as response_info:
            return response_info.value
```

- [ ] **Step 5: 添加通用辅助方法**

```python
    def take_screenshot(self, path: str) -> None:
        """截图保存到指定路径"""
        self.page.screenshot(path=path)
    
    def wait_for_timeout(self, timeout: int) -> None:
        """等待指定时间（毫秒）"""
        self.page.wait_for_timeout(timeout)
    
    def evaluate(self, expression: str) -> any:
        """在页面中执行JavaScript"""
        return self.page.evaluate(expression)
    
    def get_current_url(self) -> str:
        """获取当前URL"""
        return self.page.url
    
    def reload(self) -> None:
        """刷新页面"""
        self.page.reload()
```

- [ ] **Step 6: 提交BasePage**

```powershell
git add tests/e2e/pages/base_page.py tests/e2e/pages/__init__.py
git commit -m "test(e2e): add BasePage with data-testid selector methods"
```

---

## Task 6: 修改login.html添加data-testid

**Files:**
- Modify: `module/web/login.html`

- [ ] **Step 1: 为Token输入框添加data-testid**

找到Token输入框（约第80-88行），添加 `data-testid="token-input"`：

```html
            <input
              id="token"
              type="password"
              x-model="token"
              placeholder="请输入 Token"
              class="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              data-testid="token-input"
              required
              autofocus
            />
```

- [ ] **Step 2: 为登录按钮添加data-testid**

找到登录按钮（约第116-126行），添加 `data-testid="login-submit-btn"`：

```html
        <button
          type="submit"
          :disabled="loading || !token"
          data-testid="login-submit-btn"
          class="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center"
        >
```

- [ ] **Step 3: 为错误提示添加data-testid**

找到错误提示div（约第106-113行），添加 `data-testid="login-error-msg"`，并为内部span添加 `data-testid="login-error-text"`：

```html
        <div x-show="error" x-transition data-testid="login-error-msg" class="bg-red-900/30 border border-red-700 text-red-300 px-4 py-3 rounded-lg text-sm">
          <div class="flex items-center">
            <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
            </svg>
            <span x-text="error" data-testid="login-error-text"></span>
          </div>
        </div>
```

- [ ] **Step 4: 为显示密码按钮添加data-testid**

找到显示密码按钮（约第89-101行），添加 `data-testid="toggle-password-btn"`：

```html
            <button
              type="button"
              @click="showToken = !showToken"
              data-testid="toggle-password-btn"
              class="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-slate-300"
            >
              <svg x-show="!showToken" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
```

- [ ] **Step 5: 为自动登录提示添加data-testid**

找到自动登录提示div（约第66-72行），添加 `data-testid="auto-login-hint"`：

```html
        <div x-show="loading && token" x-transition data-testid="auto-login-hint" class="mb-4 bg-blue-900/20 border border-blue-700 text-blue-300 px-4 py-3 rounded-lg text-sm flex items-center">
```

- [ ] **Step 6: 提交login.html修改**

```powershell
git add module/web/login.html
git commit -m "feat(web): add data-testid to login.html for E2E testing"
```

---

## Task 7: 编写LoginPage Page Object

**Files:**
- Create: `tests/e2e/pages/login_page.py`

- [ ] **Step 1: 创建LoginPage类定义**

```python
"""
LoginPage - 登录页Page Object

封装登录页面的交互逻辑，提供稳定的data-testid选择器接口。
"""
from playwright.sync_api import Page
from .base_page import BasePage
from ..fixtures.test_config import NAVIGATION_TIMEOUT


class LoginPage(BasePage):
    """登录页Page Object"""
    
    # 页面路径
    URL_PATH = "/web/login.html"
    
    # data-testid常量
    TOKEN_INPUT = "token-input"
    LOGIN_BUTTON = "login-submit-btn"
    ERROR_MESSAGE = "login-error-msg"
    ERROR_TEXT = "login-error-text"
    TOGGLE_PASSWORD = "toggle-password-btn"
    AUTO_LOGIN_HINT = "auto-login-hint"
    
    def __init__(self, page: Page):
        super().__init__(page)
```

- [ ] **Step 2: 添加导航方法**

```python
    def navigate(self, base_url: str, token: str = None) -> None:
        """
        导航到登录页
        
        Args:
            base_url: 服务基础URL
            token: 可选，URL参数Token用于自动登录
        """
        if token:
            url = f"{base_url}{self.URL_PATH}?token={token}"
        else:
            url = f"{base_url}{self.URL_PATH}"
        self.page.goto(url)
    
    def goto_dashboard(self, base_url: str) -> None:
        """直接跳转到Dashboard（用于测试Token过期跳转）"""
        self.page.goto(f"{base_url}/web/index.html")
```

- [ ] **Step 3: 添加表单操作方法**

```python
    def fill_token(self, token: str) -> None:
        """填写Token输入框"""
        self.fill_by_testid(self.TOKEN_INPUT, token)
    
    def clear_token(self) -> None:
        """清空Token输入框"""
        self.fill_by_testid(self.TOKEN_INPUT, "")
    
    def get_token_value(self) -> str:
        """获取Token输入框的值"""
        return self.get_value_by_testid(self.TOKEN_INPUT)
    
    def click_login(self) -> None:
        """点击登录按钮"""
        self.click_by_testid(self.LOGIN_BUTTON)
    
    def login(self, token: str) -> None:
        """
        执行登录操作
        
        Args:
            token: 认证Token
        """
        self.fill_token(token)
        self.click_login()
```

- [ ] **Step 4: 添加状态检查方法**

```python
    def is_login_button_enabled(self) -> bool:
        """检查登录按钮是否可用"""
        return self.is_enabled_by_testid(self.LOGIN_BUTTON)
    
    def is_loading(self) -> bool:
        """检查是否在加载状态"""
        return self.is_visible_by_testid(self.AUTO_LOGIN_HINT)
    
    def has_error(self) -> bool:
        """检查是否有错误提示"""
        return self.is_visible_by_testid(self.ERROR_MESSAGE)
    
    def get_error_message(self) -> str:
        """获取错误提示文本"""
        if self.has_error():
            return self.get_text_by_testid(self.ERROR_TEXT)
        return ""
    
    def toggle_password_visibility(self) -> None:
        """切换密码显示/隐藏"""
        self.click_by_testid(self.TOGGLE_PASSWORD)
    
    def is_token_visible(self) -> bool:
        """检查Token是否可见（非password类型）"""
        input_type = self.page.locator(f'[data-testid="{self.TOKEN_INPUT}"]').get_attribute("type")
        return input_type == "text"
```

- [ ] **Step 5: 添加等待方法**

```python
    def wait_for_dashboard(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待跳转到Dashboard"""
        self.wait_for_navigation("**/index.html", timeout)
    
    def wait_for_login_to_complete(self, timeout: int = NAVIGATION_TIMEOUT) -> None:
        """等待登录完成（跳转到Dashboard或显示错误）"""
        # 等待加载状态消失
        self.wait_for_hidden_by_testid(self.AUTO_LOGIN_HINT, timeout)
    
    def wait_for_error(self, timeout: int = 10000) -> None:
        """等待错误提示出现"""
        self.wait_for_selector(self.ERROR_MESSAGE, timeout)
```

- [ ] **Step 6: 提交LoginPage**

```powershell
git add tests/e2e/pages/login_page.py tests/e2e/pages/__init__.py
git commit -m "test(e2e): add LoginPage Page Object"
```

---

## Task 8: 编写登录流程E2E测试用例

**Files:**
- Create: `tests/e2e/web/test_login.py`

- [ ] **Step 1: 创建test_login.py - 导入和基础结构**

```python
"""
登录流程E2E测试

覆盖登录成功、Token无效、自动登录、Token过期等场景。
"""
import pytest
from playwright.sync_api import Page

from ..pages.login_page import LoginPage
from ..fixtures.test_config import E2E_SERVER_URL


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    """登录页Page Object fixture"""
    return LoginPage(page)
```

- [ ] **Step 2: 编写测试用例L001 - 登录成功**

```python
class TestLoginSuccess:
    """L001: 登录成功场景"""
    
    def test_valid_token_login_success(
        self, login_page: LoginPage, test_token: str, live_server: str
    ):
        """
        L001: 使用有效Token登录成功
        
        验证点：
        1. 填写Token后登录按钮变为可用
        2. 点击登录后跳转到Dashboard
        3. 无错误提示
        """
        # 导航到登录页
        login_page.navigate(live_server)
        
        # 填写Token
        login_page.fill_token(test_token)
        
        # 验证登录按钮可用
        assert login_page.is_login_button_enabled()
        
        # 点击登录
        login_page.click_login()
        
        # 等待跳转到Dashboard
        login_page.wait_for_dashboard()
        
        # 验证当前URL
        assert "index.html" in login_page.get_current_url()
```

- [ ] **Step 3: 编写测试用例L002 - Token无效**

```python
class TestLoginFailure:
    """L002: Token无效场景"""
    
    def test_invalid_token_shows_error(
        self, login_page: LoginPage, live_server: str
    ):
        """
        L002: 使用无效Token显示错误提示
        
        验证点：
        1. 填写无效Token后点击登录
        2. 显示错误提示
        3. 停留在登录页
        """
        # 导航到登录页
        login_page.navigate(live_server)
        
        # 填写无效Token
        login_page.fill_token("invalid_token_12345")
        
        # 点击登录
        login_page.click_login()
        
        # 等待错误提示出现
        login_page.wait_for_error(timeout=15000)
        
        # 验证错误提示可见
        assert login_page.has_error()
        
        # 验证错误消息非空
        error_msg = login_page.get_error_message()
        assert len(error_msg) > 0
        
        # 验证仍停留在登录页
        assert login_page.get_current_url().endswith("login.html")
```

- [ ] **Step 4: 编写测试用例L003 - 自动登录**

```python
class TestAutoLogin:
    """L003: 自动登录场景"""
    
    def test_url_token_auto_login(
        self, login_page: LoginPage, test_token: str, live_server: str
    ):
        """
        L003: URL携带Token参数自动登录
        
        验证点：
        1. URL携带Token时自动填入输入框
        2. 自动触发登录
        3. 跳转到Dashboard
        """
        # 导航到登录页（携带Token参数）
        login_page.navigate(live_server, token=test_token)
        
        # 等待自动登录完成
        login_page.wait_for_dashboard()
        
        # 验证跳转到Dashboard
        assert "index.html" in login_page.get_current_url()
```

- [ ] **Step 5: 编写测试用例L004 - Token过期（标记为跳过）**

```python
class TestTokenExpiry:
    """L004: Token过期场景"""
    
    @pytest.mark.skip(reason="需要手动准备过期Token")
    def test_expired_token_redirect_to_login(
        self, login_page: LoginPage, live_server: str
    ):
        """
        L004: Token过期后跳转回登录页
        
        验证点：
        1. 使用过期Token访问Dashboard
        2. 自动跳转到登录页
        
        注意：此测试需要手动准备一个过期的Token
        """
        # 直接跳转到Dashboard（使用过期Token在cookie中）
        # 此测试需要特殊fixture提供过期Token
        login_page.goto_dashboard(live_server)
        
        # 等待跳转到登录页
        login_page.wait_for_navigation("**/login.html")
        
        # 验证跳转到登录页
        assert "login.html" in login_page.get_current_url()
```

- [ ] **Step 6: 编写测试用例L005 - 显示密码**

```python
class TestPasswordToggle:
    """L005: 显示密码场景"""
    
    def test_toggle_password_visibility(
        self, login_page: LoginPage, live_server: str
    ):
        """
        L005: 点击切换按钮显示/隐藏Token
        
        验证点：
        1. 默认Token为password类型（隐藏）
        2. 点击切换按钮后变为text类型（显示）
        3. 再次点击恢复password类型（隐藏）
        """
        # 导航到登录页
        login_page.navigate(live_server)
        
        # 填写Token（用于测试可见性）
        login_page.fill_token("test_token_value")
        
        # 验证默认隐藏
        assert not login_page.is_token_visible()
        
        # 点击切换按钮
        login_page.toggle_password_visibility()
        
        # 等待一小段时间让Alpine.js响应
        login_page.wait_for_timeout(100)
        
        # 验证Token可见
        assert login_page.is_token_visible()
        
        # 再次点击切换按钮
        login_page.toggle_password_visibility()
        
        # 等待响应
        login_page.wait_for_timeout(100)
        
        # 验证Token再次隐藏
        assert not login_page.is_token_visible()
```

- [ ] **Step 7: 提交测试用例**

```powershell
git add tests/e2e/web/test_login.py tests/e2e/web/__init__.py
git commit -m "test(e2e): add login flow E2E test cases (L001-L005)"
```

---

## Task 9: 运行测试验证

**Files:**
- 无新文件，仅运行测试

- [ ] **Step 1: 设置环境变量**

在运行测试前需要设置测试Token环境变量：

```powershell
$env:TRMD_TEST_TOKEN = "your_test_token_here"
```

注意：实际Token需要从Bot获取（发送/web命令）

- [ ] **Step 2: 运行登录测试**

```powershell
pytest tests/e2e/web/test_login.py -v
```

Expected: 
- L001, L003, L005 通过
- L002 需要服务返回错误（取决于API实现）
- L04 被skip

- [ ] **Step 3: 运行带headed模式调试**

```powershell
pytest tests/e2e/web/test_login.py -v --headed --slowmo=100
```

Expected: 打开浏览器窗口，观察测试执行过程

- [ ] **Step 4: 检查测试报告**

如果测试失败，检查 `tests/reports/traces/` 目录下的trace文件：

```powershell
playwright show-trace tests/reports/traces/test_name.zip
```

---

## 验收标准

Phase 1 完成验收：

- [ ] `tests/e2e/` 目录结构创建完成
- [ ] `pyproject.toml` 包含 `[project.optional-dependencies] e2e` 配置
- [ ] `login.html` 包含以下 `data-testid`：
  - `token-input`
  - `login-submit-btn`
  - `login-error-msg`
  - `toggle-password-btn`
  - `auto-login-hint`
- [ ] `pytest tests/e2e/web/test_login.py -v` 至少3个测试通过（L001, L003, L005）

---

## 后续阶段概览

### Phase 2: Dashboard + 资源监控

- 修改 `module/web/index.html` 添加data-testid
- 编写 `DashboardPage` Page Object
- 编写资源卡片验证测试

### Phase 3: 任务管理核心流程

- 修改 `module/web/tasks.html` 添加data-testid（最多）
- 编写 `TasksPage` Page Object
- 编写任务CRUD测试

### Phase 4: 文件管理 + 上传流程

- 修改 `module/web/files.html` 添加data-testid
- 编写 `FilesPage` Page Object
- 编写文件浏览/选择/上传测试

### Phase 5: Bot E2E

- 创建 `tests/e2e/bot/` 目录
- 编写Bot测试fixture（Pyrogram User Client）
- 编写Bot命令测试

### Phase 6: 配置管理 + 边缘场景

- 修改 `module/web/config.html` 添加data-testid
- 编写 `ConfigPage` Page Object
- 编写边缘场景测试

---

**计划结束**