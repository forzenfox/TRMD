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
from typing import Optional
from dataclasses import dataclass, field

log = logging.getLogger('rich')


# ============================================================
# 枚举定义
# ============================================================

class TaskType(Enum):
    """任务类型。"""
    DOWNLOAD = 'download'
    FORWARD = 'forward'
    UPLOAD = 'upload'


class TaskStatus(Enum):
    """任务状态。"""
    PENDING = 'pending'
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class ItemStatus(Enum):
    """子任务状态。"""
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    CANCELLED = 'cancelled'


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TaskItem:
    """子任务项，对应一条消息或一个本地文件。"""
    item_id: str
    message_id: Optional[int] = None
    status: ItemStatus = ItemStatus.PENDING
    file_size: int = 0
    error_reason: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def mark_success(self):
        """标记为成功。"""
        self.status = ItemStatus.SUCCESS

    def mark_failed(self, reason: str):
        """标记为失败。"""
        self.status = ItemStatus.FAILED
        self.error_reason = reason
        self.retry_count += 1

    def mark_skipped(self, reason: str):
        """标记为跳过。"""
        self.status = ItemStatus.SKIPPED
        self.error_reason = reason

    def can_retry(self) -> bool:
        """判断是否可重试。"""
        if self.retry_count >= self.max_retries:
            return False
        # 不可重试的错误类型
        non_retryable = [
            'MESSAGE_ID_INVALID',
            'CHAT_FORBIDDEN',
            'USER_BANNED',
            'CHANNEL_PRIVATE',
        ]
        if self.error_reason and any(
            nr in self.error_reason for nr in non_retryable
        ):
            return False
        return True


# 不可重试错误的判定函数
_NON_RETRYABLE_KEYWORDS = [
    'MESSAGE_ID_INVALID',
    'CHAT_FORBIDDEN',
    'USER_BANNED',
    'CHANNEL_PRIVATE',
]


@dataclass
class Task:
    """任务，对应一个下载/转发/上传操作。"""
    task_id: str
    task_type: TaskType
    chat_id: int
    status: TaskStatus = TaskStatus.PENDING
    target_chat_id: Optional[int] = None
    message_range: Optional[tuple] = None
    file_paths: list = field(default_factory=list)
    items: list = field(default_factory=list)
    estimated_size: int = 0
    total_size: int = 0
    retry_count: int = 0
    max_retries: int = 3
    delete_after_upload: bool = True
    error_reason: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def success_count(self) -> int:
        """成功子任务数。"""
        return sum(1 for item in self.items if item.status == ItemStatus.SUCCESS)

    @property
    def failed_count(self) -> int:
        """失败子任务数。"""
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
        TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
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
        self._db_path = db_path or ':memory:'
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

    def _init_db(self):
        """初始化数据库表。"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                target_chat_id INTEGER,
                message_range_start INTEGER,
                message_range_end INTEGER,
                file_paths TEXT,
                status TEXT NOT NULL,
                estimated_size INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                delete_after_upload INTEGER DEFAULT 1,
                error_reason TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                message_id INTEGER,
                status TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                error_reason TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        ''')
        conn.commit()
        conn.close()

    def _load_tasks_from_db(self):
        """从数据库加载未完成的任务。"""
        if self._db_path == ':memory:':
            return
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks')
        rows = cursor.fetchall()

        for row in rows:
            task = self._row_to_task(row)
            self._tasks[task.task_id] = task
            # 加载子任务
            cursor.execute('SELECT * FROM task_items WHERE task_id = ?', (task.task_id,))
            item_rows = cursor.fetchall()
            for item_row in item_rows:
                task.items.append(self._row_to_item(item_row))

        conn.close()

    def _row_to_task(self, row) -> Task:
        """将数据库行转换为 Task。"""
        import json
        file_paths = []
        if row[6]:
            try:
                file_paths = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                file_paths = []

        message_range = None
        if row[4] is not None and row[5] is not None:
            message_range = (row[4], row[5])

        return Task(
            task_id=row[0],
            task_type=TaskType(row[1]),
            chat_id=row[2],
            target_chat_id=row[3],
            message_range=message_range,
            file_paths=file_paths,
            status=TaskStatus(row[7]),
            estimated_size=row[8] or 0,
            total_size=row[9] or 0,
            retry_count=row[10] or 0,
            max_retries=row[11] or 3,
            delete_after_upload=bool(row[12]),
            error_reason=row[13],
            created_at=row[14],
            started_at=row[15],
            completed_at=row[16],
        )

    def _row_to_item(self, row) -> TaskItem:
        """将数据库行转换为 TaskItem。"""
        return TaskItem(
            item_id=row[2],
            message_id=row[3],
            status=ItemStatus(row[4]),
            file_size=row[5] or 0,
            error_reason=row[6],
            retry_count=row[7] or 0,
            max_retries=row[8] or 3,
        )

    def _save_task(self, task: Task):
        """保存任务到数据库。"""
        if self._db_path == ':memory:':
            return
        import json
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        file_paths_json = json.dumps(task.file_paths) if task.file_paths else None
        msg_start = task.message_range[0] if task.message_range else None
        msg_end = task.message_range[1] if task.message_range else None

        cursor.execute('''
            INSERT OR REPLACE INTO tasks
            (task_id, task_type, chat_id, target_chat_id, message_range_start,
             message_range_end, file_paths, status, estimated_size, total_size,
             retry_count, max_retries, delete_after_upload, error_reason,
             created_at, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.task_id,
            task.task_type.value,
            task.chat_id,
            task.target_chat_id,
            msg_start,
            msg_end,
            file_paths_json,
            task.status.value,
            task.estimated_size,
            task.total_size,
            task.retry_count,
            task.max_retries,
            int(task.delete_after_upload),
            task.error_reason,
            task.created_at,
            task.started_at,
            task.completed_at,
        ))
        conn.commit()
        conn.close()

    def _save_item(self, task_id: str, item: TaskItem):
        """保存子任务到数据库。"""
        if self._db_path == ':memory:':
            return
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO task_items
            (task_id, item_id, message_id, status, file_size, error_reason, retry_count, max_retries)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id,
            item.item_id,
            item.message_id,
            item.status.value,
            item.file_size,
            item.error_reason,
            item.retry_count,
            item.max_retries,
        ))
        conn.commit()
        conn.close()

    def _validate_transition(self, current: TaskStatus, target: TaskStatus):
        """验证状态转换是否合法。"""
        allowed = self.VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransition(
                f'无效状态转换: {current.value} → {target.value}'
            )

    def _get_running_count(self) -> int:
        """获取当前正在运行的任务数。"""
        return sum(
            1 for task in self._tasks.values()
            if task.status == TaskStatus.RUNNING
        )

    # ============================================================
    # 公开接口
    # ============================================================

    async def create_task(
        self,
        task_type: TaskType,
        chat_id: int,
        target_chat_id: Optional[int] = None,
        message_range: Optional[tuple] = None,
        file_paths: Optional[list] = None,
        estimated_size: int = 0,
        delete_after_upload: bool = True,
    ) -> Task:
        """创建任务。"""
        from datetime import datetime
        task_id = f'task_{uuid.uuid4().hex[:8]}'
        task = Task(
            task_id=task_id,
            task_type=task_type,
            chat_id=chat_id,
            target_chat_id=target_chat_id,
            message_range=message_range,
            file_paths=file_paths or [],
            estimated_size=estimated_size,
            delete_after_upload=delete_after_upload,
            max_retries=self._max_retries,
            created_at=datetime.now().isoformat(),
        )
        async with self._lock:
            self._tasks[task_id] = task
            self._save_task(task)
        log.info(f'任务已创建: {task_id} ({task_type.value})')
        return task

    async def start_task(self, task_id: str) -> bool:
        """启动任务。"""
        from datetime import datetime
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')

            running_count = self._get_running_count()
            if running_count >= self._max_concurrent_tasks:
                # 进入队列
                self._validate_transition(task.status, TaskStatus.QUEUED)
                task.status = TaskStatus.QUEUED
                self._task_queue.append(task_id)
                self._save_task(task)
                log.info(f'任务进入队列: {task_id}')
                return False
            else:
                # 直接运行
                self._validate_transition(task.status, TaskStatus.RUNNING)
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._save_task(task)
                log.info(f'任务开始执行: {task_id}')
                return True

    async def complete_task(self, task_id: str):
        """完成任务。"""
        from datetime import datetime
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')

            self._validate_transition(task.status, TaskStatus.COMPLETED)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            self._save_task(task)
            log.info(f'任务已完成: {task_id}')

            # 尝试启动队列中的下一个任务
            await self._process_queue()

    async def fail_task(self, task_id: str, reason: str):
        """标记任务失败。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')

            self._validate_transition(task.status, TaskStatus.FAILED)
            task.status = TaskStatus.FAILED
            task.error_reason = reason
            self._save_task(task)
            log.warning(f'任务失败: {task_id} - {reason}')

            # 尝试启动队列中的下一个任务
            await self._process_queue()

    async def cancel_task(self, task_id: str):
        """取消任务。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')

            self._validate_transition(task.status, TaskStatus.CANCELLED)
            task.status = TaskStatus.CANCELLED
            self._save_task(task)
            log.info(f'任务已取消: {task_id}')

            # 从队列中移除
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)

    async def retry_task(self, task_id: str):
        """重试任务。"""
        from datetime import datetime
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')

            self._validate_transition(task.status, TaskStatus.PENDING)
            task.status = TaskStatus.PENDING
            task.retry_count += 1
            task.error_reason = None
            task.started_at = None
            task.completed_at = None

            # 重置失败的子任务
            for item in task.items:
                if item.status == ItemStatus.FAILED and item.can_retry():
                    item.status = ItemStatus.PENDING
                    item.error_reason = None
                    self._save_item(task_id, item)

            self._save_task(task)
            log.info(f'任务重试: {task_id} (第 {task.retry_count} 次)')

    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务。"""
        return self._tasks.get(task_id)

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        """获取任务列表。"""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    async def add_items(self, task_id: str, items: list[TaskItem]):
        """添加子任务项。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')
            task.items.extend(items)
            for item in items:
                self._save_item(task_id, item)
            self._save_task(task)

    async def update_item_status(
        self, task_id: str, item_id: str, status: ItemStatus,
        error_reason: Optional[str] = None
    ):
        """更新子任务状态。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f'任务不存在: {task_id}')
            for item in task.items:
                if item.item_id == item_id:
                    item.status = status
                    if error_reason:
                        item.error_reason = error_reason
                    self._save_item(task_id, item)
                    self._save_task(task)
                    break

    async def get_failed_items(self, task_id: str) -> list[TaskItem]:
        """获取失败的子任务。"""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f'任务不存在: {task_id}')
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
            return 'exceeded'
        elif size_bytes > warning_bytes:
            return 'warning'
        return 'ok'

    def check_disk_space(self) -> bool:
        """检查磁盘空间是否充足。

        返回 True 表示空间充足，False 表示空间不足。
        """
        try:
            # 获取项目目录所在磁盘
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            usage = shutil.disk_usage(project_dir)
            free_gb = usage.free / (1024 * 1024 * 1024)
            return free_gb >= self._min_disk_space_gb
        except OSError:
            log.warning('无法获取磁盘使用信息')
            return True  # 无法获取时默认允许

    async def _process_queue(self):
        """处理任务队列，尝试启动排队的任务。"""
        while self._task_queue and self._get_running_count() < self._max_concurrent_tasks:
            next_task_id = self._task_queue.pop(0)
            task = self._tasks.get(next_task_id)
            if task and task.status == TaskStatus.QUEUED:
                from datetime import datetime
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._save_task(task)
                log.info(f'队列任务已启动: {next_task_id}')
