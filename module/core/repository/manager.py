# coding=UTF-8
"""
RepositoryManager 模块 - 仓库频道编排器

职责：
- 判断是否启用仓库模式
- 三级去重检查（source 定位 / file_unique_id / 内容哈希）
- 上传成功回调：写入仓库记录
- 内容哈希计算
- 分发到目标频道（copy_message -> file_id_send -> 重新下载上传降级）
- 记录分发日志

注意：本类不直接操作文件和 Telegram API，而是委托 FileManager/Uploader 执行操作，
      使用 RepositoryDB 进行数据访问。
"""

import asyncio
import hashlib
import logging

from module.core.repository.db import (
    RepositoryDB,
    RepositoryFile,
    RepositorySource,
    FileDistribution,
)

logger = logging.getLogger(__name__)


# ==================== 异常类型 ====================


class RepositoryError(Exception):
    """仓库模式基础异常。"""

    pass


class RepositoryConfigError(RepositoryError):
    """仓库配置错误。"""

    pass


# ==================== RepositoryManager ====================


class RepositoryManager:
    """仓库频道编排器（不直接操作文件和 Telegram API）。"""

    def __init__(self, repository_db: RepositoryDB, config_manager) -> None:
        """
        初始化仓库频道编排器。

        Args:
            repository_db: RepositoryDB 实例
            config_manager: ConfigManager 实例
        """
        self._db = repository_db
        self._config_manager = config_manager
        self._lock = asyncio.Lock()

    # --- 配置相关 ---

    def should_use_repository(self) -> bool:
        """判断是否应使用仓库模式。

        Returns:
            当 repository.enabled 为 True 且 chat_id 非空时返回 True
        """
        repo_config = self._config_manager.get_repository_config()
        enabled = repo_config.get("enabled", False)
        chat_id = repo_config.get("chat_id", "")
        return bool(enabled and chat_id)

    def get_repository_chat_id(self) -> str | None:
        """获取仓库频道 ID。

        Returns:
            仓库频道 ID 字符串，未配置时返回 None
        """
        repo_config = self._config_manager.get_repository_config()
        chat_id = repo_config.get("chat_id", "")
        return chat_id if chat_id else None

    # --- 去重检查 ---

    def check_dedup(
        self,
        source_chat_id: int,
        source_message_id: int,
        file_unique_id: str | None = None,
        content_hash: str | None = None,
    ) -> RepositoryFile | None:
        """
        三级去重检查。

        Level 1: source 定位（source_chat_id + source_message_id）
        Level 2: file_unique_id 去重
        Level 3: 内容哈希去重

        Args:
            source_chat_id: 源频道 ID
            source_message_id: 源消息 ID
            file_unique_id: 文件唯一标识（Level 2）
            content_hash: 内容哈希（Level 3）

        Returns:
            已存在的文件记录，或 None（未命中去重）
        """
        # Level 1: source 定位
        result = self._db.get_file_by_source(source_chat_id, source_message_id)
        if result:
            logger.debug(f"L1 去重命中: source={source_chat_id}/{source_message_id}")
            return result

        # Level 2: file_unique_id 去重
        if file_unique_id:
            result = self._db.get_file_by_unique_id(file_unique_id)
            if result:
                logger.debug(f"L2 去重命中: file_unique_id={file_unique_id}")
                return result

        # Level 3: 内容哈希去重
        if content_hash:
            result = self._db.get_file_by_content_hash(content_hash)
            if result:
                logger.debug(f"L3 去重命中: content_hash={content_hash}")
                return result

        return None

    # --- 上传成功回调 ---

    async def on_upload_success(
        self,
        message,  # Pyrogram Message object
        source_chat_id: int,
        source_message_id: int,
        content_hash: str | None = None,
    ) -> None:
        """
        上传成功回调：写入仓库记录。

        从上传后的 Pyrogram Message 中提取媒体信息，构建 RepositoryFile 和
        RepositorySource 记录并写入数据库。

        Args:
            message: 上传后的 Pyrogram Message 对象
            source_chat_id: 源频道 ID
            source_message_id: 源消息 ID
            content_hash: 内容哈希
        """
        # 从消息中提取媒体信息
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
            logger.warning(f"消息 {message.id} 不包含可识别的媒体文件")
            return

        file_record = RepositoryFile(
            id=None,
            file_unique_id=media.file_unique_id,
            file_id=media.file_id,
            content_hash=content_hash,
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

        source_record = RepositorySource(
            id=None,
            file_unique_id=media.file_unique_id,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            created_at=None,
        )

        async with self._lock:
            try:
                self._db.insert_file_record(file_record)
                self._db.insert_source_mapping(source_record)
                logger.info(
                    f"仓库记录已写入: file_unique_id={media.file_unique_id}, "
                    f"source={source_chat_id}/{source_message_id}"
                )
            except Exception as e:
                logger.error(f"仓库记录写入失败: {e}")

    async def on_upload_success_batch(
        self,
        messages: list,
        source_chat_id: int,
        source_message_ids: list[int] | None = None,
        source_message_id: int | None = None,
        content_hashes: list[str] | None = None,
    ) -> None:
        """批量写入仓库记录（媒体组场景）。

        为媒体组中每条消息分别调用 on_upload_success，写入独立的
        RepositoryFile 和 RepositorySource 记录。

        Args:
            messages: Pyrogram Message 列表（媒体组返回的消息列表）
            source_chat_id: 源频道 ID
            source_message_ids: 每条消息对应的源消息 ID 列表（与 messages 一一对应）
            source_message_id: 源消息 ID（同组文件共享，向后兼容，优先级低于 source_message_ids）
            content_hashes: 可选，与 messages 一一对应的内容哈希列表
        """
        for i, message in enumerate(messages):
            hash_val = (
                content_hashes[i]
                if content_hashes and i < len(content_hashes)
                else None
            )
            # 优先使用 source_message_ids（每个文件独立的来源），否则回退到 source_message_id
            if source_message_ids and i < len(source_message_ids):
                msg_id = source_message_ids[i]
            elif source_message_id is not None:
                msg_id = source_message_id
            else:
                msg_id = 0
            await self.on_upload_success(
                message=message,
                source_chat_id=source_chat_id,
                source_message_id=msg_id,
                content_hash=hash_val,
            )

    # --- 内容哈希计算 ---

    @staticmethod
    def compute_content_hash(file_path: str) -> str:
        """计算文件内容的 SHA256 哈希。

        Args:
            file_path: 本地文件绝对路径

        Returns:
            SHA256 哈希的十六进制字符串
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # --- 分发 ---

    async def distribute_to_target(
        self,
        client,  # Pyrogram Client
        file_unique_id: str,
        target_chat_id: int,
        caption: str | None = None,
    ) -> int | None:
        """
        分发到目标频道。

        分发策略（逐级降级）：
        1. copy_message：直接从仓库频道复制消息
        2. file_id_send：使用 file_id 发送（需先刷新 file_id）
        3. 重新下载上传：返回 None，由调用方处理

        Args:
            client: Pyrogram User Client
            file_unique_id: 文件唯一标识
            target_chat_id: 目标频道 ID
            caption: 可选说明文字

        Returns:
            目标频道的消息 ID，或 None（分发失败）
        """
        # 获取仓库消息位置
        repo_location = self._db.get_repository_message_id(file_unique_id)
        if not repo_location:
            logger.error(f"未找到文件记录: file_unique_id={file_unique_id}")
            return None

        repo_chat_id, repo_message_id = repo_location
        method = "copy_message"

        # 1. 尝试 copy_message
        try:
            result = await client.copy_message(
                chat_id=target_chat_id,
                from_chat_id=repo_chat_id,
                message_id=repo_message_id,
                caption=caption,
            )
            self._record_distribution(file_unique_id, target_chat_id, result.id, method)
            logger.info(f"copy_message 分发成功: {file_unique_id} -> {target_chat_id}")
            return result.id
        except Exception as e:
            logger.warning(f"copy_message 失败: {e}")

        # 2. 降级: file_id_send
        method = "file_id_send"
        try:
            # 从仓库消息刷新 file_id
            messages = await client.get_messages(
                chat_id=repo_chat_id,
                message_ids=repo_message_id,
            )
            if messages:
                fresh_file_id = self._extract_file_id(messages)
                if fresh_file_id:
                    # 更新数据库中的 file_id
                    self._db.update_file_id(file_unique_id, fresh_file_id)

                    # 使用 file_id 发送
                    result = await self._send_by_file_id(
                        client, fresh_file_id, file_unique_id, target_chat_id, caption
                    )
                    if result:
                        self._record_distribution(
                            file_unique_id, target_chat_id, result.id, method
                        )
                        logger.info(
                            f"file_id_send 分发成功: {file_unique_id} -> {target_chat_id}"
                        )
                        return result.id
        except Exception as e:
            logger.warning(f"file_id_send 失败: {e}")

        # 3. 最终降级: 需要调用方处理重新下载上传
        logger.error(f"分发最终降级: file_unique_id={file_unique_id}, 需要重新下载上传")
        return None

    def _extract_file_id(self, message) -> str | None:
        """从消息中提取 file_id。

        按优先级依次检查 photo/video/document/audio/animation 属性。

        Args:
            message: Pyrogram Message 对象

        Returns:
            file_id 字符串，未找到时返回 None
        """
        for attr in ("photo", "video", "document", "audio", "animation"):
            media = getattr(message, attr, None)
            if media:
                return media.file_id
        return None

    async def _send_by_file_id(
        self,
        client,
        file_id: str,
        file_unique_id: str,
        target_chat_id: int,
        caption: str | None = None,
    ):
        """使用 file_id 发送文件。

        根据数据库中记录的 file_type 选择对应的 Pyrogram send 方法。

        Args:
            client: Pyrogram Client
            file_id: 文件 file_id
            file_unique_id: 文件唯一标识（用于查询 file_type）
            target_chat_id: 目标频道 ID
            caption: 可选说明文字

        Returns:
            Pyrogram Message 对象，发送失败时返回 None
        """
        # 查询文件类型
        file_record = self._db.get_file_by_unique_id(file_unique_id)
        if not file_record:
            return None

        file_type = file_record.file_type

        if file_type == "photo":
            return await client.send_photo(
                chat_id=target_chat_id, photo=file_id, caption=caption
            )
        elif file_type == "video":
            return await client.send_video(
                chat_id=target_chat_id, video=file_id, caption=caption
            )
        elif file_type == "audio":
            return await client.send_audio(
                chat_id=target_chat_id, audio=file_id, caption=caption
            )
        elif file_type == "animation":
            return await client.send_animation(
                chat_id=target_chat_id, animation=file_id, caption=caption
            )
        else:
            return await client.send_document(
                chat_id=target_chat_id, document=file_id, caption=caption
            )

    def _record_distribution(
        self,
        file_unique_id: str,
        target_chat_id: int,
        target_message_id: int | None,
        method: str,
        task_id: str | None = None,
    ) -> None:
        """记录分发日志。

        Args:
            file_unique_id: 文件唯一标识
            target_chat_id: 目标频道 ID
            target_message_id: 目标消息 ID
            method: 分发方法（copy_message / file_id_send）
            task_id: 可选任务 ID
        """
        try:
            record = FileDistribution(
                id=None,
                file_unique_id=file_unique_id,
                target_chat_id=target_chat_id,
                target_message_id=target_message_id,
                method=method,
                task_id=task_id,
                created_at=None,
            )
            self._db.insert_distribution(record)
        except Exception as e:
            logger.error(f"分发记录写入失败: {e}")
