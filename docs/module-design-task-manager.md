# TaskManager 模块级开发设计文档

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **模块**: TaskManager（任务管理器）  
> **文档版本**: v1.0  
> **创建日期**: 2026-06-18  
> **状态**: 草案  
> **作者**: SOLO

---

## 1. 设计目标与职责边界

### 1.1 设计目标

TaskManager 是核心业务层中负责**任务全生命周期管理**的模块，目标是为 Bot 端和 WebUI 端提供统一、可靠、可观测的任务调度能力：

1. **统一任务抽象**：将下载、转发、上传三种业务动作抽象为同一类 `Task`，屏蔽底层 Telegram API 差异。
2. **状态可观测**：任务状态持久化到 SQLite，支持进程重启后恢复，并实时对外暴露进度。
3. **资源可保护**：通过阈值与并发限制，防止单任务或并发任务耗尽磁盘、带宽和 API 配额。
4. **重试可信任**：重试时避免重复下载/上传、避免无效 API 调用、避免不必要带宽消耗。
5. **向后兼容**：新 TaskManager 的引入不破坏现有 Bot 命令（`/download`、`/forward`、`/upload`、`/upload_r` 等）的行为与返回文案。

### 1.2 职责边界

| 范围 | TaskManager 负责 | TaskManager 不负责 |
|------|------------------|-------------------|
| 任务 | 创建、排队、启动、重试、取消、状态流转、持久化 | 实际文件下载/上传/转发的 IO 细节（由 `downloader.py` / `uploader.py` / `client.py` 负责） |
| 调度 | 多任务队列、`max_concurrent_tasks` 控制 | 单任务内的下载/上传并发池（由执行器内部通过 `asyncio.Semaphore` 控制） |
| 资源 | 任务总量预估校验、磁盘空间预检、阈值告警 | 磁盘清理、文件去重扫描（由 FileManager 配合） |
| 交互 | 为 Bot / WebUI 提供统一方法，接收操作指令 | Bot 的消息渲染、WebUI 的页面展示与 Token 认证 |
| 持久化 | 任务与子任务状态落库 | 配置持久化（ConfigManager）、Token 持久化（TokenManager） |

### 1.3 兼容性要求

- 现有 `module/task.py` 中的 `DownloadTask` 与 `UploadTask` 继续保留，作为**执行器内部的任务跟踪对象**，不直接删除。
- 新 `TaskManager` 在 Bot 命令入口处被调用，将原命令参数转换为 `Task` 后排队执行；原命令返回给用户的文案不变。
- WebUI 通过 RESTful API 直接调用 `TaskManager` 公共方法，不绕过 TaskManager 直接操作下载/上传逻辑。

---

## 2. 任务状态机

### 2.1 任务级状态（Task Status）

任务级状态描述整个任务的宏观生命周期。

| 状态 | 说明 | 允许转换 |
|------|------|---------|
| `pending` | 任务已创建，等待启动或排队 | `pending` → `queued` / `running` / `cancelled` |
| `queued` | 任务在队列中等待资源（超出 `max_concurrent_tasks`） | `queued` → `running` / `cancelled` |
| `running` | 任务正在执行 | `running` → `completed` / `failed` / `cancelled` |
| `completed` | 任务全部子任务成功 | 终态 |
| `failed` | 任务执行失败且存在不可恢复错误，或达到最大重试次数 | 终态（可 `retry` 后重新进入 `pending`） |
| `cancelled` | 用户取消或超时取消 | 终态（可 `retry` 后重新进入 `pending`） |

### 2.2 子任务/文件项状态（Item Status）

每个子任务对应一条消息或一个本地文件。

| 状态 | 说明 |
|------|------|
| `pending` | 待处理 |
| `running` | 正在下载/上传/转发 |
| `success` | 已成功完成 |
| `failed` | 失败，记录失败原因与重试次数 |
| `skipped` | 因去重、类型过滤、消息被删除等原因跳过 |
| `cancelled` | 因任务取消而终止 |

### 2.3 Bot 批量输入会话状态（Interaction State）

Bot 端 `/batch` 命令使用独立的轻量状态机，由 `InteractionManager` 托管，TaskManager 只接收最终聚合后的 `Task`。

```
                    ┌─────────────┐
                    │   IDLE      │ ← 默认状态
                    └──────┬──────┘
                           │
          用户触发 /batch  │
                    ┌──────▼──────┐
                    │ WAITING     │ ← 等待用户逐条输入链接
                    │ _INPUT      │
                    └──────┬──────┘
                           │
              用户输入链接  │ / 文件选择
                    ┌──────▼──────┐
                    │ PROCESSING  │ ← 校验单条输入
                    │ _INPUT      │
                    └──────┬──────┘
                           │
              校验完成，返回 │
                    ┌──────▼──────┐
                    │ WAITING     │ ← 继续等待
                    │ _INPUT      │
                    └──────┬──────┘
                           │
              用户发送 /done 或超时
                    ┌──────▼──────┐
                    │ EXECUTING   │ ← 创建 Task 并提交 TaskManager
                    │ _TASK       │
                    └──────┬──────┘
                           │
              任务完成/取消
                    ┌──────▼──────┐
                    │   IDLE      │
                    └─────────────┘
```

### 2.4 状态转换表

| 当前状态 | 触发事件 | 下一状态 | 说明 |
|---------|---------|---------|------|
| `pending` | `start_task()` / 自动调度 | `queued` / `running` | 若并发未满则直接运行，否则入队 |
| `queued` | 调度器释放槽位 | `running` | 按 FIFO 出队 |
| `queued` | `cancel_task()` | `cancelled` | 从队列中移除 |
| `running` | 所有子任务 `success` / `skipped` | `completed` | 释放并发槽 |
| `running` | 存在子任务 `failed` 且不可恢复 | `failed` | 释放并发槽 |
| `running` | `cancel_task()` | `cancelled` | 向执行器发送取消信号 |
| `failed` / `cancelled` | `retry_task()` | `pending` | 重置失败/取消的子任务为 `pending` |

---

## 3. 数据模型

### 3.1 Task 类

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Union


class TaskType(str, Enum):
    DOWNLOAD = "download"      # 下载到本地
    FORWARD = "forward"        # 先下载再上传到目标频道
    UPLOAD = "upload"          # 上传本地文件到目标频道


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务聚合根对象。"""

    id: str                                 # 全局唯一任务 ID，UUID4
    task_type: TaskType                     # 任务类型
    status: TaskStatus = TaskStatus.PENDING
    params: dict = field(default_factory=dict)   # 原始业务参数（源频道、目标频道、范围等）
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_items: int = 0
    success_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    total_size_bytes: int = 0               # 预估总字节数（用于资源保护）
    error_message: Optional[str] = None     # 失败时的汇总错误信息
    retry_count: int = 0                    # 已重试次数
    max_retry_count: int = 5                # 从配置读取，默认 5
    extra: dict = field(default_factory=dict)    # 扩展字段（如 with_delete、media_group_id）
```

### 3.2 TaskItem 类（子任务/文件项）

```python
@dataclass
class TaskItem:
    """任务下的最小执行单元。"""

    id: str                                 # 子任务 ID，UUID4
    task_id: str                            # 所属 Task.id
    status: ItemStatus = ItemStatus.PENDING
    source_id: Optional[Union[int, str]] = None   # 消息 ID / 本地文件路径
    source_link: Optional[str] = None       # 消息链接
    target_id: Optional[Union[int, str]] = None   # 目标频道 ID / 目标路径
    file_path: Optional[str] = None         # 本地文件路径（下载/转发后）
    file_size: int = 0                      # 文件大小（字节）
    file_sha256: Optional[str] = None       # 本地文件 SHA256（用于去重与断点续传）
    telegram_file_id: Optional[str] = None  # Telegram file_id（上传成功后回填）
    uploaded_message_id: Optional[int] = None   # 上传/转发后的消息 ID
    retry_count: int = 0
    error_code: Optional[str] = None        # 失败原因分类码
    error_message: Optional[str] = None
    last_progress_bytes: int = 0            # 最后记录进度（用于断点续传）
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    extra: dict = field(default_factory=dict)
```

### 3.3 数据库表结构

采用 SQLite，通过 `aiosqlite` 或 `sqlite3` 异步访问。表名前缀 `tm_`（TaskManager）。

#### 3.3.1 `tm_tasks` 任务主表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | 任务 UUID |
| `task_type` | TEXT NOT NULL | download / forward / upload |
| `status` | TEXT NOT NULL | pending / queued / running / completed / failed / cancelled |
| `params` | TEXT NOT NULL | JSON 序列化参数 |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC 时间 |
| `started_at` | TEXT | ISO-8601 UTC 时间 |
| `completed_at` | TEXT | ISO-8601 UTC 时间 |
| `total_items` | INTEGER DEFAULT 0 | 子任务总数 |
| `success_items` | INTEGER DEFAULT 0 | 成功数 |
| `failed_items` | INTEGER DEFAULT 0 | 失败数 |
| `skipped_items` | INTEGER DEFAULT 0 | 跳过数 |
| `total_size_bytes` | INTEGER DEFAULT 0 | 预估总大小 |
| `error_message` | TEXT | 汇总错误 |
| `retry_count` | INTEGER DEFAULT 0 | 已重试次数 |
| `max_retry_count` | INTEGER DEFAULT 5 | 最大重试次数 |
| `extra` | TEXT | JSON 扩展字段 |

索引：

```sql
CREATE INDEX idx_tm_tasks_status ON tm_tasks(status);
CREATE INDEX idx_tm_tasks_created_at ON tm_tasks(created_at);
```

#### 3.3.2 `tm_task_items` 子任务表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | 子任务 UUID |
| `task_id` | TEXT NOT NULL | 外键（tm_tasks.id） |
| `status` | TEXT NOT NULL | pending / running / success / failed / skipped / cancelled |
| `source_id` | TEXT | 消息 ID 或文件路径 |
| `source_link` | TEXT | 消息链接 |
| `target_id` | TEXT | 目标频道 ID |
| `file_path` | TEXT | 本地文件路径 |
| `file_size` | INTEGER DEFAULT 0 | 文件大小 |
| `file_sha256` | TEXT | 文件哈希 |
| `telegram_file_id` | TEXT | Telegram file_id |
| `uploaded_message_id` | INTEGER | 上传后消息 ID |
| `retry_count` | INTEGER DEFAULT 0 | 子任务重试次数 |
| `error_code` | TEXT | 错误分类码 |
| `error_message` | TEXT | 错误信息 |
| `last_progress_bytes` | INTEGER DEFAULT 0 | 最后进度字节 |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC 时间 |
| `updated_at` | TEXT NOT NULL | ISO-8601 UTC 时间 |
| `extra` | TEXT | JSON 扩展字段 |

索引：

```sql
CREATE INDEX idx_tm_task_items_task_id ON tm_task_items(task_id);
CREATE INDEX idx_tm_task_items_status ON tm_task_items(status);
CREATE INDEX idx_tm_task_items_sha256 ON tm_task_items(file_sha256);
```

#### 3.3.3 `tm_task_events` 任务事件/日志表（可选，用于监控与审计）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | 自增 ID |
| `task_id` | TEXT NOT NULL | 任务 ID |
| `item_id` | TEXT | 子任务 ID，可为空 |
| `event_type` | TEXT NOT NULL | created / started / progress / failed / retried / cancelled / completed |
| `message` | TEXT | 事件描述 |
| `payload` | TEXT | JSON 附加数据 |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC 时间 |

索引：

```sql
CREATE INDEX idx_tm_task_events_task_id ON tm_task_events(task_id);
```

---

## 4. 接口契约

### 4.1 TaskManager 公共方法

```python
class TaskManager:
    """任务管理器 - Bot 和 WebUI 共享（单用户）。"""

    def __init__(
        self,
        config: dict,
        db_path: str,
        user_client: pyrogram.Client,
        bot_client: Optional[pyrogram.Client] = None,
        notify_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        Args:
            config: 全局配置字典，至少包含 resource_limits。
            db_path: SQLite 数据库路径。
            user_client: Telegram 用户会话 Client。
            bot_client: Telegram Bot Client，可选。
            notify_callback: 任务完成/失败通知回调。
        """

    async def initialize(self) -> None:
        """初始化：建表、加载未完成任务。"""

    async def shutdown(self) -> None:
        """优雅关闭：取消运行中任务、持久化状态、释放资源。"""

    # ---------------- 任务操作 ----------------

    async def create_task(
        self,
        task_type: TaskType,
        params: dict,
        auto_start: bool = True
    ) -> Task:
        """
        创建任务。
        1. 参数校验与消息范围解析。
        2. 资源预检（磁盘空间、任务大小阈值）。
        3. 生成 Task 与 TaskItem，落库。
        4. 若 auto_start=True 且并发未满，则启动；否则 queued。
        """

    async def start_task(self, task_id: str) -> bool:
        """
        手动启动任务。
        - pending → running（并发未满）或 pending → queued（并发已满）。
        - 非 pending 状态返回 False。
        """

    async def retry_task(self, task_id: str) -> bool:
        """
        重试任务。
        - 仅对 failed / cancelled 状态有效。
        - 将 failed / cancelled 子任务重置为 pending，success / skipped 子任务保持不变。
        - 增加 retry_count，重新进入调度。
        """

    async def cancel_task(self, task_id: str, reason: str = "user") -> bool:
        """
        取消任务。
        - pending / queued：直接取消。
        - running：发送取消信号，等待执行器安全退出后标记 cancelled。
        - completed / failed：不可取消，返回 False。
        """

    # ---------------- 查询 ----------------

    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务基本信息。"""

    async def get_task_items(
        self,
        task_id: str,
        status: Optional[ItemStatus] = None
    ) -> list[TaskItem]:
        """获取任务子任务列表，支持按状态过滤。"""

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Task]:
        """分页查询任务列表。"""

    async def get_task_stats(self, task_id: str) -> dict:
        """
        获取任务实时统计：
        {
            "total": int,
            "success": int,
            "failed": int,
            "skipped": int,
            "progress": float,      # 0.0 ~ 1.0
            "downloaded_bytes": int,
            "uploaded_bytes": int,
            "speed_bps": float      # 最近 5 秒平均速度
        }
        """

    # ---------------- 资源与配置 ----------------

    async def estimate_task_size(
        self,
        task_type: TaskType,
        params: dict
    ) -> tuple[int, int]:
        """
        预估任务大小与消息数。
        Returns: (total_size_bytes, total_items)
        - 全部消息模式使用抽样估算，避免大量 API 调用。
        """

    async def check_resource_limits(self, task: Task) -> tuple[bool, str]:
        """
        资源检查。
        Returns: (is_allowed, message)
        - 检查磁盘剩余空间是否低于 `min_disk_space_gb`。
        - 检查任务大小是否超过 `task_size_max_gb`。
        - 检查 5GB ~ 10GB 区间需告警（返回 allowed=True 但携带 warning 标记）。
        """

    # ---------------- 内部回调 ----------------

    async def _on_item_progress(
        self,
        task_id: str,
        item_id: str,
        downloaded_bytes: int,
        total_bytes: int
    ) -> None:
        """执行器回调：子任务进度更新。"""

    async def _on_item_complete(
        self,
        task_id: str,
        item_id: str,
        result: dict
    ) -> None:
        """执行器回调：子任务完成（success / failed / skipped）。"""

    async def _on_task_complete(self, task_id: str) -> None:
        """任务完成后释放并发槽并调度下一个。"""
```

### 4.2 返回约定

- 所有修改状态的方法返回 `bool`，成功为 `True`，失败或状态不允许为 `False`。
- 资源超限、参数非法等场景抛出 `TaskManagerError` 派生异常，调用方转换为 Bot 消息或 HTTP 响应。
- 进度与事件通过 `Monitor` 模块（WebSocket）推送，TaskManager 只负责生成事件，不直接发送 WebSocket 消息。

---

## 5. 任务生命周期详细设计

### 5.1 创建阶段

```
[Bot / WebUI 调用 create_task]
        │
        ▼
[参数校验] ──非法──▶ 抛出 ValidationError
        │
        ▼
[消息范围解析] ──无法解析──▶ 抛出 ValidationError
        │
        ▼
[资源预估]
        │
        ├── total_size > 10GB ──▶ 禁止创建，抛出 ResourceLimitError
        ├── 5GB <= total_size <= 10GB ──▶ 标记 warning=True，允许创建（WebUI 需二次确认）
        └── total_size < 5GB ──▶ 正常创建
        │
        ▼
[磁盘空间预检]
        │
        ├── 剩余空间 < min_disk_space_gb + 预估大小 ──▶ 抛出 ResourceLimitError
        └── 通过
        │
        ▼
[生成 Task + TaskItem，写入 SQLite]
        │
        ▼
[auto_start=True 且并发未满] ──▶ pending → running
[auto_start=False 或并发已满] ──▶ pending → queued
```

### 5.2 启动阶段

1. `create_task()` 或 `start_task()` 被调用。
2. TaskManager 检查当前 `running_count < max_concurrent_tasks`。
   - 若满足，更新任务状态为 `running`，并提交给对应执行器（下载执行器 / 转发执行器 / 上传执行器）。
   - 若不满足，更新任务状态为 `queued`，加入 `asyncio.Queue`。
3. 执行器以异步方式处理子任务，通过回调向 TaskManager 报告进度与结果。

### 5.3 执行阶段

执行器由 TaskManager 内部持有，按任务类型分发：

| 任务类型 | 执行器 | 说明 |
|----------|--------|------|
| `download` | `DownloadExecutor` | 调用 `downloader.py` 中的下载逻辑 |
| `forward` | `ForwardExecutor` | 先下载到本地，再调用上传逻辑；可配置 `with_delete` |
| `upload` | `UploadExecutor` | 调用 `uploader.py` 中的上传逻辑 |

执行器内部约束：

- 使用 `asyncio.Semaphore` 控制 `max_download_concurrency` / `max_upload_concurrency` / `max_forward_concurrency`。
- 每个子任务执行前检查取消信号，若收到取消则立即将子任务状态置为 `cancelled` 并退出。
- 子任务完成后回调 `_on_item_complete()`，由 TaskManager 统一落库与聚合统计。

### 5.4 完成阶段

- 当所有子任务状态为 `success` / `skipped` 时，任务状态变为 `completed`。
- 当存在子任务为 `failed` 且已耗尽重试次数或错误不可恢复时，任务状态变为 `failed`。
- 任务完成后：
  1. 释放并发槽，`running_count -= 1`。
  2. 持久化最终状态。
  3. 触发 `notify_callback` 发送完成/失败通知。
  4. 检查队列，若存在 `queued` 任务则自动出队并启动。

### 5.5 取消阶段

| 任务状态 | 行为 |
|----------|------|
| `pending` | 直接标记 `cancelled`，不入队。 |
| `queued` | 从队列中移除并标记 `cancelled`。 |
| `running` | 设置 `cancel_event`，执行器收到后优雅停止；所有未完成的子任务标记 `cancelled`；已完成的子任务保留。 |
| `completed` / `failed` | 不可取消，返回 `False`。 |

### 5.6 Bot 端兼容路径

现有 Bot 命令不直接感知 `TaskManager`，由 `Bot` 类内部转换：

- `/download <link> [start_id] [end_id]` → 创建 `TaskType.DOWNLOAD`。
- `/forward <origin> <target> <start> <end>` → 创建 `TaskType.FORWARD`。
- `/upload <file> <target>` / `/upload_r <folder> <target>` → 创建 `TaskType.UPLOAD`。
- 命令返回给用户的文案保持原样，只在内部将任务提交给 TaskManager。

---

## 6. 并发控制与资源保护

### 6.1 并发维度

| 配置项 | 默认值 | 作用范围 | 控制方式 |
|--------|--------|----------|----------|
| `max_concurrent_tasks` | 1 | TaskManager 全局 | `asyncio.Semaphore` |
| `max_download_concurrency` | 3 | 单个任务内 | 下载执行器 `Semaphore` |
| `max_upload_concurrency` | 1 | 单个任务内 | 上传执行器 `Semaphore` |
| `max_forward_concurrency` | 1 | 单个任务内 | 转发执行器 `Semaphore` |

### 6.2 资源限制配置

```yaml
resource_limits:
  max_concurrent_tasks: 1
  max_download_concurrency: 3
  max_upload_concurrency: 1
  max_forward_concurrency: 1

  min_disk_space_gb: 2
  memory_limit_mb: 512

  task_size_warning_gb: 5
  task_size_max_gb: 10
```

### 6.3 任务大小边界判断

```python
def check_task_size(total_size_bytes: int) -> tuple[str, Optional[str]]:
    gb = total_size_bytes / (1024 ** 3)
    if gb > 10:
        return "forbidden", "单次任务超过 10GB，禁止创建。"
    elif gb >= 5:
        return "warning", f"当前任务 {gb:.2f}GB，超过 5GB 告警阈值，请确认后继续。"
    else:
        return "ok", None
```

- `< 5GB`：正常创建。
- `5GB ~ 10GB`：允许创建，但 `Task.warning` 字段置为 `True`，WebUI 弹窗二次确认；Bot 端发送告警文案并等待用户确认（`/confirm` 或按钮）。
- `> 10GB`：直接抛出 `ResourceLimitError`，禁止创建。

### 6.4 磁盘空间保护

创建任务前：

```python
required_bytes = task.total_size_bytes
available_bytes = shutil.disk_usage(download_dir).free
min_required_bytes = (config.min_disk_space_gb * 1024 ** 3) + required_bytes

if available_bytes < min_required_bytes:
    raise ResourceLimitError(f"磁盘剩余空间不足，需至少保留 {min_required_bytes / (1024**3):.2f}GB。")
```

转发任务若开启 `with_delete`，上传成功后立即删除本地文件以释放空间。

### 6.5 队列行为

- 使用 `asyncio.Queue` 存储 `queued` 任务 ID。
- 任务按创建顺序执行（FIFO）。
- 取消 `queued` 任务时，需遍历队列移除对应 ID；因队列长度通常很小，线性扫描可接受。
- 进程启动时，`initialize()` 将数据库中 `queued` 和 `running` 任务重新加载。`running` 任务视为异常中断，自动重置为 `pending` 或 `failed`（根据子任务完成情况）。

---

## 7. 重试逻辑详细设计

### 7.1 核心原则

1. **避免重复下载**：已下载且文件完整的子任务，重试时直接跳过。
2. **避免重复上传**：已上传成功的子任务（存在 `telegram_file_id` 或 `uploaded_message_id`），重试时直接跳过。
3. **避免无效 API 调用**：消息被删除、频道无权限、被封禁等错误不可重试。
4. **避免不必要带宽消耗**：支持断点续传（上传使用 `file_part` 记录）。

### 7.2 错误分类与可重试性

| 错误码 | 来源示例 | 可重试 | 行为 |
|--------|---------|--------|------|
| `NETWORK_TIMEOUT` | 网络超时、连接断开 | 是 | 指数退避后重试 |
| `FLOOD_WAIT` | Telegram 限流 | 是 | 等待指定秒数后继续 |
| `FILE_INCOMPLETE` | 本地文件大小 < 预期 | 是 | 从已下载大小处续传 |
| `MESSAGE_DELETED` | 消息被删除 | 否 | 标记 skipped，记录原因 |
| `CHANNEL_BANNED` | 频道被封 | 否 | 标记 failed，任务终止 |
| `NO_PERMISSION` | 无访问权限 | 否 | 标记 failed，任务终止 |
| `FILE_TOO_LARGE` | 单文件超过 Telegram 限制 | 否 | 标记 skipped |
| `DUPLICATE_UPLOAD` | 目标频道已存在 | 否 | 标记 success（幂等视为成功） |
| `UNKNOWN` | 未知错误 | 是（有限次） | 纳入重试计数 |

### 7.3 子任务重试流程

```
子任务失败
    │
    ▼
[错误分类] ──不可重试──▶ 标记 skipped / failed，不累加重试计数
    │
    ▼
[可重试]
    │
    ├── retry_count < max_retry_count ──▶ 等待退避时间，重置为 pending
    └── retry_count >= max_retry_count ──▶ 标记 failed
```

退避策略：

```python
def backoff_seconds(retry_count: int, error_code: str, flood_wait: int = 0) -> int:
    if error_code == "FLOOD_WAIT":
        return max(flood_wait, 1)
    # 指数退避：1, 2, 4, 8, 16...
    return min(2 ** retry_count, 300)
```

### 7.4 下载任务重试

1. 检查本地文件是否存在。
2. 若存在且 `os.path.getsize(file_path) == expected_size`，计算 SHA256 与数据库记录比对；一致则标记 `success`，不一致则删除后重新下载。
3. 若不存在，重新下载。
4. 下载器内部使用流式写入，避免全量加载内存。

### 7.5 上传任务重试

1. 检查 `telegram_file_id` 或 `uploaded_message_id` 是否存在；存在则跳过。
2. 检查本地文件是否存在；不存在且属于 forward 任务则重新下载。
3. 上传器内部使用 `UploadTask` 的 `file_part` 机制实现断点续传，重试时从 `get_missing_parts()` 继续。
4. 上传成功后回填 `telegram_file_id` 与 `uploaded_message_id`。

### 7.6 任务级重试 `retry_task()`

1. 校验任务状态为 `failed` 或 `cancelled`。
2. 若 `retry_count >= max_retry_count`，返回 `False`。
3. 将 `failed` / `cancelled` 子任务重置为 `pending`，`retry_count += 1`。
4. 将任务状态改为 `pending`，并调用调度逻辑。
5. 已 `success` / `skipped` 子任务保持原状，不重新执行。

---

## 8. 错误处理

### 8.1 异常体系

```python
class TaskManagerError(Exception):
    """TaskManager 基础异常。"""

class ValidationError(TaskManagerError):
    """参数校验失败。"""

class ResourceLimitError(TaskManagerError):
    """资源限制触发。"""

class TaskNotFoundError(TaskManagerError):
    """任务不存在。"""

class TaskStateError(TaskManagerError):
    """任务状态不允许当前操作。"""

class ExecutorError(TaskManagerError):
    """执行器内部错误。"""
```

### 8.2 错误处理策略

| 场景 | 处理方式 | 用户感知 |
|------|---------|----------|
| 参数校验失败 | 抛出 `ValidationError`，不创建任务 | Bot / WebUI 返回语法错误提示 |
| 资源超限 | 抛出 `ResourceLimitError` | 弹窗/消息提示超出限制 |
| 任务不存在 | 抛出 `TaskNotFoundError` | 提示任务 ID 无效 |
| 状态不允许 | 返回 `False` | 提示当前状态不可操作 |
| 单个子任务失败 | 记录错误码与重试次数，按重试策略处理 | 进度中显示失败数 |
| 执行器未捕获异常 | TaskManager 捕获后标记任务 `failed`，记录 traceback | 任务失败通知 |
| 数据库操作失败 | 记录 error log，任务状态保留在内存，下一次持久化重试 | 可能状态丢失风险（见 11 节） |

### 8.3 日志规范

- 任务级别事件写入 `tm_task_events` 表，用于 WebUI 任务详情展示。
- 异常栈通过 `log.exception` 输出到终端/文件，便于开发者排查。
- 不记录敏感信息（如完整文件路径中的用户目录、Token、Bot Token 等）。

---

## 9. TDD 测试策略

### 9.1 测试目标

- 核心模块单元测试覆盖率 ≥ 80%。
- 重试逻辑、状态机、资源保护必须 100% 覆盖分支。
- 不依赖真实 Telegram 网络连接，所有外部调用 Mock。

### 9.2 单元测试用例清单

#### TaskManager 创建与调度

1. `test_create_download_task_success`：成功创建下载任务，状态为 `pending`。
2. `test_create_task_auto_start_when_slot_available`：并发槽空闲时自动启动，状态变为 `running`。
3. `test_create_task_queued_when_slot_full`：并发满时进入 `queued`。
4. `test_create_task_exceeds_max_size_forbidden`：超过 10GB 禁止创建。
5. `test_create_task_warning_size_flag`：5GB ~ 10GB 设置 warning 标记。
6. `test_create_task_insufficient_disk_space`：磁盘不足禁止创建。
7. `test_start_task_from_pending`：手动启动 pending 任务。
8. `test_start_task_invalid_state`：running 任务调用 start 返回 False。

#### 取消与状态机

9. `test_cancel_pending_task`：pending 任务直接取消。
10. `test_cancel_queued_task`：queued 任务从队列移除并取消。
11. `test_cancel_running_task`：running 任务发送取消信号，子任务标记 cancelled。
12. `test_cancel_completed_task_fails`：completed 任务不可取消。
13. `test_task_state_transitions_all_valid`：遍历所有合法状态转换。

#### 重试逻辑

14. `test_retry_failed_task_resets_failed_items`：重试后 failed 子任务变为 pending。
15. `test_retry_skips_success_items`：已成功的子任务不被重置。
16. `test_retry_reaches_max_count_fails`：超过最大重试次数后 retry 返回 False。
17. `test_retry_download_with_existing_complete_file`：本地文件完整时直接标记 success。
18. `test_retry_download_with_incomplete_file`：本地文件不完整时删除并重试。
19. `test_retry_upload_with_existing_file_id`：已上传成功直接跳过。
20. `test_non_retryable_error_marked_skipped`：消息删除等错误标记 skipped。
21. `test_retry_backoff_flood_wait`：FloodWait 按指定时间等待。
22. `test_retry_backoff_exponential`：普通错误指数退避。

#### 并发控制

23. `test_max_concurrent_tasks_default_one`：默认同时只能运行 1 个任务。
24. `test_max_concurrent_tasks_respected`：配置为 2 时同时运行 2 个任务。
25. `test_queue_fifo_order`：队列按创建顺序执行。
26. `test_task_completion_triggers_next_in_queue`：任务完成后自动启动队列下一个。

#### 持久化

27. `test_task_persisted_to_sqlite`：创建后数据库存在记录。
28. `test_item_persisted_to_sqlite`：子任务随任务一起落库。
29. `test_load_unfinished_tasks_on_initialize`：重启后加载 queued / running 任务。
30. `test_progress_persisted`：子任务进度更新写入数据库。

#### 错误处理

31. `test_invalid_task_type_raises_validation_error`：非法 task_type 抛出异常。
32. `test_missing_required_params_raises_validation_error`：缺少必填参数抛出异常。
33. `test_executor_error_marks_task_failed`：执行器异常被捕获并标记任务失败。
34. `test_database_write_failure_logged`：数据库写入失败记录日志。

### 9.3 Mock 点

| 被测对象 | Mock 目标 | 说明 |
|----------|----------|------|
| TaskManager | `pyrogram.Client` | 所有 Telegram API 调用 |
| TaskManager | `shutil.disk_usage` | 磁盘空间检查 |
| TaskManager | `sqlite3` / `aiosqlite` | 数据库操作（可选，使用内存数据库更快） |
| 执行器 | `downloader.py` / `uploader.py` 函数 | 不执行真实 IO |
| 执行器 | `os.path.getsize`、`calc_sha256` | 文件存在与哈希判断 |
| 执行器 | `asyncio.sleep` | 加速退避等待测试 |
| 回调 | `notify_callback` | 验证通知触发 |

### 9.4 覆盖率目标

| 模块 | 覆盖率目标 |
|------|-----------|
| `task_manager.py` | ≥ 90% |
| `task_executor.py`（执行器） | ≥ 85% |
| 状态机与重试逻辑 | 100% 分支覆盖 |

### 9.5 测试框架

- 使用 `pytest` + `pytest-asyncio`。
- 数据库使用 `:memory:` 或临时文件，测试结束后清理。
- CI 中运行 `pytest tests/unit/test_task_manager.py -v --cov=module/core --cov-report=term-missing`。

---

## 10. 依赖关系

### 10.1 内部依赖

```
TaskManager
    ├── module/enums.py           # TaskType / TaskStatus / ItemStatus 等枚举
    ├── module/config.py          # 读取 resource_limits 配置
    ├── module/client.py          # TelegramClient 封装
    ├── module/downloader.py      # 下载执行细节
    ├── module/uploader.py        # 上传执行细节
    ├── module/task.py            # 现有 DownloadTask / UploadTask（执行器内部复用）
    ├── module/path_tool.py       # safe_delete / calc_sha256
    ├── module/monitor.py         # 进度/事件推送（可选）
    └── module/language.py        # 文案国际化（Bot 通知）
```

### 10.2 外部依赖

| 依赖 | 用途 |
|------|------|
| `pyrogram` | Telegram API 客户端 |
| `aiosqlite` | 异步 SQLite 访问 |
| `dataclasses` | Task / TaskItem 数据模型 |
| `uuid` | 生成任务/子任务 ID |
| `shutil` | 磁盘空间检查 |

### 10.3 被依赖方

```
module/bot.py          # Bot 命令调用 create_task / retry_task / cancel_task
module/api/routes/tasks.py   # WebUI RESTful API 调用 TaskManager
module/api/websocket/tasks.py # WebSocket 从 TaskManager 获取实时状态
module/monitor.py      # 读取 tm_task_events 展示任务日志
```

---

## 11. 风险与假设

### 11.1 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 现有 `module/task.py` 与新 `TaskManager` 状态对象命名冲突 | 中等 | 新模块放在 `module/core/task_manager.py`，旧类保留并作为执行器内部对象使用 |
| SQLite 写入失败导致状态丢失 | 中低 | 关键状态变更先写内存，再异步批量落库；异常时记录日志 |
| 进程崩溃导致 `running` 任务中断 | 中低 | 重启后将 `running` 任务重置为 `pending`，基于子任务状态继续或重试 |
| 大文件 SHA256 计算耗时 | 中低 | 仅在需要时计算，重试时优先比对文件大小；SHA256 作为可选校验 |
| Telegram API 频繁返回 FloodWait | 中 | 执行器统一处理 FloodWait，TaskManager 不强制超时 |
| 用户同时操作 Bot 和 WebUI 导致状态竞态 | 低 | 单用户场景，所有操作都通过同一 TaskManager 实例串行化 |

### 11.2 假设

1. **单用户**：TaskManager 不处理多用户隔离，所有任务属于同一用户。
2. **单进程**：同一时刻只有一个 TaskManager 实例访问 SQLite 数据库。
3. **Bot 命令向后兼容**：现有命令的入口参数和返回文案不变，只在内部转发给 TaskManager。
4. **磁盘路径可写**：任务运行目录对当前进程可读写。
5. **Telegram 客户端已登录**：`user_client` 在 TaskManager 初始化前已完成登录。
6. **网络短期可恢复**：可重试错误在最大重试次数内有望恢复；长期网络中断视为任务失败。
7. **上传幂等**：若目标频道已存在相同文件，视为成功，不重试。

### 11.3 后续可扩展点（本版本不实现）

- 任务暂停/恢复（明确不支持）。
- 多用户隔离。
- 分布式多进程调度。
- 任务优先级与抢占。
- 自动清理过期任务历史。

---

## 12. 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-18 | 初始版本，完成 TaskManager 模块级设计 | SOLO |

---

> **文档结束**
