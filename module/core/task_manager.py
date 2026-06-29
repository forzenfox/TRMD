# coding=UTF-8
"""TaskManager - 任务管理器

负责任务全生命周期管理：
- 创建、排队、启动、重试、取消
- 状态流转与持久化
- 资源保护（大小阈值、磁盘空间）
- 子任务管理
"""

import os
import uuid
import sqlite3
import shutil
import logging
import asyncio
from enum import Enum
from typing import Optional, Union
from dataclasses import dataclass, field
from contextlib import contextmanager

log = logging.getLogger("rich")


# ============================================================
# 枚举定义
# ============================================================


class TaskType(Enum):
    """任务类型。"""

    DOWNLOAD = "download"
    FORWARD = "forward"
    UPLOAD = "upload"


class TaskStatus(Enum):
    """任务状态。"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ItemStatus(Enum):
    """子任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ============================================================
# 数据模型
# ============================================================


@dataclass
class TaskItem:
    """子任务项，对应一条消息或一个本地文件（设计文档 §3.2）。"""

    id: str
    task_id: str
    status: ItemStatus = ItemStatus.PENDING
    source_id: Optional[Union[int, str]] = None
    source_link: Optional[str] = None
    target_id: Optional[Union[int, str]] = None
    file_path: Optional[str] = None
    file_size: int = 0
    file_sha256: Optional[str] = None
    telegram_file_id: Optional[str] = None
    file_unique_id: Optional[str] = None
    uploaded_message_id: Optional[int] = None
    retry_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    last_progress_bytes: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    extra: dict = field(default_factory=dict)

    # ---- 辅助方法 ----

    def mark_success(self):
        """标记为成功。"""
        self.status = ItemStatus.SUCCESS

    def mark_failed(self, reason: str):
        """标记为失败。"""
        self.status = ItemStatus.FAILED
        self.error_message = reason
        self.retry_count += 1

    def mark_skipped(self, reason: str):
        """标记为跳过。"""
        self.status = ItemStatus.SKIPPED
        self.error_message = reason

    def can_retry(self) -> bool:
        """判断是否可重试。"""
        if self.retry_count >= 3:
            return False
        non_retryable = [
            "MESSAGE_ID_INVALID",
            "CHAT_FORBIDDEN",
            "USER_BANNED",
            "CHANNEL_PRIVATE",
        ]
        if self.error_message and any(nr in self.error_message for nr in non_retryable):
            return False
        return True


@dataclass
class Task:
    """任务，对应一个下载/转发/上传操作（设计文档 §3.1）。"""

    task_id: str
    task_type: TaskType
    chat_id: int
    status: TaskStatus = TaskStatus.PENDING
    items: list = field(default_factory=list)
    total_size_bytes: int = 0
    retry_count: int = 0
    max_retry_count: int = 5
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    params: dict = field(default_factory=dict)
    total_items: int = 0
    success_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def success_count(self) -> int:
        """成功子任务数。"""
        if self.success_items > 0 or self.completed_at:
            return self.success_items
        return sum(1 for item in self.items if item.status == ItemStatus.SUCCESS)

    @property
    def failed_count(self) -> int:
        """失败子任务数。"""
        if self.failed_items > 0 or self.completed_at:
            return self.failed_items
        return sum(1 for item in self.items if item.status == ItemStatus.FAILED)

    @property
    def pending_count(self) -> int:
        """待处理子任务数。"""
        return sum(1 for item in self.items if item.status == ItemStatus.PENDING)

    @property
    def progress(self) -> float:
        """任务进度百分比。"""
        if not self.items:
            return 0.0
        return (self.success_count / len(self.items)) * 100


# ============================================================
# 异常定义
# ============================================================


class TaskManagerError(Exception):
    """TaskManager 基础异常。"""

    pass


class InvalidStateTransition(TaskManagerError):
    """无效状态转换异常。"""

    pass


class ResourceLimitExceeded(TaskManagerError):
    """资源限制超出异常。"""

    pass


class TaskNotFoundError(TaskManagerError):
    """任务未找到异常。"""

    pass


# ============================================================
# TaskManager 类
# ============================================================


class TaskManager:
    """任务管理器。

    负责任务创建、调度、状态流转、持久化与资源保护。
    """

    # 允许的状态转换
    VALID_TRANSITIONS = {
        TaskStatus.PENDING: {
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.CANCELLED,
        },
        TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.FAILED: {TaskStatus.PENDING},  # retry
        TaskStatus.CANCELLED: {TaskStatus.PENDING},  # retry
    }

    def __init__(
        self,
        db_path: Optional[str] = None,
        max_concurrent_tasks: int = 1,
        max_retries: int = 3,
        task_size_warning_gb: int = 5,
        task_size_max_gb: int = 10,
        min_disk_space_gb: int = 2,
    ):
        self._db_path = db_path or ":memory:"
        self._max_concurrent_tasks = max_concurrent_tasks
        self._max_retries = max_retries
        self._task_size_warning_gb = task_size_warning_gb
        self._task_size_max_gb = task_size_max_gb
        self._min_disk_space_gb = min_disk_space_gb

        self._tasks: dict[str, Task] = {}
        self._task_queue: list[str] = []
        self._lock = asyncio.Lock()

        self._init_db()
        self._load_tasks_from_db()

    @contextmanager
    def _db_connection(self):
        """数据库连接上下文管理器。"""
        if self._db_path == ":memory:":
            yield None
            return

        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表。"""
        if self._db_path == ":memory:":
            return

        with self._db_connection() as conn:
            cursor = conn.cursor()

            # tm_tasks 任务主表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tm_tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    total_items INTEGER DEFAULT 0,
                    success_items INTEGER DEFAULT 0,
                    failed_items INTEGER DEFAULT 0,
                    skipped_items INTEGER DEFAULT 0,
                    total_size_bytes INTEGER DEFAULT 0,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retry_count INTEGER DEFAULT 5,
                    extra TEXT DEFAULT '{}'
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_tasks_status ON tm_tasks(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_tasks_created_at ON tm_tasks(created_at)"
            )

            # tm_task_items 子任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tm_task_items (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    source_id TEXT,
                    source_link TEXT,
                    target_id TEXT,
                    file_path TEXT,
                    file_size INTEGER DEFAULT 0,
                    file_sha256 TEXT,
                    telegram_file_id TEXT,
                    file_unique_id TEXT,
                    uploaded_message_id INTEGER,
                    retry_count INTEGER DEFAULT 0,
                    error_code TEXT,
                    error_message TEXT,
                    last_progress_bytes INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    extra TEXT DEFAULT '{}',
                    FOREIGN KEY (task_id) REFERENCES tm_tasks(id)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_task_items_task_id ON tm_task_items(task_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_task_items_status ON tm_task_items(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_task_items_sha256 ON tm_task_items(file_sha256)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_task_items_file_unique_id ON tm_task_items(file_unique_id)"
            )

            # tm_task_events 任务事件表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tm_task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    item_id TEXT,
                    event_type TEXT NOT NULL,
                    message TEXT,
                    payload TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tm_task_events_task_id ON tm_task_events(task_id)"
            )

            conn.commit()

    def _load_tasks_from_db(self):
        """从数据库加载未完成的任务。"""
        if self._db_path == ":memory:":
            return

        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tm_tasks")
            rows = cursor.fetchall()

            for row in rows:
                task = self._row_to_task(row)
                self._tasks[task.task_id] = task
                # 加载子任务
                cursor.execute(
                    "SELECT * FROM tm_task_items WHERE task_id = ?", (task.task_id,)
                )
                item_rows = cursor.fetchall()
                for item_row in item_rows:
                    task.items.append(self._row_to_item(item_row))

            # 恢复排队中的任务到队列（防止重启后排队任务丢失）
            queued_ids = [
                t.task_id for t in self._tasks.values() if t.status == TaskStatus.QUEUED
            ]
            if queued_ids:
                self._task_queue.extend(queued_ids)
                log.info(f"已恢复 {len(queued_ids)} 个排队任务: {queued_ids}")

    def _row_to_task(self, row) -> Task:
        """将数据库行转换为 Task。"""
        import json

        # tm_tasks 列: 0=id, 1=task_type, 2=status, 3=params, 4=created_at,
        #               5=started_at, 6=completed_at, 7=total_items, 8=success_items,
        #               9=failed_items, 10=skipped_items, 11=total_size_bytes,
        #               12=error_message, 13=retry_count, 14=max_retry_count, 15=extra

        params = {}
        if row[3]:
            try:
                params = json.loads(row[3])
            except (json.JSONDecodeError, TypeError):
                params = {}

        extra = {}
        if len(row) > 15 and row[15]:
            try:
                extra = json.loads(row[15])
            except (json.JSONDecodeError, TypeError):
                extra = {}

        return Task(
            task_id=row[0],
            task_type=TaskType(row[1]),
            chat_id=params.get("chat_id", 0),
            params=params,
            status=TaskStatus(row[2]),
            total_size_bytes=row[11] or 0,
            retry_count=row[13] or 0,
            max_retry_count=row[14] or 5,
            error_message=row[12],
            created_at=row[4],
            started_at=row[5],
            completed_at=row[6],
            total_items=row[7] or 0,
            success_items=row[8] or 0,
            failed_items=row[9] or 0,
            skipped_items=row[10] or 0,
            extra=extra,
        )

    def _row_to_item(self, row) -> TaskItem:
        """将数据库行转换为 TaskItem。"""
        import json

        # tm_task_items 列: 0=id, 1=task_id, 2=status, 3=source_id, 4=source_link,
        #                   5=target_id, 6=file_path, 7=file_size, 8=file_sha256,
        #                   9=telegram_file_id, 10=file_unique_id, 11=uploaded_message_id,
        #                   12=retry_count, 13=error_code, 14=error_message,
        #                   15=last_progress_bytes, 16=created_at, 17=updated_at, 18=extra

        extra = {}
        if len(row) > 18 and row[18]:
            try:
                extra = json.loads(row[18])
            except (json.JSONDecodeError, TypeError):
                extra = {}

        return TaskItem(
            id=row[0],
            task_id=row[1],
            status=ItemStatus(row[2]),
            source_id=row[3],
            source_link=row[4],
            target_id=row[5],
            file_path=row[6],
            file_size=row[7] or 0,
            file_sha256=row[8],
            telegram_file_id=row[9],
            file_unique_id=row[10],
            uploaded_message_id=row[11],
            retry_count=row[12] or 0,
            error_code=row[13],
            error_message=row[14],
            last_progress_bytes=row[15] or 0,
            created_at=row[16],
            updated_at=row[17],
            extra=extra,
        )

    def _save_task(self, task: Task):
        """保存任务到数据库（tm_tasks 表）。"""
        if self._db_path == ":memory:":
            return
        import json

        task.params["chat_id"] = task.chat_id

        with self._db_connection() as conn:
            cursor = conn.cursor()
            params_json = json.dumps(task.params) if task.params else "{}"
            extra_json = json.dumps(task.extra) if task.extra else "{}"

            cursor.execute(
                """
                INSERT OR REPLACE INTO tm_tasks
                (id, task_type, status, params, created_at, started_at, completed_at,
                 total_items, success_items, failed_items, skipped_items,
                 total_size_bytes, error_message, retry_count, max_retry_count, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task.task_id,
                    task.task_type.value,
                    task.status.value,
                    params_json,
                    task.created_at,
                    task.started_at,
                    task.completed_at,
                    len(task.items),
                    task.success_count,
                    task.failed_count,
                    task.skipped_items,
                    task.total_size_bytes,
                    task.error_message,
                    task.retry_count,
                    task.max_retry_count,
                    extra_json,
                ),
            )
            conn.commit()

    def _save_item(self, task_id: str, item: TaskItem):
        """保存子任务到数据库（tm_task_items 表）。"""
        if self._db_path == ":memory:":
            return
        import json

        extra_json = json.dumps(item.extra) if item.extra else "{}"

        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO tm_task_items
                (id, task_id, status, source_id, source_link, target_id, file_path,
                 file_size, file_sha256, telegram_file_id, file_unique_id,
                 uploaded_message_id, retry_count, error_code, error_message,
                 last_progress_bytes, created_at, updated_at, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item.id,
                    task_id,
                    item.status.value,
                    str(item.source_id) if item.source_id is not None else None,
                    item.source_link,
                    str(item.target_id) if item.target_id is not None else None,
                    item.file_path,
                    item.file_size,
                    item.file_sha256,
                    item.telegram_file_id,
                    item.file_unique_id,
                    item.uploaded_message_id,
                    item.retry_count,
                    item.error_code,
                    item.error_message,
                    item.last_progress_bytes,
                    item.created_at,
                    item.updated_at,
                    extra_json,
                ),
            )
            conn.commit()

    def _validate_transition(self, current: TaskStatus, target: TaskStatus):
        """验证状态转换是否合法。"""
        allowed = self.VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransition(
                f"无效状态转换: {current.value} → {target.value}"
            )

    def _get_running_count(self) -> int:
        """获取当前正在运行的任务数。"""
        return sum(
            1 for task in self._tasks.values() if task.status == TaskStatus.RUNNING
        )

    # ============================================================
    # 公开接口
    # ============================================================

    async def create_task(
        self,
        task_type: TaskType,
        chat_id: int,
        params: Optional[dict] = None,
    ) -> Task:
        """创建任务。"""
        from datetime import datetime

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            task_type=task_type,
            chat_id=chat_id,
            params=params or {},
            max_retry_count=self._max_retries,
            created_at=datetime.now().isoformat(),
        )
        async with self._lock:
            self._tasks[task_id] = task
            self._save_task(task)
        log.info(f"任务已创建: {task_id} ({task_type.value})")
        return task

    async def start_task(self, task_id: str) -> bool:
        """启动任务。"""
        from datetime import datetime

        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")

            running_count = self._get_running_count()
            if running_count >= self._max_concurrent_tasks:
                # 进入队列
                self._validate_transition(task.status, TaskStatus.QUEUED)
                task.status = TaskStatus.QUEUED
                self._task_queue.append(task_id)
                self._save_task(task)
                log.info(f"任务进入队列: {task_id}")
                return False
            else:
                # 直接运行
                self._validate_transition(task.status, TaskStatus.RUNNING)
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._save_task(task)
                log.info(f"任务开始执行: {task_id}")
                return True

    async def complete_task(self, task_id: str):
        """完成任务。"""
        from datetime import datetime

        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")

            self._validate_transition(task.status, TaskStatus.COMPLETED)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            self._save_task(task)
            log.info(f"任务已完成: {task_id}")

            # 尝试启动队列中的下一个任务
            await self._process_queue()

    async def fail_task(self, task_id: str, reason: str):
        """标记任务失败。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")

            self._validate_transition(task.status, TaskStatus.FAILED)
            task.status = TaskStatus.FAILED
            task.error_message = reason
            self._save_task(task)
            log.warning(f"任务失败: {task_id} - {reason}")

            # 尝试启动队列中的下一个任务
            await self._process_queue()

    async def cancel_task(self, task_id: str):
        """取消任务。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")

            self._validate_transition(task.status, TaskStatus.CANCELLED)
            task.status = TaskStatus.CANCELLED
            self._save_task(task)
            log.info(f"任务已取消: {task_id}")

            # 从队列中移除
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)

    async def retry_task(self, task_id: str):
        """重试任务。"""

        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")

            self._validate_transition(task.status, TaskStatus.PENDING)
            task.status = TaskStatus.PENDING
            task.retry_count += 1
            task.error_message = None
            task.started_at = None
            task.completed_at = None

            # 重置失败的子任务
            for item in task.items:
                if item.status == ItemStatus.FAILED and item.can_retry():
                    item.status = ItemStatus.PENDING
                    item.error_message = None
                    self._save_item(task_id, item)

            self._save_task(task)
            log.info(f"任务重试: {task_id} (第 {task.retry_count} 次)")

    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务。"""
        return self._tasks.get(task_id)

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        """获取任务列表。"""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    async def delete_task(self, task_id: str):
        """删除任务及其所有子任务（同时从内存和数据库中删除）。"""
        async with self._lock:
            # 从内存移除
            self._tasks.pop(task_id, None)
            # 从数据库删除
            if self._db_path != ":memory:":
                with self._db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM tm_task_items WHERE task_id = ?", (task_id,)
                    )
                    cursor.execute("DELETE FROM tm_tasks WHERE id = ?", (task_id,))
                    conn.commit()
            log.info(f"任务已删除: {task_id}")

    async def add_items(self, task_id: str, items: list[TaskItem]):
        """添加子任务项。"""
        from datetime import datetime

        now = datetime.now().isoformat()
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")
            for item in items:
                item.task_id = task_id
                item.created_at = now
                item.updated_at = now
            task.items.extend(items)
            for item in items:
                self._save_item(task_id, item)
            self._save_task(task)

    async def update_item_status(
        self,
        task_id: str,
        item_id: str,
        status: ItemStatus,
        error_reason: Optional[str] = None,
    ):
        """更新子任务状态。"""
        from datetime import datetime

        now = datetime.now().isoformat()
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")
            for item in task.items:
                if item.id == item_id:
                    item.status = status
                    item.updated_at = now
                    if error_reason:
                        item.error_message = error_reason
                    self._save_item(task_id, item)
                    self._save_task(task)
                    break

    async def update_file_paths(self, task_id: str, file_paths: list[str]):
        """更新任务的已下载文件路径列表。

        Args:
            task_id: 任务 ID
            file_paths: 已下载文件的完整路径列表
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")
            task.params["file_paths"] = file_paths
            self._save_task(task)
            log.info(f"任务 {task_id} 文件路径已更新: {len(file_paths)} 个文件")

    async def get_failed_items(self, task_id: str) -> list[TaskItem]:
        """获取失败的子任务。"""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"任务不存在: {task_id}")
        return [item for item in task.items if item.status == ItemStatus.FAILED]

    def check_size_threshold(self, size_bytes: int) -> str:
        """检查任务大小阈值。

        返回:
            'ok' - 低于告警阈值
            'warning' - 超过告警阈值但低于上限
            'exceeded' - 超过上限
        """
        warning_bytes = self._task_size_warning_gb * 1024 * 1024 * 1024
        max_bytes = self._task_size_max_gb * 1024 * 1024 * 1024

        if size_bytes > max_bytes:
            return "exceeded"
        elif size_bytes > warning_bytes:
            return "warning"
        return "ok"

    def check_disk_space(self, estimated_size: int = 0) -> bool:
        """检查磁盘空间是否充足。

        返回 True 表示空间充足，False 表示空间不足。
        """
        try:
            # 获取项目目录所在磁盘
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            usage = shutil.disk_usage(project_dir)
            free_gb = usage.free / (1024 * 1024 * 1024)
            estimated_gb = estimated_size / (1024 * 1024 * 1024)
            return free_gb >= (self._min_disk_space_gb + estimated_gb)
        except OSError:
            log.warning("无法获取磁盘使用信息")
            return True  # 无法获取时默认允许

    async def _process_queue(self):
        """处理任务队列，尝试启动排队的任务。"""
        while (
            self._task_queue and self._get_running_count() < self._max_concurrent_tasks
        ):
            next_task_id = self._task_queue.pop(0)
            task = self._tasks.get(next_task_id)
            if task and task.status == TaskStatus.QUEUED:
                from datetime import datetime

                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._save_task(task)
                log.info(f"队列任务已启动: {next_task_id}")
