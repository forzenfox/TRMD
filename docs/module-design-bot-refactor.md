# Bot 端重构模块设计文档

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **模块名称**: Bot 端重构  
> **文档版本**: v1.1  
> **创建日期**: 2026-06-18  
> **状态**: 草稿  
> **关联文档**: `docs/interaction-enhancement-design.md`

---

## 1. 设计目标与职责边界

### 1.1 设计目标

在《交互体验增强设计文档》的总体架构下，对现有 `module/bot.py` 进行重构，将 Bot 端定位为**轻量级操作入口**，复杂任务统一引导至 WebUI 完成。

核心目标：

1. **命令精简**：保留高频简单命令，移除/弱化依赖复杂表单交互的命令入口。
2. **WebUI 引导**：通过 `/web` 命令生成一次性 Token 链接，用户点击即可进入 WebUI，无需二次登录。
3. **状态隔离**：引入 `InteractionManager` 管理 Bot 端多轮交互状态（如 `/batch` 批量收集），避免与业务逻辑耦合。
4. **向后兼容**：所有已有命令的调用语法与行为保持不变，老用户无感知。
5. **单用户模型**：当前版本仅支持 `self.root` 对应的单一用户，所有状态以 `user_id` 为键，但不做多用户隔离。

### 1.2 Bot 与 WebUI 职责边界

| 能力维度 | Bot 端职责 | WebUI 端职责 |
|----------|------------|--------------|
| 单条下载 | `/download <链接>` | 任务创建表单 |
| 范围转发 | `/forward <源> <目标> <起始ID> <结束ID>` | 可视化范围选择 + 预览 |
| 单文件/目录上传 | `/upload` / `/upload_r` | 文件树勾选 + 媒体组配置 |
| 批量操作 | `/batch` 简化收集入口 | 完整批量任务配置、预览、资源告警 |
| 频道监听 | 保留 `/listen_download`、`/listen_forward`、`/listen_info` | 监听规则管理面板 |
| 配置管理 | 引导到 WebUI | 全部配置项可视化编辑 |
| 任务监控 | `/status` 文本概览 | 实时 Dashboard + WebSocket |
| 认证 | `filters.user(self.root)` + `/web` Token | URL Token / Cookie / Header |

### 1.3 与主设计文档的衔接

- Token 认证层由新增的 `module/core/token_manager.py`（或等效模块）提供，Bot 端仅调用 `TokenManager.generate(user_id)` 与 `TokenManager.revoke(user_id)`。
- 任务创建后统一进入 `TaskManager` 的队列调度体系，Bot 端不再自行维护下载/上传并发。
- `/batch` 收集完成后的任务提交，通过 `TaskManager.create_task(...)` 完成，Bot 只负责参数透传。

---

## 2. 命令体系

### 2.1 命令总表

| 命令 | 状态 | 功能说明 | 复杂度 |
|------|------|----------|--------|
| `/start` | 保留 | 欢迎信息，附带 WebUI 引导按钮 | 低 |
| `/help` | 保留 | 帮助信息，展示可用命令 | 低 |
| `/download` | 保留 | 单条/多条链接下载；支持范围下载语法 | 低 |
| `/forward` | 保留 | 单条转发任务：`/forward 源 目标 起始ID 结束ID` | 中 |
| `/upload` | 保留 | 上传本地单个文件或文件夹 | 中 |
| `/upload_r` | 保留 | 递归上传本地文件夹 | 中 |
| `/listen_download` | 保留 | 创建监听下载规则 | 中 |
| `/listen_forward` | 保留 | 创建监听转发规则 | 中 |
| `/listen_info` | 保留 | 查看当前监听规则 | 低 |
| `/status` | 新增 | 查看当前任务队列与运行状态 | 低 |
| `/web` | 新增 | 生成带 Token 的 WebUI 访问链接 | 低 |
| `/web_revoke` | 新增 | 撤销当前用户所有生效 Token | 低 |
| `/batch` | 新增 | 进入简化批量操作模式 | 中 |
| `/setup_repository` | 新增 | 设置仓库频道（配置存储频道） | 中 |
| `/table` | 移除 | 原终端统计表入口，功能迁移至 WebUI | - |
| `/download_chat` | 移除 | 复杂频道过滤表单迁移至 WebUI | - |
| `/exit` | 保留 | 退出软件 | 低 |

### 2.2 保留/新增/移除说明

#### 2.2.1 保留命令

- `/download`、`/forward`、`/upload`、`/upload_r` 保持原有语法与返回值不变，其底层仍通过现有 `get_download_link_from_bot`、`get_forward_link_from_bot`、`get_upload_link_from_bot` 处理。
- `/listen_download`、`/listen_forward`、`/listen_info` 保持监听功能入口，复杂规则配置引导到 WebUI。
- `/start`、`/help` 更新文案，增加 WebUI 引导段落与 `/web` 按钮。
- `/exit` 保持原行为。

#### 2.2.2 新增命令

- `/status`：调用 `TaskManager.list_tasks()` 返回当前运行中/排队中任务概览。
- `/web`：调用 `TokenManager.generate(user_id)` 生成 1 小时有效 Token，拼接 WebUI URL。
- `/web_revoke`：调用 `TokenManager.revoke(user_id)` 使该用户所有 Token 失效。
- `/batch`：启动 `InteractionManager` 的批量收集会话，进入简化批量模式。
- `/setup_repository`：设置仓库频道，验证频道输入格式，解析频道 ID，检查 Bot 管理员权限，保存到配置。

#### 2.2.3 移除命令

- `/table`：统计表属于数据可视化需求，WebUI Dashboard 与任务详情页替代。
- `/download_chat`：日期范围、类型过滤、关键词过滤等复杂交互表单全部迁移至 WebUI。

> **向后兼容策略**：移除命令不再注册到 Bot 菜单；若用户仍发送旧命令，Bot 回复「该功能已迁移到 WebUI，请发送 /web 获取链接」，不触发原逻辑。

---

## 3. `/web` 命令详细设计

### 3.1 触发条件

- 命令：`/web`
- 权限：`filters.user(self.root)`，仅登录用户账户 ID 可触发。
- 依赖：WebUI 服务已启动（由 `main.py` 的 `--web` 或 `--web-only` 参数控制）。

### 3.2 处理流程

```
用户发送 /web
  │
  ▼
Bot 通过 filters.user(self.root) 校验身份
  │
  ▼
调用 TokenManager.generate(user_id=root_id, ttl=3600)
  │
  ▼
读取 WebUI 基础地址（ConfigManager.web_ui.base_url）
  │
  ▼
拼接链接：{base_url}/?token={token}
  │
  ▼
格式化回复文本并发送
```

### 3.3 Token 生成调用

TokenManager 接口约定：

```python
class TokenManager:
    async def generate(self, user_id: int, ttl: int = 3600) -> str:
        """生成临时访问 Token，返回 token 字符串。"""

    async def validate(self, token: str) -> bool:
        """验证 Token 是否有效。"""

    async def revoke(self, user_id: int) -> int:
        """撤销指定用户的所有 Token，返回撤销数量。"""
```

Bot 端调用方式：

```python
async def web(self, client, message):
    user_id = message.from_user.id
    token = await self.token_manager.generate(user_id=user_id, ttl=3600)
    base_url = self.config_manager.get_config('web_ui.base_url')
    url = f'{base_url}/?token={token}'
    expires_at = datetime.now() + timedelta(hours=1)
    await client.send_message(
        chat_id=user_id,
        text=format_web_message(url, expires_at),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🌐 打开 WebUI', url=url)]])
    )
```

### 3.4 回复格式

```text
🌐 WebUI 管理面板

访问链接: http://192.168.1.100:8080/?token=eyJhbGciOi...
有效期: 1 小时（2026-06-18 16:30 过期）

💡 点击链接即可直接进入管理界面，无需额外登录。
⚠️ Token 过期后请重新发送 /web 获取新链接。
```

### 3.5 异常处理

| 异常场景 | Bot 回复 |
|----------|----------|
| WebUI 未启动 | 「WebUI 服务尚未启动，请使用 `python main.py --web` 启动。」 |
| Token 生成失败 | 「生成访问链接失败，请稍后重试或查看日志。」 |
| 非 root 用户触发 | Pyrogram `filters.user` 自动拦截，无回复 |

---

## 4. `/batch` 命令详细设计

### 4.1 设计定位

`/batch` 提供**简化版批量操作入口**：用户在 Bot 中逐条发送链接或消息，Bot 收集后统一提交为一个批量任务。复杂参数（日期范围、类型过滤、资源告警确认等）在提交后由 WebUI 或 TaskManager 的预览阶段处理；Bot 端不做复杂表单。

### 4.2 状态机

```
                    ┌─────────────┐
                    │    IDLE     │ ← 默认状态
                    └──────┬──────┘
                           │
              用户发送 /batch
                    ┌──────▼──────┐
                    │  WAITING    │ ← 等待用户输入
                    │   INPUT     │
                    └──────┬──────┘
                           │
              用户发送有效链接/消息
                    ┌──────▼──────┐
                    │ COLLECTING  │ ← 持续收集
                    └──────┬──────┘
                           │
              用户发送 /done
                    ┌──────▼──────┐
                    │  SUBMITTING │ ← 提交批量任务
                    └──────┬──────┘
                           │
              任务创建成功
                    ┌──────▼──────┐
                    │    IDLE     │ ← 回到空闲
                    └─────────────┘
                           ▲
                           │
              用户发送 /cancel 或超时
```

### 4.3 用户输入收集规则

- 在 `WAITING_INPUT` / `COLLECTING` 状态下，用户每条消息视为一个待处理项。
- 有效输入：
  - `https://t.me/...` 单条消息链接
  - 纯数字消息 ID（Bot 将其与当前默认上下文组合，或要求用户补充频道）
- 无效输入：非链接、非数字、以 `/` 开头的命令（`/done`、`/cancel` 除外）
- 每收到一条有效输入，Bot 更新提示消息：「当前已收集 N 条，继续发送或发送 /done 结束。」

### 4.4 超时处理

- 会话超时时间：10 分钟（可配置 `bot.batch_timeout_seconds`）。
- 超时行为：
  1. `InteractionManager.check_timeout()` 定期扫描超时会话。
  2. 超时后自动取消会话，清空已收集项。
  3. Bot 向用户发送：「批量操作已超时取消，请重新发送 /batch 开始。」
- 用户发送任意非 `/batch` 消息时，重置超时计时器。

### 4.5 结束与提交

- 用户发送 `/done`：
  1. 校验收集项非空。
  2. 调用 `TaskManager.create_batch_task(items=..., default_params=...)`。
  3. 若任务进入预览/告警阶段，由 TaskManager 返回任务 ID，Bot 仅回复「批量任务 #xxx 已创建，请通过 /status 或 WebUI 查看进度。」
- 用户发送 `/cancel`：
  1. 立即取消会话，丢弃已收集项，回到 `IDLE`。

### 4.6 回复文案示例

**进入批量模式：**

```text
📦 批量操作模式

请逐条发送需要处理的链接或消息 ID。
发送 /done 结束收集并创建任务。
发送 /cancel 取消。

当前: 0 条待处理

💡 提示：复杂批量操作（日期过滤、类型过滤、媒体组）请使用 WebUI。
发送 /web 获取访问地址。
```

**收集过程中：**

```text
📦 批量操作模式

当前: 3 条待处理
已收集:
• https://t.me/c/1/100
• https://t.me/c/1/101
• https://t.me/c/1/102

继续发送链接，或发送 /done 提交。
```

---

## 5. `/setup_repository` 命令详细设计

### 5.1 设计定位

`/setup_repository` 提供仓库频道的 Bot 端配置入口。用户通过该命令指定一个 Telegram 频道作为仓库频道，Bot 验证输入格式、解析频道 ID、检查管理员权限后，将 `chat_id` 写入配置。仓库模式启用后，下载的媒体文件将自动存储到该频道，实现去重和分发。

### 5.2 触发条件

- 命令：`/setup_repository <频道标识>` 或 `/setup_repository`（无参数时发送欢迎消息）
- 权限：`filters.user(self.root)`，仅登录用户账户 ID 可触发。
- 依赖：`ConfigManager` 实例已注入 `BotCommands`。

### 5.3 处理流程

```
用户发送 /setup_repository <频道标识>
  │
  ▼
Bot 通过 filters.user(self.root) 校验身份
  │
  ▼
解析命令参数，无参数时发送欢迎消息和使用说明
  │
  ▼
调用 validate_channel_input(channel_input) 验证输入格式
  │
  ├─ 无效 → 回复错误提示（支持的格式列表）
  │
  ▼
调用 resolve_channel_id(client, channel_input) 解析为数字 chat_id
  │
  ├─ 解析失败 → 回复错误提示
  │
  ▼
调用 _check_admin_permission(client, chat_id) 检查 Bot 管理员权限
  │
  ├─ 权限不足 → 回复权限不足提示
  │
  ▼
调用 config_manager.set_repository_chat_id(chat_id) 保存配置
  │
  ├─ 保存失败 → 回复配置保存失败提示
  │
  ▼
回复成功消息（含频道 ID）
```

### 5.4 频道输入验证与解析

#### 5.4.1 支持的输入格式

| 格式 | 示例 | 验证正则 | 返回类型 |
|------|------|----------|----------|
| 数字 ID | `-1001234567890` | `^-?\d+$` | `"numeric_id"` |
| @用户名 | `@my_repo` | `^@[a-zA-Z]\w{3,30}$` | `"username"` |
| t.me 链接 | `https://t.me/my_repo` | `^https?://t\.me/([a-zA-Z]\w{0,30})$` | `"t_me_link"` |
| 邀请链接 | `https://t.me/+AbCdEf` | `^https?://t\.me/\+[A-Za-z0-9_-]+$` | `"invite_link"` |

#### 5.4.2 验证方法

```python
def validate_channel_input(self, channel_input: str) -> Optional[str]:
    """验证频道输入格式是否合法。

    :param channel_input: 用户输入的频道标识
    :return: 输入类型字符串或 None（无效输入）
    """
```

#### 5.4.3 解析方法

```python
async def resolve_channel_id(self, client, channel_input: str) -> str:
    """将用户输入的频道标识解析为数字 chat_id。

    - 纯数字 ID 直接返回
    - @username / t.me 链接 / 邀请链接通过 client.get_chat() 解析

    :param client: Pyrogram 客户端
    :param channel_input: 用户输入的频道标识
    :return: 解析后的数字 chat_id 字符串
    :raises Exception: 解析失败时抛出异常
    """
```

#### 5.4.4 权限检查方法

```python
async def _check_admin_permission(self, client, chat_id: str) -> bool:
    """检查 Bot 是否在指定频道中拥有管理员权限。

    :param client: Pyrogram 客户端
    :param chat_id: 频道 chat_id
    :return: 是否为管理员
    """
```

### 5.5 回复文案示例

**无参数欢迎消息：**

```text
🗄️ 仓库频道设置

仓库模式会将下载的媒体文件自动存储到指定频道，实现去重和分发功能。

📋 请使用以下命令格式设置仓库频道：
`/setup_repository <频道标识>`

支持的频道标识格式：
  • 频道 ID：`-1001234567890`
  • 用户名：`@my_repo`
  • 频道链接：`https://t.me/my_repo`
  • 邀请链接：`https://t.me/+AbCdEf`

⚠️ Bot 需要在目标频道拥有管理员权限
```

**设置成功：**

```text
✅ 仓库频道设置成功！

📁 频道 ID：`-1001234567890`

仓库模式已启用，下载的媒体文件将自动存储到该频道。
你可以通过 WebUI 查看和管理仓库内容。
```

### 5.6 异常处理

| 异常场景 | Bot 回复 |
|----------|----------|
| 无效的频道标识格式 | 回复错误提示，列出支持的格式 |
| 频道解析失败（不存在/不可访问） | 回复错误提示，建议确认频道存在且 Bot 可访问 |
| Bot 无管理员权限 | 回复权限不足提示，建议在频道设置中将 Bot 设为管理员 |
| 配置保存失败 | 回复配置保存失败提示，建议检查配置文件权限 |
| 无 `config_manager` 实例 | 跳过保存，记录警告日志 |

---

## 6. 复杂操作引导文案

当用户触发已移除命令或试图在 Bot 中执行复杂操作时，统一返回引导文案，不做复杂表单。

### 6.1 旧命令迁移提示

**`/download_chat`：**

```text
📁 频道下载过滤功能已迁移到 WebUI。

WebUI 支持：
✅ 可视化日期范围选择
✅ 下载类型勾选
✅ 关键词过滤
✅ 评论区包含/排除
✅ 任务进度实时监控

获取访问地址: /web
```

**`/table`：**

```text
📊 统计表功能已迁移到 WebUI。

WebUI 支持：
✅ 实时任务统计
✅ 链接/计数/上传统计表导出
✅ 可视化图表

获取访问地址: /web
```

### 6.2 通用 WebUI 引导

```text
🌐 该操作在 WebUI 中更便捷：
✅ 可视化表单
✅ 实时进度
✅ 文件树选择
✅ 资源告警提示

获取访问地址: /web
```

---

## 7. 与核心模块集成

### 7.1 模块依赖图

```
┌──────────────────────────────────────────────────┐
│              module/bot.py (Bot)                  │
├──────────────────────────────────────────────────┤
│  /start /help /download /forward /upload         │
│  /status /web /web_revoke /batch                 │
│  /setup_repository /cancel                       │
└───────────┬─────────────────┬────────────────────┘
            │                 │
    filters.user(self.root)   │
            │                 │
            ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│   TokenManager   │  │ InteractionManager│
│  (Token 生成/撤销)│  │  (/batch 状态管理)│
└──────────────────┘  └──────────────────┘
            │                 │
            ▼                 ▼
┌──────────────────────────────────────────────────┐
│ TaskManager / FileManager / ConfigManager         │
│ RepositoryManager / RepositoryDB                  │
│          (核心业务逻辑层)                          │
└──────────────────────────────────────────────────┘
```

### 7.2 Bot 类属性扩展

在现有 `Bot.__init__` 基础上新增：

```python
self.token_manager: TokenManager = ...      # 注入
self.task_manager: TaskManager = ...        # 注入
self.interaction_manager: InteractionManager = ...  # 注入或内部实例化
self.web_ui_enabled: bool = ...             # 由 main.py 启动参数决定
self.repository_manager: RepositoryManager | None = None  # 仓库模式管理器，可选
```

Downloader 类新增方法：

```python
def _init_repository_manager(self):
    """初始化仓库模式管理器。

    当全局配置中仓库模式启用时，创建 RepositoryDB 和 RepositoryManager 实例。
    如果仓库模式未启用或配置无效，repository_manager 保持为 None。
    """
```

### 7.3 集成点说明

| 功能 | 调用方法 | 返回值处理 |
|------|----------|------------|
| 生成 WebUI Token | `TokenManager.generate(user_id, ttl=3600)` | 拼接 URL 后回复 |
| 撤销 Token | `TokenManager.revoke(user_id)` | 回复撤销数量 |
| 查询任务状态 | `TaskManager.list_tasks(status='running')` | 格式化文本列表 |
| 创建批量任务 | `TaskManager.create_task(task_type='batch', params=...)` | 返回任务 ID |
| 启动批量会话 | `InteractionManager.start_session(user_id, mode='batch')` | 记录会话状态 |
| 收集输入 | `InteractionManager.add_item(user_id, item)` | 更新计数 |
| 结束批量会话 | `InteractionManager.end_session(user_id)` | 返回收集列表 |
| 验证频道输入 | `BotCommands.validate_channel_input(channel_input)` | 返回类型字符串或 None |
| 解析频道 ID | `BotCommands.resolve_channel_id(client, channel_input)` | 返回 chat_id 字符串 |
| 检查管理员权限 | `BotCommands._check_admin_permission(client, chat_id)` | 返回布尔值 |
| 保存仓库频道 ID | `ConfigManager.set_repository_chat_id(chat_id)` | 返回保存是否成功 |

### 7.4 与 ConfigManager 的集成

- `ConfigManager.get_config('web_ui.base_url')` 用于 `/web` 链接拼接。
- `ConfigManager.get_config('bot.batch_timeout_seconds')` 用于 `/batch` 超时时间。
- `ConfigManager.set_repository_chat_id(chat_id)` 用于 `/setup_repository` 保存仓库频道 ID。
- `ConfigManager.get_repository_config()` 用于获取仓库配置分组。
- `ConfigManager.validate_repository_config()` 用于验证仓库配置合法性。
- 若配置中未启用 WebUI，`/web` 命令回复启动指引。

### 7.5 配置合并影响

配置已从独立的 `GlobalConfig` + `UserConfig` 合并为单一 `config.yaml`，由 `ConfigManager` 统一管理：

- `BotCommands` 构造函数新增可选参数 `config_manager: Optional[ConfigManager] = None`，用于 `/setup_repository` 等需要写配置的命令。
- `GlobalConfig` 现从 `UserConfig`（即 `ConfigManager` 底层）读取配置，不再独立维护配置文件。
- Downloader 通过 `_init_global_config(user_config=self.app)` 将合并后的配置传入 `GlobalConfig`。
- 配置访问模式：读操作通过 `ConfigManager.get_config(key)` / `get_repository_config()`，写操作通过 `ConfigManager.set_config(key, value)` / `set_repository_chat_id(chat_id)`。

---

## 8. 交互状态管理（InteractionManager）

### 8.1 职责

`InteractionManager` 负责管理 Bot 端的多轮交互会话，当前仅服务于 `/batch` 模式，后续可扩展至其他需要多轮输入的命令。

### 8.2 数据模型

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

class InteractionMode(Enum):
    BATCH = 'batch'

@dataclass
class InteractionState:
    user_id: int
    mode: InteractionMode
    items: list = field(default_factory=list)
    last_active_at: datetime = field(default_factory=datetime.now)
    timeout_seconds: int = 600
```

### 8.3 接口定义

```python
class InteractionManager:
    def __init__(self, timeout_seconds: int = 600):
        self.sessions: dict[int, InteractionState] = {}
        self.timeout_seconds = timeout_seconds

    def start_session(self, user_id: int, mode: InteractionMode) -> bool:
        """启动会话；若已有会话返回 False。"""

    def add_item(self, user_id: int, item: str) -> int:
        """添加输入项，返回当前总数。"""

    def get_session(self, user_id: int) -> Optional[InteractionState]:
        """获取当前会话。"""

    def reset_timeout(self, user_id: int) -> None:
        """重置会话活跃时间。"""

    def end_session(self, user_id: int) -> list:
        """结束会话并返回收集列表。"""

    def cancel_session(self, user_id: int) -> bool:
        """取消会话。"""

    def check_timeout(self) -> list[int]:
        """返回已超时的 user_id 列表。"""
```

### 8.4 与 Bot 的协作

1. Bot 收到 `/batch` 时调用 `start_session`。
2. Bot 收到普通消息时，先判断 `get_session(user_id)` 是否存在：
   - 存在：调用 `add_item` 并 `reset_timeout`。
   - 不存在：走原有命令/错误处理流程。
3. Bot 收到 `/done` 时调用 `end_session` 并提交任务。
4. Bot 收到 `/cancel` 时调用 `cancel_session`。
5. 后台任务（或在每次消息处理前）调用 `check_timeout` 清理过期会话。

---

## 9. 向后兼容策略

### 9.1 命令兼容

- 保留命令的解析逻辑、错误提示、返回值全部保持与现有代码一致。
- 仅调整 `COMMANDS` 列表（注册到 Telegram Bot 菜单的命令），移除 `/table`、`/download_chat`，新增 `/status`、`/web`、`/web_revoke`、`/batch`、`/setup_repository`。

### 9.2 旧命令兜底

- 对于已移除但用户仍可能发送的命令（`/table`、`/download_chat`），在 `process_error_message` 之前增加一层处理：
  - 识别命令 → 返回迁移提示文案 → 不进入原有业务逻辑。
- 避免直接删除方法，先通过 `bot.py` 内的映射表转发到引导文案，便于后续彻底移除时审计。

### 9.3 配置兼容

- `GlobalConfig.TEMPLATE` 中新增 `web_ui` 相关配置项，使用 `add_missing_keys` 自动补全，不破坏旧配置文件。
- 新增配置项均提供默认值，如 `web_ui.base_url` 默认 `http://127.0.0.1:8080`。

### 9.4 监听功能兼容

- `/listen_download`、`/listen_forward`、`/listen_info` 保持原有入口。
- 复杂监听规则管理后续可在 WebUI 中补充，但 Bot 端入口不删除。

---

## 10. 错误处理

### 10.1 Bot 端错误分类

| 错误类型 | 示例 | 处理方式 |
|----------|------|----------|
| 权限错误 | 非 root 用户触发 | `filters.user(self.root)` 拦截，静默忽略 |
| 语法错误 | `/forward` 缺少参数 | 回复语法示例 |
| 状态冲突 | `/batch` 已在进行中 | 回复「已有批量会话进行中，请先 /cancel」 |
| 资源错误 | 输入项为空时发送 `/done` | 回复「未收集到任何链接，已取消」 |
| 依赖错误 | WebUI 未启动时发送 `/web` | 回复启动指引 |
| 超时错误 | `/batch` 超过 10 分钟 | 自动取消并通知用户 |
| 核心模块错误 | TokenManager 异常 | 记录日志，回复「服务暂不可用」 |

### 10.2 异常处理原则

- Bot 端不吞没异常，所有业务异常记录到日志。
- 对用户回复使用中文、简洁、不含堆栈信息。
- `FloodWait` / `FloodPremiumWait` 沿用现有重试机制。
- 不暴露内部路径、Token 完整值或配置敏感字段。

---

## 11. TDD 测试策略

### 11.1 测试目标

- 新增 Bot 命令处理逻辑单元测试覆盖率 ≥ 80%。
- `/web` Token 生成与链接拼接逻辑 100% 覆盖。
- `/batch` 状态机与超时逻辑 100% 覆盖。
- 向后兼容命令（`/download`、`/forward`、`/upload`）至少保留关键路径回归测试。

### 11.2 测试框架

- 使用 `pytest` + `pytest-asyncio`。
- 使用 `unittest.mock` / `pytest-mock` 模拟 Pyrogram Client、Message、User。

### 11.3 单元测试用例清单

#### `/web` 命令

| 用例 ID | 用例描述 | 预期结果 |
|---------|----------|----------|
| TC-WEB-01 | root 用户发送 `/web` 且 WebUI 已启用 | 返回带 Token 的链接，Token 有效期 1 小时 |
| TC-WEB-02 | WebUI 未启用时发送 `/web` | 回复 WebUI 启动指引 |
| TC-WEB-03 | TokenManager 生成失败 | 回复错误提示，记录日志 |
| TC-WEB-04 | 非 root 用户发送 `/web` | 命令被拦截，无回复 |

#### `/web_revoke` 命令

| 用例 ID | 用例描述 | 预期结果 |
|---------|----------|----------|
| TC-REV-01 | root 用户发送 `/web_revoke` | 撤销所有 Token，返回撤销数量 |
| TC-REV-02 | 无生效 Token 时发送 | 返回「没有可撤销的 Token」 |

#### `/batch` 命令

| 用例 ID | 用例描述 | 预期结果 |
|---------|----------|----------|
| TC-BAT-01 | 发送 `/batch` 进入收集模式 | 会话状态为 WAITING_INPUT |
| TC-BAT-02 | 收集有效链接后发送 `/done` | 调用 TaskManager.create_task，返回任务 ID |
| TC-BAT-03 | 空收集时发送 `/done` | 回复错误，取消会话 |
| TC-BAT-04 | 发送 `/cancel` | 会话取消，状态回到 IDLE |
| TC-BAT-05 | 会话超时 | 自动取消并通知用户 |
| TC-BAT-06 | 会话进行中再次发送 `/batch` | 回复已有会话提示 |
| TC-BAT-07 | 收集无效输入 | 忽略或提示，不影响已有项 |

#### `/status` 命令

| 用例 ID | 用例描述 | 预期结果 |
|---------|----------|----------|
| TC-STA-01 | 无任务时发送 `/status` | 回复「当前没有运行中任务」 |
| TC-STA-02 | 有运行中和排队任务 | 回复任务列表与状态 |

#### `/setup_repository` 命令

| 用例 ID | 用例描述 | 预期结果 |
|---------|----------|----------|
| TC-REPO-01 | 发送 `/setup_repository` 无参数 | 回复欢迎消息和使用说明 |
| TC-REPO-02 | 发送 `/setup_repository -1001234567890` 有效数字 ID | 验证通过，解析成功，权限检查通过，保存配置，回复成功 |
| TC-REPO-03 | 发送 `/setup_repository @my_repo` 有效用户名 | 通过 `client.get_chat()` 解析，保存配置 |
| TC-REPO-04 | 发送 `/setup_repository https://t.me/my_repo` 有效链接 | 通过 `client.get_chat()` 解析，保存配置 |
| TC-REPO-05 | 发送 `/setup_repository https://t.me/+AbCdEf` 有效邀请链接 | 通过 `client.get_chat()` 解析，保存配置 |
| TC-REPO-06 | 发送无效格式输入 | 回复错误提示，列出支持的格式 |
| TC-REPO-07 | 频道解析失败（不存在/不可访问） | 回复错误提示 |
| TC-REPO-08 | Bot 无管理员权限 | 回复权限不足提示 |
| TC-REPO-09 | 配置保存失败 | 回复配置保存失败提示 |
| TC-REPO-10 | 无 `config_manager` 实例时设置 | 跳过保存，记录警告日志 |
| TC-REPO-11 | `setup_repository` 在 COMMANDS 列表中 | 命令名和描述均存在 |

#### 向后兼容命令

| 用例 ID | 用例描述 | 预期结果 |
|---------|----------|----------|
| TC-COMP-01 | `/download https://t.me/c/1/100` | 返回任务创建提示 |
| TC-COMP-02 | `/forward a b 1 100` 语法正确 | 返回参数字典 |
| TC-COMP-03 | `/upload /path file 目标` | 返回上传任务创建提示 |
| TC-COMP-04 | 发送 `/table` | 回复迁移提示，不进入原逻辑 |
| TC-COMP-05 | 发送 `/download_chat` | 回复迁移提示，不进入原逻辑 |

### 11.4 Mock 点

- `pyrogram.Client`：模拟 `send_message`、`edit_message_text`、`set_bot_commands`、`get_me`、`get_chat`、`get_chat_member`。
- `pyrogram.types.Message`：构造 `from_user.id`、`text`、`id`。
- `TokenManager`：模拟 `generate`、`revoke`、`validate`。
- `TaskManager`：模拟 `list_tasks`、`create_task`。
- `ConfigManager`：模拟 `get_config`、`get_repository_config`、`set_repository_chat_id` 返回值。
- `datetime.now`：用于 `/batch` 超时测试。

### 11.5 测试目录建议

```
tests/
├── __init__.py
├── conftest.py
├── bot/
│   ├── __init__.py
│   ├── test_web_command.py
│   ├── test_batch_command.py
│   ├── test_status_command.py
│   ├── test_bot_setup_repository.py
│   └── test_backward_compat.py
└── core/
    └── test_interaction_manager.py
```

---

## 12. 依赖关系

### 12.1 新增依赖

| 依赖 | 用途 | 是否必选 |
|------|------|----------|
| `module/core/token_manager.py` | Token 生成与验证 | 是 |
| `module/core/task_manager.py` | 任务创建与查询 | 是 |
| `module/core/interaction_manager.py` | `/batch` 状态管理 | 是 |
| `module/core/config_manager.py` | 统一配置读写（含 repository 配置） | 是 |
| `module/core/repository_manager.py` | 仓库模式编排（去重/分发） | 否（仓库模式启用时必选） |
| `module/core/repository_db.py` | 仓库数据持久化 | 否（仓库模式启用时必选） |

### 12.2 现有依赖

- `pyrogram`：Bot 客户端、消息处理、filters。
- `module/language.py`：文案翻译（可选，保持现有 `_t` 调用）。
- `module/enums.py`：`BotCommandText`、`BotButton`、`BotCallbackText` 等。
- `module/config.py`：`GlobalConfig` 配置读取。

### 12.3 循环依赖规避

- Bot 模块只依赖核心模块的接口，不依赖核心模块内部实现。
- 核心模块（TaskManager、TokenManager）不反向依赖 `Bot`。
- 通过依赖注入（构造函数传入）的方式在 `main.py` 中完成组装。

---

## 13. 风险与假设

### 13.1 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 旧用户习惯 `/download_chat` 复杂表单 | 体验落差 | 在移除命令回复中明确 WebUI 优势，并提供 `/web` 快速入口 |
| `filters.user(self.root)` 在动态 root 更新时延迟 | 权限误判 | root ID 在 Bot 启动时一次性加载，当前单用户场景下可接受 |
| Token 明文出现在 Telegram 聊天记录 | 泄露风险 | Token 仅 1 小时有效；WebUI 首次验证后下发 HttpOnly Cookie |
| `/batch` 会话超时与真实任务执行混淆 | 用户困惑 | 超时仅针对收集会话，已提交任务不受影响 |
| 并发消息导致 `/batch` 状态竞争 | 数据不一致 | 单用户 + 单 Bot 实例，状态操作串行化；后续如需扩展再加锁 |

### 13.2 假设

1. 当前版本为单用户模型，`self.root` 仅包含一个用户 ID。
2. WebUI 与 Bot 运行在同一进程或同一信任网络中，`base_url` 可配置。
3. TokenManager 已实现并保证线程/协程安全。
4. TaskManager 的 `create_task` 接口支持 `task_type='batch'` 或等效批量任务创建。
5. 用户已具备访问 WebUI 的网络条件（浏览器可达 `base_url`）。

---

## 14. 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-06-18 | 初始版本，完成 Bot 端重构模块设计 |
| v1.1 | 2026-06-21 | 新增 `/setup_repository` 命令设计；新增频道验证与解析方法；更新 BotCommands 构造函数（config_manager 参数）；更新 Bot 类属性（repository_manager）；更新配置合并影响说明；新增仓库模式相关依赖 |

---

> **文档结束**
