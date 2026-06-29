# coding=UTF-8
"""TaskExecutor - 任务执行桥接器

桥接 TaskManager 与实际下载/上传逻辑，负责任务的实际执行和进度回调。
"""

import os
import asyncio
import logging
from typing import Optional

from module.core.task_manager import TaskManager, Task, TaskType, ItemStatus
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
    ):
        """
        Args:
            task_manager: TaskManager 实例
            file_manager: FileManager 实例
            client: Pyrogram Client 实例
            downloader: 下载器实例（可选）
            uploader: 上传器实例（可选）
        """
        self._task_manager = task_manager
        self._file_manager = file_manager
        self._client = client
        self._downloader = downloader
        self._uploader = uploader
        self._running_tasks: dict[str, asyncio.Task] = {}

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
                raise ValueError(f"未知任务类型: {task.task_type}")

            # 任务成功完成
            await self._task_manager.complete_task(task.task_id)

        except asyncio.CancelledError:
            log.info(f"任务 {task.task_id} 被取消")
            await self._task_manager.cancel_task(task.task_id)
            raise

        except Exception as e:
            log.error(f"任务 {task.task_id} 执行失败: {e}")
            await self._task_manager.fail_task(task.task_id, str(e))

    def _resolve_message_ids(self, task: Task) -> list[int]:
        """根据任务 params 中的 range_mode 解析消息 ID 列表。"""
        range_mode = task.params.get("range_mode", "id_range")

        if range_mode == "message_list":
            message_ids = task.params.get("message_ids", [])
            if not message_ids:
                raise ValueError(f"任务 {task.task_id} message_list 模式缺少 message_ids 参数")
            return message_ids

        # id_range 模式或默认
        start = task.params.get("min_id") or task.params.get("message_range_start")
        end = task.params.get("max_id") or task.params.get("message_range_end")
        if start is None:
            raise ValueError(f"下载任务 {task.task_id} 缺少消息范围参数（message_range）")
        return list(range(int(start), (int(end) if end else int(start)) + 1))

    async def _execute_download(self, task: Task) -> None:
        """执行下载任务。"""
        chat_id = task.chat_id
        message_ids = self._resolve_message_ids(task)
        filter_types = task.params.get("filter_types", [])
        downloaded_files: list[str] = []

        if not message_ids:
            raise ValueError(
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
            # 降级方案：手动逐个下载
            # 为每个消息创建子任务项并持久化到数据库
            if not task.items:
                new_items = []
                for msg_id in message_ids:
                    item_id = f"{task.task_id}_msg_{msg_id}"
                    new_items.append(
                        self._create_item(task, item_id, message_id=msg_id)
                    )
                await self._task_manager.add_items(task.task_id, new_items)

            # 逐个下载
            for item in task.items:
                if item.status in (ItemStatus.SUCCESS, ItemStatus.SKIPPED):
                    continue

                await self._task_manager.update_item_status(
                    task.task_id, item.id, ItemStatus.RUNNING
                )

                try:
                    # 下载单条消息
                    message = await self._client.get_messages(chat_id, item.source_id)
                    if message and message.media:
                        # 类型过滤：检查消息媒体类型是否匹配 filter_types
                        if filter_types:
                            media_type = self._get_media_type(message)
                            if media_type and media_type not in filter_types:
                                await self._task_manager.update_item_status(
                                    task.task_id, item.id, ItemStatus.SKIPPED
                                )
                                continue
                        # 记录成功
                        await self._task_manager.update_item_status(
                            task.task_id, item.id, ItemStatus.SUCCESS
                        )
                    else:
                        await self._task_manager.update_item_status(
                            task.task_id,
                            item.id,
                            ItemStatus.FAILED,
                            "MESSAGE_NOT_FOUND",
                        )
                except Exception as e:
                    await self._task_manager.update_item_status(
                        task.task_id, item.id, ItemStatus.FAILED, str(e)
                    )

        # 保存已下载的文件路径到任务
        if downloaded_files:
            await self._task_manager.update_file_paths(task.task_id, downloaded_files)

    async def _execute_forward(self, task: Task) -> None:
        """执行转发任务。"""
        chat_id = task.chat_id
        target_chat_id = task.params.get("target_chat_id")
        filter_types = task.params.get("filter_types", [])

        message_ids = self._resolve_message_ids(task)

        # 创建子任务项并持久化到数据库
        if not task.items:
            new_items = []
            for msg_id in message_ids:
                item_id = f"{task.task_id}_msg_{msg_id}"
                new_items.append(self._create_item(task, item_id, message_id=msg_id))
            await self._task_manager.add_items(task.task_id, new_items)

        # 逐个转发
        for item in task.items:
            if item.status in (ItemStatus.SUCCESS, ItemStatus.SKIPPED):
                continue

            await self._task_manager.update_item_status(
                task.task_id, item.id, ItemStatus.RUNNING
            )

            try:
                # 类型过滤
                if filter_types:
                    message = await self._client.get_messages(chat_id, item.source_id)
                    if message and message.media:
                        media_type = self._get_media_type(message)
                        if media_type and media_type not in filter_types:
                            await self._task_manager.update_item_status(
                                task.task_id, item.id, ItemStatus.SKIPPED
                            )
                            continue

                await self._client.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=chat_id,
                    message_id=item.source_id,
                )
                await self._task_manager.update_item_status(
                    task.task_id, item.id, ItemStatus.SUCCESS
                )
            except Exception as e:
                await self._task_manager.update_item_status(
                    task.task_id, item.id, ItemStatus.FAILED, str(e)
                )

    async def _execute_upload(self, task: Task) -> None:
        """执行上传任务。"""
        chat_id = task.chat_id
        file_paths = task.params.get("file_paths", [])

        if not file_paths:
            raise ValueError(f"任务 {task.task_id} 没有文件路径")

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
            raise ValueError(f"任务 {task.task_id} 没有有效的文件")

        # 拆分为媒体组和单文件
        groups = await self._file_manager.split_media_group(file_infos)

        item_index = 0
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

            # 上传
            for file_info in files:
                item_id = (
                    f"{task.task_id}_file_{item_index - files.index(file_info) - 1}"
                )

                await self._task_manager.update_item_status(
                    task.task_id, item_id, ItemStatus.RUNNING
                )

                try:
                    if is_album and len(files) > 1:
                        # 媒体组上传（只在第一文件时执行整组）
                        if file_info == files[0]:
                            results = await self._file_manager.upload_media_group(
                                file_infos=files,
                                chat_id=chat_id,
                                progress_callback=self._on_progress,
                                delete_after=task.params.get("delete_after_upload", True),
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
                                        res.error_msg or "UNKNOWN_ERROR",
                                    )
                            continue
                        else:
                            continue  # 跳过已处理的文件
                    else:
                        # 单文件上传
                        result = await self._file_manager.upload(
                            file_path=file_info.path,
                            chat_id=chat_id,
                            progress_callback=self._on_progress,
                            delete_after=task.params.get("delete_after_upload", True),
                        )
                        if result.success:
                            await self._task_manager.update_item_status(
                                task.task_id, item_id, ItemStatus.SUCCESS
                            )
                        else:
                            await self._task_manager.update_item_status(
                                task.task_id,
                                item_id,
                                ItemStatus.FAILED,
                                result.error_msg or "UNKNOWN_ERROR",
                            )
                except Exception as e:
                    await self._task_manager.update_item_status(
                        task.task_id, item_id, ItemStatus.FAILED, str(e)
                    )

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

        返回: "video", "photo", "document", "audio", "animation" 或 None。
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
        return None
