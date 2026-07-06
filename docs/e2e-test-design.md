# TRMD E2E测试设计方案

> 版本: 1.0
> 日期: 2026-07-06
> 作者: AI Assistant

## 一、概述

### 1.1 背景

TRMD项目当前测试体系以单元测试和API集成测试为主，缺乏端到端（E2E）浏览器自动化测试。随着Web UI功能日益完善，需要建立E2E测试体系以保障用户交互流程的稳定性。

### 1.2 目标

建立基于Playwright的E2E测试框架，实现：

- **Web UI E2E测试**：覆盖登录、Dashboard、任务管理、文件管理、配置管理等核心页面
- **Bot E2E测试**（可选）：覆盖Telegram Bot命令交互
- **真实Telegram交互验证**：使用真实API凭证验证完整业务链路

### 1.3 覆盖范围评估

| 接口层 | 现有测试覆盖 | E2E可新增覆盖 | 说明 |
|--------|-------------|---------------|------|
| Web UI | 0% | ~90% | 浏览器交互流程 |
| Web API | ~80%（集成测试） | ~30%（通过UI间接触发） | 补充UI→API联调验证 |
| Telegram Bot | ~70%（单元测试） | ~70%（E2E可选） | Bot命令真实交互 |
| 核心业务逻辑 | ~90%（单元测试） | 0% | 不重复覆盖 |

**总体功能覆盖率预估**：E2E新增覆盖 ~40-50%，整体测试覆盖率提升至 ~90%

---

## 二、技术选型

### 2.1 方案选择

采用 **方案B：Playwright Python + 真实服务**

| 组件 | 选型 | 理由 |
|------|------|------|
| 测试框架 | pytest + pytest-playwright | 与现有pytest体系一致 |
| 浏览器驱动 | Playwright (Python) | 原生async支持、自动等待、多浏览器 |
| Bot测试 | Pyrogram Client (user session) | 模拟真实用户向Bot发消息 |
| 页面抽象 | Page Object Model | 降低选择器耦合、提高可维护性 |

### 2.2 不选其他方案的理由

- **方案A（Mock API）**：不验证真实Telegram交互，与"全栈E2E"目标不符
- **方案C（Node.js Playwright）**：引入多语言栈，维护成本高

---

## 三、设计理念与原则

### 3.1 测试金字塔分层

E2E作为补充而非替代现有测试：

```
        ▲ E2E Tests (~40%功能覆盖)
       ╱╲  Web UI交互验证
      ╱  ╲  Bot命令验证(可选)
     ╱────╲
    ╱ API集成╲  (~30%覆盖) - 现有test_web_api.py
   ╱    测试   ╲
  ╱─────────────╲
 ╱   单元测试    ╲ (~30%覆盖) - 现有25+单元测试文件
╱─────────────────╲
```

**原则**：不重复已有测试覆盖范围，E2E专注于用户交互流程和跨模块集成验证。

### 3.2 选择器稳定性优先

| 优先级 | 选择器类型 | 使用场景 |
|--------|------------|----------|
| **P0** | `data-testid` | 所有关键交互元素（必须添加） |
| P1 | `id` 属性 | 已存在的id（如`#token`） |
| P2 | `aria-label` | 可访问性语义元素 |
| P3 | CSS类 + 结构组合 | 非交互元素、容器 |
| ❌ 避免 | 文本内容、Alpine指令、动态索引 | 易变、不可靠 |

**原则**：通过添加`data-testid`确保选择器与UI重构解耦。

### 3.3 真实服务 vs Mock策略

| 测试场景 | 策略 | 理由 |
|----------|------|------|
| 认证流程 | 真实API | Token验证是核心安全功能 |
| 任务列表查询 | 真实API | 验证数据结构一致性 |
| 任务创建表单 | 真实API | 验证前后端参数传递 |
| 任务执行 | 真实TG交互 | 核心业务逻辑，需真实验证 |
| 监听任务 | 真实TG交互 | 实时性验证需要真实连接 |
| 进度轮询 | 真实API | 异步行为验证 |
| Bot命令 | 真实TG Bot | Bot是核心接口之一 |

**原则**：全栈测试，不Mock核心业务链路，仅Mock不可控外部依赖（如网络故障模拟）。

### 3.4 测试环境隔离

| 维度 | 隔离策略 |
|------|----------|
| 数据隔离 | 使用专用测试频道/群组，避免污染生产数据 |
| 状态隔离 | 每个测试清理创建的测试任务 |
| 时间隔离 | 异步操作设置合理超时（默认15s），避免竞态 |
| 凭证隔离 | 测试Token与生产Token分离 |

**原则**：测试不污染生产环境，可重复运行。

### 3.5 失败诊断友好性

每个测试自动截图和trace，失败时保存到reports目录：

```python
@pytest.fixture(autouse=True)
def setup_trace(page):
    page.context.tracing.start(screenshots=True, snapshots=True)
    yield
    # 测试失败时保存trace
```

**原则**：失败时提供完整诊断信息（截图、trace、console log、network log）。

---

## 四、测试目录结构

```
tests/
├── e2e/                          # E2E测试根目录
│   ├── conftest.py               # E2E全局fixture（服务启动、认证、浏览器）
│   ├── pages/                    # Page Object定义
│   │   ├── __init__.py
│   │   ├── base_page.py          # 基础页面类（通用操作）
│   │   ├── login_page.py         # 登录页
│   │   ├── dashboard_page.py     # Dashboard页
│   │   ├── tasks_page.py         # 任务管理页
│   │   ├── files_page.py         # 文件管理页
│   │   └── config_page.py        # 配置页
│   ├── web/                      # Web UI E2E测试
│   │   ├── __init__.py
│   │   ├── test_login.py         # 登录流程
│   │   ├── test_dashboard.py     # Dashboard
│   │   ├── test_tasks.py         # 任务管理
│   │   ├── test_files.py         # 文件管理
│   │   ├── test_config.py        # 配置管理
│   │   └── test_tasks_real.py    # 真实TG任务执行验证
│   ├── bot/                      # Bot E2E测试（可选）
│   │   ├── __init__.py
│   │   ├── conftest.py           # Bot测试专用fixture
│   │   ├── helpers.py            # Bot测试辅助函数
│   │   ├── test_bot_commands.py  # Bot命令测试
│   │   └── test_bot_callbacks.py # 回调查询测试
│   └── fixtures/                 # E2E测试数据
│       ├── __init__.py
│       └── test_channels.py      # 测试频道配置
└── reports/                      # 测试报告输出目录
    ├── traces/                   # Playwright traces
    └── screenshots/              # 失败截图
```

---

## 五、前端选择器改进方案

### 5.1 当前状态

| 属性类型 | 使用情况 | E2E可靠性 |
|----------|----------|-----------|
| `id` 属性 | 仅登录页Token输入框有 `id="token"` | 高 |
| `data-testid` | **完全缺失** | 无法使用 |
| CSS类名 | Tailwind类 + 自定义 `.btn`, `.card`, `.badge` | 中 |
| Alpine.js指令 | 大量使用 `x-show`, `x-model`, `x-for` | 中低 |
| 文本内容 | 按钮文本如"登录"、"新建任务" | 低 |

### 5.2 建议添加的 data-testid

#### login.html

| 元素 | 建议 testid |
|------|-------------|
| Token输入框 | `token-input` (已有id，可双写) |
| 登录按钮 | `login-submit-btn` |
| 错误提示区 | `login-error-msg` |
| 显示密码按钮 | `toggle-password-btn` |
| 自动登录提示 | `auto-login-hint` |

#### index.html (Dashboard)

| 元素 | 建议 testid |
|------|-------------|
| 磁盘状态卡片 | `disk-card` |
| 内存状态卡片 | `memory-card` |
| CPU状态卡片 | `cpu-card` |
| Client状态指示器 | `client-status-indicator` |
| 快捷操作按钮组 | `quick-action-btns` |
| 新建下载按钮 | `quick-download-btn` |
| 新建转发按钮 | `quick-forward-btn` |
| 新建上传按钮 | `quick-upload-btn` |

#### tasks.html

| 元素 | 建议 testid |
|------|-------------|
| 新建任务按钮 | `create-task-btn` |
| 刷新按钮 | `refresh-btn` |
| 状态筛选按钮组 | `status-filter-btns` |
| 单个筛选按钮 | `filter-btn-{status}` (如 `filter-btn-running`) |
| 类型筛选按钮组 | `type-filter-btns` |
| 任务列表容器 | `task-list` |
| 任务表格 | `task-table` |
| 任务行 | `task-row-{task.id}` |
| 任务ID列 | `task-id-{task.id}` |
| 任务类型列 | `task-type-{task.id}` |
| 任务状态徽章 | `task-status-{task.id}` |
| 任务进度条 | `task-progress-{task.id}` |
| 任务操作按钮 | `task-{taskId}-{action}-btn` (如 `task-1-start-btn`) |
| 创建任务弹窗 | `create-task-modal` |
| 任务类型选择组 | `task-type-radio-group` |
| 任务类型单选 | `task-type-radio-{type}` |
| 任务名称输入框 | `task-name-input` |
| 源频道输入框 | `source-chat-input` |
| 解析源频道按钮 | `resolve-source-btn` |
| 源频道解析结果 | `source-chat-result` |
| 目标频道输入框 | `target-chat-input` |
| 解析目标频道按钮 | `resolve-target-btn` |
| 消息范围模式组 | `range-mode-radio-group` |
| 范围模式单选 | `range-mode-radio-{mode}` |
| ID范围最小输入框 | `min-id-input` |
| ID范围最大输入框 | `max-id-input` |
| 日期范围开始输入框 | `start-date-input` |
| 日期范围结束输入框 | `end-date-input` |
| ID列表输入框 | `raw-items-input` |
| 最近N条输入框 | `recent-count-input` |
| 类型过滤组 | `filter-types-group` |
| 最小大小输入框 | `min-size-input` |
| 最大大小输入框 | `max-size-input` |
| 创建表单错误提示 | `create-form-error` |
| 提交创建按钮 | `submit-create-btn` |
| 取消创建按钮 | `cancel-create-btn` |
| 任务详情抽屉 | `task-detail-drawer` |
| 详情关闭按钮 | `close-detail-btn` |
| 详情复制ID按钮 | `copy-id-btn` |
| 资源告警弹窗 | `resource-alert-modal` |
| 确认对话框 | `confirm-dialog` |

#### files.html

| 元素 | 建议 testid |
|------|-------------|
| 刷新按钮 | `refresh-files-btn` |
| 上传选中按钮 | `upload-selected-btn` |
| 面包屑导航 | `breadcrumb-nav` |
| 全选按钮 | `select-all-btn` |
| 清空选择按钮 | `clear-selection-btn` |
| 排序名称按钮 | `sort-name-btn` |
| 排序大小按钮 | `sort-size-btn` |
| 排序日期按钮 | `sort-date-btn` |
| 文件列表 | `file-list` |
| 文件表格 | `file-table` |
| 文件行 | `file-row-{index}` |
| 文件checkbox | `file-checkbox-{index}` |
| 文件名称 | `file-name-{index}` |
| 文件大小 | `file-size-{index}` |
| 文件修改时间 | `file-modified-{index}` |
| 文件预览按钮 | `file-preview-btn-{index}` |
| 选择信息栏 | `selection-info-bar` |
| 上传弹窗 | `upload-modal` |
| 目标频道输入框 | `upload-target-input` |
| 媒体组选项checkbox | `media-group-checkbox` |
| 删除后上传checkbox | `delete-after-upload-checkbox` |
| 提交上传按钮 | `submit-upload-btn` |

#### config.html

| 元素 | 建议 testid |
|------|-------------|
| 配置保存按钮 | `save-config-btn` |
| 配置项容器 | `config-section-{section}` |
| 配置输入框 | `config-input-{key}` |

---

## 六、测试基础设施设计

### 6.1 全局Fixture (tests/e2e/conftest.py)

```python
import pytest
import subprocess
import time
import requests
import os
from pathlib import Path
from playwright.sync_api import Page, BrowserContext

PROJECT_ROOT = Path(__file__).parent.parent.parent  # tests/e2e -> tests -> TRMD

@pytest.fixture(scope="session")
def live_server():
    """启动完整TRMD服务（FastAPI + Telegram Client）"""
    # 使用子进程启动 main.py
    test_env = os.environ.copy()
    test_env["TRMD_E2E_TEST"] = "1"  # 标记为测试模式
    process = subprocess.Popen(
        ["python", "main.py"],
        cwd=PROJECT_ROOT,
        env=test_env
    )
    
    # 等待服务就绪
    base_url = "http://localhost:8800"
    for _ in range(30):  # 最多等待30秒
        try:
            resp = requests.get(f"{base_url}/api/monitor/stats")
            if resp.status_code == 200:
                break
        except:
            time.sleep(1)
    
    yield base_url
    
    # 清理：终止进程
    process.terminate()
    process.wait()

@pytest.fixture(scope="session")
def test_token(live_server):
    """获取测试用的认证Token"""
    # 从环境变量读取预设Token（需提前配置）
    token = os.environ.get("TRMD_TEST_TOKEN")
    if not token:
        raise ValueError("请设置环境变量 TRMD_TEST_TOKEN")
    return token

@pytest.fixture
def authenticated_page(page: Page, test_token: str, live_server: str):
    """已认证的Playwright页面"""
    page.goto(f"{live_server}/web/login.html?token={test_token}")
    page.wait_for_url("**/index.html", timeout=10000)
    return page

@pytest.fixture(autouse=True)
def setup_trace(browser_context: BrowserContext):
    """自动启动trace，失败时保存"""
    browser_context.tracing.start(screenshots=True, snapshots=True)
    yield
    # 在pytest hook中处理失败保存
```

### 6.2 Page Object基类 (tests/e2e/pages/base_page.py)

```python
from playwright.sync_api import Page, Locator

class BasePage:
    """所有Page Object的基类"""
    
    def __init__(self, page: Page):
        self.page = page
    
    def wait_for_selector(self, testid: str, timeout: int = 10000) -> Locator:
        """等待并返回指定testid的元素"""
        return self.page.wait_for_selector(
            f'[data-testid="{testid}"]', 
            timeout=timeout
        )
    
    def click_by_testid(self, testid: str) -> None:
        """点击指定testid的元素"""
        self.page.click(f'[data-testid="{testid}"]')
    
    def fill_by_testid(self, testid: str, value: str) -> None:
        """填充指定testid的输入框"""
        self.page.fill(f'[data-testid="{testid}"]', value)
    
    def get_text_by_testid(self, testid: str) -> str:
        """获取指定testid元素的文本"""
        return self.page.locator(f'[data-testid="{testid}"]').text_content() or ""
    
    def is_visible_by_testid(self, testid: str) -> bool:
        """检查指定testid元素是否可见"""
        return self.page.locator(f'[data-testid="{testid}"]').is_visible()
    
    def wait_for_response(self, url_pattern: str, timeout: int = 15000):
        """等待特定API响应"""
        with self.page.expect_response(url_pattern, timeout=timeout) as response:
            return response.value
    
    def wait_for_navigation(self, url_pattern: str, timeout: int = 10000) -> None:
        """等待页面跳转"""
        self.page.wait_for_url(url_pattern, timeout=timeout)
    
    def get_by_testid(self, testid: str) -> Locator:
        """获取指定testid的Locator"""
        return self.page.locator(f'[data-testid="{testid}"]')
    
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
    
    def wait_for_hidden_by_testid(self, testid: str, timeout: int = 10000) -> None:
        """等待元素消失"""
        self.page.locator(f'[data-testid="{testid}"]').wait_for(state="hidden", timeout=timeout)
```

---

## 七、分阶段实施计划

### Phase 1：基础设施搭建 + 登录流程（预计1周）

**目标**：验证E2E技术可行性，建立基础设施

| 任务 | 具体内容 | 交付物 |
|------|----------|--------|
| 1.1 Playwright环境 | 安装pytest-playwright，配置pyproject.toml | 测试依赖配置 |
| 1.2 测试目录结构 | 创建`tests/e2e/`目录及子目录 | 目录结构 |
| 1.3 conftest.py | 编写全局fixture | tests/e2e/conftest.py |
| 1.4 BasePage | 编写Page Object基类 | tests/e2e/pages/base_page.py |
| 1.5 data-testid添加 | 修改login.html添加testid | module/web/login.html |
| 1.6 LoginPage | 编写登录页Page Object | tests/e2e/pages/login_page.py |
| 1.7 登录测试用例 | 登录成功、Token无效、过期跳转 | tests/e2e/web/test_login.py |

**验收标准**：
- `pytest tests/e2e/web/test_login.py` 全部通过
- 登录流程可重复运行

### Phase 2：Dashboard + 资源监控（预计3天）

**目标**：验证Dashboard页面核心功能

| 任务 | 具体内容 | 交付物 |
|------|----------|--------|
| 2.1 data-testid添加 | 修改index.html添加testid | module/web/index.html |
| 2.2 DashboardPage | Dashboard页Page Object | tests/e2e/pages/dashboard_page.py |
| 2.3 资源卡片验证 | 磁盘/内存/CPU数值显示、Client状态 | tests/e2e/web/test_dashboard.py |
| 2.4 导航验证 | 侧边栏导航跳转、移动端侧边栏 | tests/e2e/web/test_dashboard.py |

**验收标准**：
- Dashboard加载后资源数据正确显示
- 导航跳转功能正常

### Phase 3：任务管理核心流程（预计1.5周）⭐ 重点阶段

**目标**：覆盖任务管理的完整生命周期

| 任务 | 具体内容 | 交付物 |
|------|----------|--------|
| 3.1 data-testid添加 | 修改tasks.html添加testid | module/web/tasks.html |
| 3.2 TasksPage | 任务管理页Page Object | tests/e2e/pages/tasks_page.py |
| 3.3 任务列表展示 | 加载、筛选、分页、排序 | tests/e2e/web/test_tasks.py |
| 3.4 任务创建 | 下载任务创建流程 | tests/e2e/web/test_tasks.py |
| 3.5 任务创建 | 转发任务、上传任务创建 | tests/e2e/web/test_tasks.py |
| 3.6 任务状态操作 | 启动、取消、重试、删除按钮 | tests/e2e/web/test_tasks.py |
| 3.7 任务详情 | 详情抽屉展示、复制ID | tests/e2e/web/test_tasks.py |
| 3.8 真实TG验证 | 创建下载任务并等待完成 | tests/e2e/web/test_tasks_real.py |

**验收标准**：
- 任务CRUD操作全流程通过
- 至少一个真实下载任务执行成功

### Phase 4：文件管理 + 上传流程（预计1周）

**目标**：覆盖文件管理和上传任务创建

| 任务 | 具体内容 | 交付物 |
|------|----------|--------|
| 4.1 data-testid添加 | 修改files.html添加testid | module/web/files.html |
| 4.2 FilesPage | 文件管理页Page Object | tests/e2e/pages/files_page.py |
| 4.3 文件浏览 | 目录导航、面包屑、排序 | tests/e2e/web/test_files.py |
| 4.4 文件选择 | checkbox选择、全选、清空 | tests/e2e/web/test_files.py |
| 4.5 上传任务创建 | 上传弹窗→目标频道→创建 | tests/e2e/web/test_files.py |

**验收标准**：
- 文件浏览功能正常
- 上传任务创建成功

### Phase 5：Bot E2E（技术可行性验证后）

**目标**：覆盖Bot命令交互

| 任务 | 具体内容 | 交付物 |
|------|----------|--------|
| 5.1 Bot测试fixture | Pyrogram User Client连接 | tests/e2e/bot/conftest.py |
| 5.2 Bot测试Helper | 发送命令、等待回复、解析回调 | tests/e2e/bot/helpers.py |
| 5.3 /web命令测试 | 发送/web，验证Token生成 | tests/e2e/bot/test_bot_commands.py |
| 5.4 /batch命令测试 | 发送链接列表，验证任务创建 | tests/e2e/bot/test_bot_commands.py |
| 5.5 内联键盘测试 | 按钮点击、回调处理 | tests/e2e/bot/test_bot_callbacks.py |

**验收标准**：
- Bot核心命令响应正确
- 内联键盘交互正常

### Phase 6：配置管理 + 边缘场景（可选）

| 任务 | 具体内容 | 交付物 |
|------|----------|--------|
| 6.1 config.html testid | 添加testid | module/web/config.html |
| 6.2 ConfigPage | 配置页Page Object | tests/e2e/pages/config_page.py |
| 6.3 配置读写 | 配置项显示、修改、敏感字段脱敏 | tests/e2e/web/test_config.py |
| 6.4 边缘场景 | 网络错误、Token过期、并发操作 | tests/e2e/web/test_edge_cases.py |

---

## 八、测试环境配置

### 8.1 测试凭证

需要在测试环境中配置以下凭证：

| 凭证类型 | 配置方式 | 说明 |
|----------|----------|------|
| Telegram API ID | 环境变量 `TG_API_ID` | 复用生产配置 |
| Telegram API Hash | 环境变量 `TG_API_HASH` | 复用生产配置 |
| Telegram Session | 环境变量 `TG_SESSION_STRING` | User Client会话 |
| Bot Token | 环境变量 `TG_BOT_TOKEN` | Bot凭证 |
| 测试Token | 配置文件 `test_token` | Web认证Token |
| 测试频道 | 配置文件 `test_channels` | 下载/转发目标 |

### 8.2 测试频道准备

需要准备以下测试环境：

1. **测试下载源频道**：包含多媒体消息的公开频道
2. **测试转发目标频道**：Bot有管理权限的频道
3. **测试私聊频道**：用于私聊下载测试（可选）

---

## 九、依赖更新

### 9.1 pyproject.toml 新增依赖

```toml
[project.optional-dependencies]
e2e = [
    "pytest-playwright>=0.4.0",
    "playwright>=1.40.0",
]
```

### 9.2 安装命令

```bash
pip install -e ".[e2e]"
playwright install chromium
```

---

## 十、运行方式

### 10.1 运行全部E2E测试

```bash
pytest tests/e2e/web/ -v --headed --slowmo=100
```

### 10.2 运行特定页面测试

```bash
pytest tests/e2e/web/test_tasks.py -v
```

### 10.3 运行真实TG验证测试

```bash
pytest tests/e2e/web/test_tasks_real.py -v --run-real-tg
```

### 10.4 生成HTML报告

```bash
pytest tests/e2e/ --html=reports/report.html --self-contained-html
```

---

## 十一、风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| Telegram API限流 | 测试执行中断 | 添加请求间隔、使用测试专用账号 |
| 测试频道数据不足 | 无法验证完整流程 | 提前准备测试数据 |
| 服务启动超时 | fixture失败 | 增加等待时间、优化启动检测 |
| 异步轮询超时 | 状态验证失败 | 增加超时时间、添加重试机制 |
| Bot E2E技术障碍 | Phase 5无法实施 | 先验证技术可行性，必要时调整范围 |

---

## 十二、验收标准

### 12.1 Phase 1验收

- [ ] tests/e2e目录结构创建完成
- [ ] conftest.py fixture可正常启动服务
- [ ] login.html data-testid添加完成
- [ ] `pytest tests/e2e/web/test_login.py` 全部通过

### 12.2 Phase 3验收（核心阶段）

- [ ] tasks.html data-testid添加完成
- [ ] 任务列表加载/筛选测试通过
- [ ] 任务创建测试通过（至少下载、转发各1个）
- [ ] 任务状态操作测试通过
- [ ] 至少1个真实下载任务执行成功

### 12.3 最终验收

- [ ] 所有Web UI页面E2E测试通过
- [ ] 测试覆盖率报告生成
- [ ] E2E测试可重复运行
- [ ] 失败时自动保存诊断信息

---

## 附录A：测试用例清单

### A.1 登录测试 (test_login.py)

| 用例ID | 用例名称 | 描述 |
|--------|----------|------|
| L001 | 登录成功 | 输入有效Token，跳转到Dashboard |
| L002 | Token无效 | 输入无效Token，显示错误提示 |
| L003 | 自动登录 | URL带Token参数，自动登录跳转 |
| L004 | Token过期 | Token过期后跳转回登录页 |
| L005 | 显示密码 | 点击切换按钮可显示/隐藏Token |

### A.2 Dashboard测试 (test_dashboard.py)

| 用例ID | 用例名称 | 描述 |
|--------|----------|------|
| D001 | 资源卡片显示 | 磁盘/内存/CPU卡片数值正确显示 |
| D002 | Client状态指示 | Client连接状态正确显示 |
| D003 | 导航跳转 | 点击侧边栏导航跳转正确 |
| D004 | 快捷操作 | 点击快捷按钮跳转到任务创建页 |

### A.3 任务管理测试 (test_tasks.py)

| 用例ID | 用例名称 | 描述 |
|--------|----------|------|
| T001 | 任务列表加载 | 任务列表正确加载并显示 |
| T002 | 状态筛选 | 点击筛选按钮，列表按状态过滤 |
| T003 | 类型筛选 | 点击类型筛选，列表按类型过滤 |
| T004 | 分页导航 | 分页按钮正确切换页面 |
| T005 | 创建下载任务 | 填写表单创建下载任务 |
| T006 | 创建转发任务 | 填写表单创建转发任务 |
| T007 | 创建上传任务 | 填写表单创建上传任务 |
| T008 | 源频道解析 | 点击解析按钮，显示频道信息 |
| T009 | 任务启动 | 点击启动按钮，任务开始执行 |
| T010 | 任务取消 | 点击取消按钮，任务停止 |
| T011 | 任务删除 | 点击删除按钮，任务从列表移除 |
| T012 | 任务详情 | 点击详情按钮，抽屉显示详情 |
| T013 | 复制任务ID | 点击复制按钮，ID复制到剪贴板 |

### A.4 文件管理测试 (test_files.py)

| 用例ID | 用例名称 | 描述 |
|--------|----------|------|
| F001 | 文件列表加载 | 文件列表正确显示 |
| F002 | 目录导航 | 点击目录进入子目录 |
| F003 | 面包屑导航 | 点击面包屑返回上级 |
| F004 | 文件选择 | checkbox选择单个文件 |
| F005 | 全选文件 | 点击全选按钮选择全部 |
| F006 | 文件排序 | 点击排序按钮按条件排序 |
| F007 | 上传任务创建 | 选择文件后创建上传任务 |

---

## 附录B：Page Object示例

### B.1 LoginPage

```python
from playwright.sync_api import Page
from .base_page import BasePage

class LoginPage(BasePage):
    """登录页Page Object"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "/web/login.html"
    
    def navigate(self, base_url: str):
        self.page.goto(f"{base_url}{self.url}")
    
    def fill_token(self, token: str):
        self.fill_by_testid("token-input", token)
    
    def click_login(self):
        self.click_by_testid("login-submit-btn")
    
    def get_error_message(self) -> str:
        if self.is_visible_by_testid("login-error-msg"):
            return self.get_text_by_testid("login-error-msg")
        return ""
    
    def login(self, token: str):
        self.fill_token(token)
        self.click_login()
    
    def wait_for_dashboard(self, timeout: int = 10000):
        self.wait_for_navigation("**/index.html", timeout)
    
    def toggle_password_visibility(self):
        self.click_by_testid("toggle-password-btn")
```

### B.2 TasksPage

```python
from playwright.sync_api import Page, Locator
from .base_page import BasePage

class TasksPage(BasePage):
    """任务管理页Page Object"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "/web/tasks.html"
    
    def navigate(self, base_url: str):
        self.page.goto(f"{base_url}{self.url}")
    
    def click_create_task(self):
        self.click_by_testid("create-task-btn")
        self.wait_for_selector("create-task-modal")
    
    def select_task_type(self, task_type: str):
        self.click_by_testid(f"task-type-radio-{task_type}")
    
    def fill_source_chat(self, source: str):
        self.fill_by_testid("source-chat-input", source)
    
    def click_resolve_source(self):
        self.click_by_testid("resolve-source-btn")
    
    def wait_for_source_result(self, timeout: int = 10000):
        self.wait_for_selector("source-chat-result", timeout)
    
    def fill_target_chat(self, target: str):
        self.fill_by_testid("target-chat-input", target)
    
    def select_range_mode(self, mode: str):
        self.click_by_testid(f"range-mode-radio-{mode}")
    
    def fill_id_range(self, min_id: int, max_id: int):
        self.fill_by_testid("min-id-input", str(min_id))
        self.fill_by_testid("max-id-input", str(max_id))
    
    def click_submit_create(self):
        self.click_by_testid("submit-create-btn")
    
    def wait_for_modal_close(self, timeout: int = 5000):
        self.wait_for_hidden_by_testid("create-task-modal", timeout)
    
    def get_task_row(self, task_id: int) -> Locator:
        return self.get_by_testid(f"task-row-{task_id}")
    
    def click_task_action(self, task_id: int, action: str):
        self.click_by_testid(f"task-{task_id}-{action}-btn")
    
    def get_task_status(self, task_id: int) -> str:
        return self.get_text_by_testid(f"task-status-{task_id}")
    
    def filter_by_status(self, status: str):
        self.click_by_testid(f"filter-btn-{status}")
    
    def get_task_count(self) -> int:
        return self.page.locator('[data-testid^="task-row-"]').count()
    
    def click_task_detail(self, task_id: int):
        self.click_by_testid(f"task-{task_id}-detail-btn")
        self.wait_for_selector("task-detail-drawer")
    
    def close_detail_drawer(self):
        self.click_by_testid("close-detail-btn")
```

---

**文档结束**