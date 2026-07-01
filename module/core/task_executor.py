# coding=UTF-8
"""TaskExecutor - 任务执行桥接器

桥接 TaskManager 与实际下载/上传逻辑，负责任务的实际执行和进度回调。
"""

import os
import asyncio
import logging
from typing import Optional

from module.core.config_manager import ConfigManager

from module.core.task_manager import (
    TaskManager,
    Task,
    TaskType,
    ItemStatus,
    ExecutorError,
)
from module.core.file_manager import FileManager, UploadProgress
from module.utils.path_tool import safe_scan_directory_file

log = logging.getLogger("rich")


class TaskExecutor:
    """任务执行桥接器，将 TaskManager 的任务分派给实际的执行逻辑。"""

    def __init__(
        self,
        task_manager: TaskManager,
        file_manager: FileManager,
        client: object,
        downloader: object = None,
        uploader: object = None,
        config_manager: Optional[ConfigManager] = None,
        repository_manager: Optional[object] = None,
    ):
        """
        Args:
            task_manager: TaskManager 实例
            file_manager: FileManager 实例
            client: Pyrogram Client 实例
            downloader: 下载器实例（可选）
            uploader: 上传器实例（可选）
            config_manager: ConfigManager 实例（可选，用于读取并发配置）
            repository_manager: RepositoryManager 实例（可选，用于仓库去重）
        """
        self._task_manager = task_manager
        self._file_manager = file_manager
        self._client = client
        self._downloader = downloader
        self._uploader = uploader
        self._repository_manager = repository_manager
        self._running_tasks: dict[str, asyncio.Task] = {}

        # 并发控制：从 ConfigManager 读取，默认值与 DEFAULT_RESOURCE_LIMITS 一致
        if config_manager:
            rl = config_manager.resource_limits
            dl_concurrency = rl.get("max_download_concurrency", 3)
            ul_concurrency = rl.get("max_upload_concurrency", 1)
            fwd_concurrency = rl.get("max_forward_concurrency", 1)
        else:
            dl_concurrency = 3
            ul_concurrency = 1
            fwd_concurrency = 1

        self._download_semaphore = asyncio.Semaphore(dl_concurrency)
        self._upload_semaphore = asyncio.Semaphore(ul_concurrency)
        self._forward_semaphore = asyncio.Semaphore(fwd_concurrency)

    def _should_use_repository(self) -> bool:
        """判断是否启用仓库去重。"""
        return (
            self._repository_manager is not None
            and self._repository_manager.should_use_repository()
        )

    async def _update_item_metadata(self, task_id: str, item_id: str, **kwargs) -> None:
        """更新子任务的元数据字段（file_unique_id 等）。"""
        task = self._task_manager._tasks.get(task_id)
        if not task:
            return
        for item in task.items:
            if item.id == item_id:
                for key, value in kwargs.items():
                    if hasattr(item, key):
                        setattr(item, key, value)
                await self._task_manager.update_item_status(
                    task_id, item_id, item.status
                )
                break

    async def execute_task(self, task: Task) -> None:
        """执行一个任务，根据任务类型分派到不同的执行器。

        Args:
            task: 要执行的任务
        """
        try:
            if task.task_type == TaskType.DOWNLOAD:
                await self._execute_download(task)
            elif task.task_type == TaskType.FORWARD:
                await self._execute_forward(task)
            elif task.task_type == TaskType.UPLOAD:
                await self._execute_upload(task)
            else:
                raise ExecutorError(f"未知任务类型: {task.task_type}")

            # 任务成功完成
            await self._task_manager.complete_task(task.task_id)

        except asyncio.CancelledError:
            log.info(f"任务 {task.task_id} 被取消")
            await self._task_manager.cancel_task(task.task_id)
            raise

        except Exception as e:
            log.error(f"任务 {task.task_id} 执行失败: {e}")
            await self._task_manager.fail_task(task.task_id, str(e))

    async def _resolve_message_ids(self, task: Task) -> list[int]:
        """根据任务 params 中的 range_mode 解析消息 ID 列表。

        支持的模式：
        - id_range: 根据 min_id/max_id 生成连续 ID 列表
        - multiple_ids: 直接返回 message_list 中的消息 ID
        - date_range: 通过 Telegram API 按日期范围获取消息 ID
        - all: 通过 Telegram API 遍历频道所有消息获取 ID
        """
        range_mode = task.params.get("range_mode", "id_range")

        if range_mode == "multiple_ids":
            message_ids = task.params.get("message_list") or task.params.get(
                "message_ids", []
            )
            if not message_ids:
                raise ExecutorError(
                    f"任务 {task.task_id} multiple_ids 模式缺少 message_list 参数"
                )
            # 解析消息 ID（支持纯数字和链接格式）
            return self._parse_message_id_list(message_ids)

        elif range_mode == "date_range":
            return await self._resolve_date_range_ids(task)

        elif range_mode == "all":
            return await self._resolve_all_ids(task)

        # id_range 模式（默认）
        start = task.params.get("min_id") or task.params.get("message_range_start")
        end = task.params.get("max_id") or task.params.get("message_range_end")
        if start is None:
            raise ExecutorError(
                f"任务 {task.task_id} id_range 模式缺少消息范围参数（min_id/max_id）"
            )
        return list(range(int(start), (int(end) if end else int(start)) + 1))

    async def _resolve_date_range_ids(self, task: Task) -> list[int]:
        """通过 Telegram API 按日期范围获取消息 ID 列表。

        使用 client.get_chat_history() 遍历指定日期范围内的消息，收集其 ID。
        """
        from datetime import datetime, timezone

        chat_id = task.chat_id
        start_date_str = task.params.get("start_date")
        end_date_str = task.params.get("end_date")

        if not start_date_str or not end_date_str:
            raise ExecutorError(
                f"任务 {task.task_id} date_range 模式缺少 start_date/end_date 参数"
            )

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError as e:
            raise ExecutorError(f"任务 {task.task_id} 日期格式无效: {e}")

        message_ids = []
        try:
            async for message in self._client.get_chat_history(
                chat_id,
                offset_date=end_date,
            ):
                if message.date and message.date < start_date:
                    break
                message_ids.append(message.id)
        except Exception as e:
            raise ExecutorError(f"任务 {task.task_id} 获取日期范围内消息失败: {e}")

        if not message_ids:
            log.warning(
                f"任务 {task.task_id}: 日期范围 {start_date_str} ~ {end_date_str} 内未找到消息"
            )

        return message_ids

    async def _resolve_all_ids(self, task: Task) -> list[int]:
        """通过 Telegram API 遍历频道所有消息获取 ID 列表。

        使用 client.get_chat_history() 遍历频道的完整消息历史。
        对于大频道，每10000条消息记录一次进度日志。
        """
        chat_id = task.chat_id
        message_ids = []
        count = 0

        try:
            async for message in self._client.get_chat_history(chat_id):
                message_ids.append(message.id)
                count += 1
                if count % 10000 == 0:
                    log.info(f"任务 {task.task_id}: 已获取 {count} 条消息 ID...")
        except Exception as e:
            raise ExecutorError(f"任务 {task.task_id} 获取频道所有消息失败: {e}")

        if not message_ids:
            log.warning(f"任务 {task.task_id}: 频道 {chat_id} 内未找到消息")
        else:
            log.info(
                f"任务 {task.task_id}: 频道 {chat_id} 共获取 {len(message_ids)} 条消息 ID"
            )

        return message_ids

    @staticmethod
    def _parse_message_id_list(items: list) -> list[int]:
        """解析消息 ID 列表，支持纯数字和链接格式。

        Args:
            items: 包含消息 ID 或消息链接的列表

        Returns:
            解析后的整数消息 ID 列表
        """
        import re

        ids = []
        for item in items:
            item_str = str(item).strip()
            if not item_str:
                continue
            # 支持格式: https://t.me/channel/123 或 t.me/channel/123 或 纯数字
            match = re.search(r"/(\d+)$", item_str)
            if match:
                ids.append(int(match.group(1)))
            elif item_str.isdigit():
                ids.append(int(item_str))
        return ids

    async def _execute_download(self, task: Task) -> None:
        """执行下载任务。"""
        chat_id = task.chat_id
        message_ids = await self._resolve_message_ids(task)
        filter_types = task.params.get("filter_types", [])
        downloaded_files: list[str] = []

        if not message_ids:
            raise ExecutorError(
                f"下载任务 {task.task_id} 缺少消息范围参数（message_range）"
            )

        # 如果已有下载器，调用其下载方法
        if self._downloader:
            downloaded_files = await self._downloader.download_range(
                chat_id=chat_id,
                start_id=message_ids[0],
                end_id=message_ids[-1],
                task_id=task.task_id,
                progress_callback=self._on_item_progress,
            )
        else:
            # 降级方案：手动下载（并发控制）
            if not task.items:
                new_items = []
                for msg_id in message_ids:
                    item_id = f"{task.task_id}_msg_{msg_id}"
                    new_items.append(
                        self._create_item(task, item_id, message_id=msg_id)
                    )
                await self._task_manager.add_items(task.task_id, new_items)

            # 并发下载
            async def _download_one(item):
                if item.status in (ItemStatus.SUCCESS, ItemStatus.SKIPPED):
                    return
                async with self._download_semaphore:
                    await self._task_manager.update_item_status(
                        task.task_id, item.id, ItemStatus.RUNNING
                    )
                    try:
                        message = await self._client.get_messages(
                            chat_id, item.source_id
                        )
                        if message and message.media:
                            if filter_types:
                                media_type = self._get_media_type(message)
                                if media_type and media_type not in filter_types:
                                    await self._task_manager.update_item_status(
                                        task.task_id, item.id, ItemStatus.SKIPPED
                                    )
                                    return

                            # 提取 file_unique_id 和 telegram_file_id
                            file_unique_id = self._extract_file_unique_id(message)
                            telegram_file_id = self._extract_telegram_file_id(message)

                            # L2 去重检查
                            if self._should_use_repository() and file_unique_id:
                                dedup = self._repository_manager.check_dedup(
                                    source_chat_id=chat_id,
                                    source_message_id=item.source_id,
                                    file_unique_id=file_unique_id,
                                )
                                if dedup:
                                    await self._task_manager.update_item_status(
                                        task.task_id,
                                        item.id,
                                        ItemStatus.SKIPPED,
                                        error_code="DUPLICATE_IN_REPOSITORY",
                                        error_message="文件已在仓库中存在，跳过下载",
                                    )
                                    return

                            await self._task_manager.update_item_status(
                                task.task_id,
                                item.id,
                                ItemStatus.SUCCESS,
                                file_unique_id=file_unique_id,
                                telegram_file_id=telegram_file_id,
                            )
                        else:
                            await self._task_manager.update_item_status(
                                task.task_id,
                                item.id,
                                ItemStatus.FAILED,
                                error_code="MESSAGE_NOT_FOUND",
                                error_message="消息未找到或不含媒体文件",
                            )
                    except Exception as e:
                        await self._task_manager.update_item_status(
                            task.task_id,
                            item.id,
                            ItemStatus.FAILED,
                            error_code="EXECUTION_ERROR",
                            error_message=str(e),
                        )

            await asyncio.gather(*[_download_one(item) for item in task.items])

            # 下载完成后计算 SHA256 并执行 L3 去重
            if self._should_use_repository():
                for item in task.items:
                    if item.status == ItemStatus.SUCCESS and item.file_path:
                        file_sha256 = self._repository_manager.compute_content_hash(
                            item.file_path
                        )
                        self._repository_manager.check_dedup(
                            source_chat_id=chat_id,
                            source_message_id=item.source_id,
                            content_hash=file_sha256,
                        )
                        await self._task_manager.update_item_status(
                            task.task_id,
                            item.id,
                            item.status,
                            file_sha256=file_sha256,
                        )

        # 保存已下载的文件路径到任务
        if downloaded_files:
            await self._task_manager.update_file_paths(task.task_id, downloaded_files)

    async def _execute_forward(self, task: Task) -> None:
        """执行转发任务。"""
        chat_id = task.chat_id
        target_chat_id = task.params.get("target_chat_id")
        filter_types = task.params.get("filter_types", [])

        message_ids = await self._resolve_message_ids(task)

        # 创建子任务项并持久化到数据库
        if not task.items:
            new_items = []
            for msg_id in message_ids:
                item_id = f"{task.task_id}_msg_{msg_id}"
                new_items.append(self._create_item(task, item_id, message_id=msg_id))
            await self._task_manager.add_items(task.task_id, new_items)

        # 并发转发
        async def _forward_one(item):
            if item.status in (ItemStatus.SUCCESS, ItemStatus.SKIPPED):
                return
            async with self._forward_semaphore:
                await self._task_manager.update_item_status(
                    task.task_id, item.id, ItemStatus.RUNNING
                )
                try:
                    if filter_types:
                        message = await self._client.get_messages(
                            chat_id, item.source_id
                        )
                        if message and message.media:
                            media_type = self._get_media_type(message)
                            if media_type and media_type not in filter_types:
                                await self._task_manager.update_item_status(
                                    task.task_id, item.id, ItemStatus.SKIPPED
                                )
                                return

                    result_message = await self._client.copy_message(
                        chat_id=target_chat_id,
                        from_chat_id=chat_id,
                        message_id=item.source_id,
                    )
                    await self._task_manager.update_item_status(
                        task.task_id,
                        item.id,
                        ItemStatus.SUCCESS,
                        target_id=target_chat_id,
                        uploaded_message_id=result_message.id,
                    )
                except Exception as e:
                    await self._task_manager.update_item_status(
                        task.task_id,
                        item.id,
                        ItemStatus.FAILED,
                        error_code="EXECUTION_ERROR",
                        error_message=str(e),
                    )

        await asyncio.gather(*[_forward_one(item) for item in task.items])

    async def _execute_upload(self, task: Task) -> None:
        """执行上传任务。"""
        chat_id = task.chat_id
        file_paths = task.params.get("file_paths", [])

        if not file_paths:
            raise ExecutorError(f"任务 {task.task_id} 没有文件路径")

        # 收集所有文件信息
        file_infos = []
        for file_path in file_paths:
            if not file_path:
                continue

            if os.path.isdir(file_path):
                # 扫描目录
                upload_files = safe_scan_directory_file(file_path)
                for filename in upload_files:
                    full_path = os.path.join(file_path, filename)
                    try:
                        file_info = await self._file_manager.get_file_info(full_path)
                        file_infos.append(file_info)
                    except Exception as e:
                        log.warning(f"获取文件信息失败: {full_path}, {e}")
            else:
                try:
                    file_info = await self._file_manager.get_file_info(file_path)
                    file_infos.append(file_info)
                except Exception as e:
                    log.warning(f"获取文件信息失败: {file_path}, {e}")

        if not file_infos:
            raise ExecutorError(f"任务 {task.task_id} 没有有效的文件")

        # 拆分为媒体组和单文件
        groups = await self._file_manager.split_media_group(file_infos)

        item_index = 0
        # 收集需要并发上传的单文件
        single_file_uploads: list[tuple] = []

        for group in groups:
            is_album = group.get("is_album", False)
            files = group.get("files", [])

            # 创建子任务项并持久化到数据库
            new_items = []
            for file_info in files:
                item_id = f"{task.task_id}_file_{item_index}"
                new_items.append(
                    self._create_item(
                        task, item_id, message_id=None, file_path=file_info.path
                    )
                )
                item_index += 1
            await self._task_manager.add_items(task.task_id, new_items)

            if is_album and len(files) > 1:
                # 媒体组：保持顺序整组上传
                for file_info in files:
                    item_id = (
                        f"{task.task_id}_file_{item_index - files.index(file_info) - 1}"
                    )
                    await self._task_manager.update_item_status(
                        task.task_id, item_id, ItemStatus.RUNNING
                    )
                    try:
                        if file_info == files[0]:
                            results = await self._file_manager.upload_media_group(
                                file_infos=files,
                                chat_id=chat_id,
                                progress_callback=self._on_progress,
                                delete_after=task.params.get(
                                    "delete_after_upload", True
                                ),
                            )
                            for i, res in enumerate(results):
                                item_id = (
                                    f"{task.task_id}_file_{item_index - len(files) + i}"
                                )
                                if res.success:
                                    await self._task_manager.update_item_status(
                                        task.task_id, item_id, ItemStatus.SUCCESS
                                    )
                                else:
                                    await self._task_manager.update_item_status(
                                        task.task_id,
                                        item_id,
                                        ItemStatus.FAILED,
                                        error_code="UPLOAD_ERROR",
                                        error_message=res.error_msg or "UNKNOWN_ERROR",
                                    )
                    except Exception as e:
                        await self._task_manager.update_item_status(
                            task.task_id,
                            item_id,
                            ItemStatus.FAILED,
                            error_code="EXECUTION_ERROR",
                            error_message=str(e),
                        )
            else:
                # 单文件：收集后并发上传
                for file_info in files:
                    item_id = (
                        f"{task.task_id}_file_{item_index - files.index(file_info) - 1}"
                    )
                    single_file_uploads.append((file_info, item_id))

        # 单文件并发上传
        async def _upload_one(file_info, item_id):
            async with self._upload_semaphore:
                await self._task_manager.update_item_status(
                    task.task_id, item_id, ItemStatus.RUNNING
                )
                try:
                    # L3 去重检查
                    if self._should_use_repository():
                        file_sha256 = self._repository_manager.compute_content_hash(
                            file_info.path
                        )
                        dedup = self._repository_manager.check_dedup(
                            content_hash=file_sha256,
                        )
                        if dedup:
                            target_msg_id = (
                                await self._repository_manager.distribute_to_target(
                                    client=self._client,
                                    file_unique_id=dedup.file_unique_id,
                                    target_chat_id=chat_id,
                                )
                            )
                            if target_msg_id:
                                await self._task_manager.update_item_status(
                                    task.task_id,
                                    item_id,
                                    ItemStatus.SUCCESS,
                                    target_id=chat_id,
                                    uploaded_message_id=target_msg_id,
                                    file_sha256=file_sha256,
                                )
                                return

                    result = await self._file_manager.upload(
                        file_path=file_info.path,
                        chat_id=chat_id,
                        progress_callback=self._on_progress,
                        delete_after=task.params.get("delete_after_upload", True),
                    )
                    if result.success:
                        await self._task_manager.update_item_status(
                            task.task_id,
                            item_id,
                            ItemStatus.SUCCESS,
                            target_id=chat_id,
                        )
                    else:
                        await self._task_manager.update_item_status(
                            task.task_id,
                            item_id,
                            ItemStatus.FAILED,
                            error_code="UPLOAD_ERROR",
                            error_message=result.error_msg or "UNKNOWN_ERROR",
                        )
                except Exception as e:
                    await self._task_manager.update_item_status(
                        task.task_id,
                        item_id,
                        ItemStatus.FAILED,
                        error_code="EXECUTION_ERROR",
                        error_message=str(e),
                    )

        if single_file_uploads:
            await asyncio.gather(*[_upload_one(f, i) for f, i in single_file_uploads])

    async def _on_item_progress(
        self,
        task_id: str,
        item_id: str,
        status: ItemStatus,
        error: Optional[str] = None,
    ) -> None:
        """子任务进度回调。"""
        try:
            await self._task_manager.update_item_status(task_id, item_id, status, error)
        except Exception as e:
            log.error(f"更新子任务状态失败: {e}")

    async def _on_progress(self, progress: UploadProgress) -> None:
        """上传进度回调（供 FileManager 使用）。"""
        log.debug(
            f"上传进度: {progress.file_path} - "
            f"{progress.percentage:.1f}% ({progress.current}/{progress.total})"
        )

    @staticmethod
    def _create_item(
        task: Task,
        item_id: str,
        message_id: Optional[int] = None,
        file_path: Optional[str] = None,
    ) -> object:
        """创建子任务项。"""
        from datetime import datetime
        from module.core.task_manager import TaskItem

        now = datetime.now().isoformat()
        return TaskItem(
            id=item_id,
            task_id=task.task_id,
            source_id=message_id or file_path,
            file_path=file_path,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _get_media_type(message) -> Optional[str]:
        """获取消息的媒体类型字符串。

        返回: "video", "photo", "document", "audio", "animation", "voice",
              "video_note" 或 None。
        """
        if not message or not message.media:
            return None
        media = message.media
        if hasattr(media, "video") and media.video:
            return "video"
        if hasattr(media, "photo") and media.photo:
            return "photo"
        if hasattr(media, "document") and media.document:
            return "document"
        if hasattr(media, "audio") and media.audio:
            return "audio"
        if hasattr(media, "animation") and media.animation:
            return "animation"
        if hasattr(media, "voice") and media.voice:
            return "voice"
        if hasattr(media, "video_note") and media.video_note:
            return "video_note"
        return None

    @staticmethod
    def _extract_file_unique_id(message) -> Optional[str]:
        """从消息的媒体对象中提取 file_unique_id。"""
        if not message or not message.media:
            return None
        media = message.media
        if hasattr(media, "video") and media.video:
            return getattr(media.video, "file_unique_id", None)
        if hasattr(media, "photo") and media.photo:
            return getattr(media.photo, "file_unique_id", None)
        if hasattr(media, "document") and media.document:
            return getattr(media.document, "file_unique_id", None)
        if hasattr(media, "audio") and media.audio:
            return getattr(media.audio, "file_unique_id", None)
        if hasattr(media, "animation") and media.animation:
            return getattr(media.animation, "file_unique_id", None)
        if hasattr(media, "voice") and media.voice:
            return getattr(media.voice, "file_unique_id", None)
        if hasattr(media, "video_note") and media.video_note:
            return getattr(media.video_note, "file_unique_id", None)
        return getattr(media, "file_unique_id", None)

    @staticmethod
    def _extract_telegram_file_id(message) -> Optional[str]:
        """从消息的媒体对象中提取 file_id。"""
        if not message or not message.media:
            return None
        media = message.media
        if hasattr(media, "video") and media.video:
            return getattr(media.video, "file_id", None)
        if hasattr(media, "photo") and media.photo:
            return getattr(media.photo, "file_id", None)
        if hasattr(media, "document") and media.document:
            return getattr(media.document, "file_id", None)
        if hasattr(media, "audio") and media.audio:
            return getattr(media.audio, "file_id", None)
        if hasattr(media, "animation") and media.animation:
            return getattr(media.animation, "file_id", None)
        if hasattr(media, "voice") and media.voice:
            return getattr(media.voice, "file_id", None)
        if hasattr(media, "video_note") and media.video_note:
            return getattr(media.video_note, "file_id", None)
        return getattr(media, "file_id", None)
