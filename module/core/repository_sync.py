# coding=UTF-8
"""
RepositorySync 模块 - 仓库频道定时同步器

职责：
- 定时增量同步仓库频道消息到数据库
- 追踪上次同步位置（最大 repository_message_id）
- 查漏补缺，用于程序崩溃或数据不一致时的恢复
"""

import asyncio
import logging

from module.core.repository_db import (
    RepositoryDB,
    RepositoryFile,
)

logger = logging.getLogger(__name__)


class RepositorySync:
    """仓库频道定时同步器（可选功能，用于查漏补缺）。"""

    def __init__(self, repository_db: RepositoryDB, config_manager) -> None:
        """
        初始化仓库同步器。

        Args:
            repository_db: RepositoryDB 实例
            config_manager: ConfigManager 实例
        """
        self._db = repository_db
        self._config_manager = config_manager
        self._sync_task: asyncio.Task | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """同步任务是否正在运行。"""
        return self._running

    def start(self) -> None:
        """启动定时同步任务。"""
        repo_config = self._config_manager.get_repository_config()
        if not repo_config.get("auto_sync_enabled", False):
            logger.info("仓库自动同步未启用")
            return

        if self._running:
            logger.warning("仓库同步任务已在运行")
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("仓库定时同步已启动")

    def stop(self) -> None:
        """停止定时同步任务。"""
        self._running = False
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        self._sync_task = None
        logger.info("仓库定时同步已停止")

    async def _sync_loop(self) -> None:
        """同步主循环。"""
        repo_config = self._config_manager.get_repository_config()
        interval_minutes = repo_config.get("auto_sync_interval_minutes", 60)
        interval_seconds = interval_minutes * 60

        while self._running:
            try:
                await self.incremental_sync()
            except Exception as e:
                logger.error(f"仓库同步出错: {e}")

            await asyncio.sleep(interval_seconds)

    async def incremental_sync(self, client=None) -> int:
        """
        增量同步：仅扫描上次同步后的新消息。

        Args:
            client: Pyrogram User Client（需要外部传入）

        Returns:
            新增的记录数
        """
        if not client:
            logger.error("同步需要 Pyrogram Client")
            return 0

        repo_config = self._config_manager.get_repository_config()
        chat_id = repo_config.get("chat_id")
        if not chat_id:
            logger.error("仓库频道 ID 未配置")
            return 0

        # 获取上次同步的最大 message_id
        last_message_id = self._get_last_synced_message_id()

        new_count = 0

        try:
            async for message in client.get_chat_history(
                chat_id=chat_id,
                offset_id=last_message_id if last_message_id else 0,
                reverse=False,
            ):
                # 检查是否已存在
                if self._exists_in_db(message):
                    continue

                # 写入数据表
                if self._insert_file_record(message):
                    new_count += 1

        except Exception as e:
            logger.error(f"增量同步失败: {e}")

        if new_count > 0:
            logger.info(f"增量同步完成，新增 {new_count} 条记录")
        else:
            logger.debug("增量同步完成，无新记录")

        return new_count

    def _get_last_synced_message_id(self) -> int | None:
        """获取上次同步的最大 repository_message_id。"""
        try:
            with self._db._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT MAX(repository_message_id) FROM repository_files"
                )
                row = cursor.fetchone()
                return row[0] if row and row[0] else None
        except Exception as e:
            logger.error(f"获取上次同步位置失败: {e}")
            return None

    def _exists_in_db(self, message) -> bool:
        """
        检查消息是否已存在于数据库。

        通过 repository_chat_id + repository_message_id 组合判断。

        Args:
            message: Pyrogram Message 对象

        Returns:
            是否已存在
        """
        try:
            with self._db._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM repository_files "
                    "WHERE repository_chat_id = ? AND repository_message_id = ?",
                    (message.chat.id, message.id),
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    def _insert_file_record(self, message) -> bool:
        """
        从消息中提取文件信息并写入数据库。

        支持的媒体类型：photo、video、document、audio、animation。
        同步时不计算 content_hash，仅记录元数据。

        Args:
            message: Pyrogram Message 对象

        Returns:
            是否成功写入
        """
        media = None
        file_type = None

        if message.photo:
            media = message.photo
            file_type = "photo"
        elif message.video:
            media = message.video
            file_type = "video"
        elif message.document:
            media = message.document
            file_type = "document"
        elif message.audio:
            media = message.audio
            file_type = "audio"
        elif message.animation:
            media = message.animation
            file_type = "animation"
        else:
            return False

        try:
            file_record = RepositoryFile(
                id=None,
                file_unique_id=media.file_unique_id,
                file_id=media.file_id,
                content_hash=None,  # 同步时不计算哈希
                file_size=media.file_size or 0,
                file_type=file_type,
                mime_type=getattr(media, "mime_type", None),
                file_name=getattr(media, "file_name", None),
                repository_chat_id=message.chat.id,
                repository_message_id=message.id,
                created_at=None,
                updated_at=None,
                status="active",
            )
            self._db.insert_file_record(file_record)
            return True
        except Exception as e:
            logger.error(f"同步写入记录失败: {e}")
            return False
