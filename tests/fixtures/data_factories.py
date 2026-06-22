# -*- coding: utf-8 -*-
"""测试数据工厂。

提供生成测试数据的辅助类，用于简化测试用例编写。
"""

from typing import Dict, Any, Optional
from datetime import datetime


class TaskFactory:
    """任务测试数据工厂。"""

    @staticmethod
    def create_task_data(
        task_type: str = "download",
        chat_id: int = -1001234567890,
        message_ids: Optional[list] = None,
    ) -> Dict[str, Any]:
        """生成任务创建数据。

        Args:
            task_type: 任务类型 (download/upload/forward)
            chat_id: 频道 ID
            message_ids: 消息 ID 列表

        Returns:
            任务创建数据字典
        """
        return {
            "task_type": task_type,
            "chat_id": chat_id,
            "params": {"message_ids": message_ids or [123, 124, 125]},
        }

    @staticmethod
    def create_download_task_data(
        chat_id: int = -1001234567890,
        message_ids: Optional[list] = None,
    ) -> Dict[str, Any]:
        """生成下载任务数据。

        Args:
            chat_id: 源频道 ID
            message_ids: 消息 ID 列表

        Returns:
            下载任务数据字典
        """
        return TaskFactory.create_task_data(
            task_type="download", chat_id=chat_id, message_ids=message_ids
        )

    @staticmethod
    def create_upload_task_data(
        chat_id: int = -1001234567890,
        file_paths: Optional[list] = None,
    ) -> Dict[str, Any]:
        """生成上传任务数据。

        Args:
            chat_id: 目标频道 ID
            file_paths: 文件路径列表

        Returns:
            上传任务数据字典
        """
        return {
            "task_type": "upload",
            "chat_id": chat_id,
            "params": {"file_paths": file_paths or ["/tmp/test.mp4"]},
        }

    @staticmethod
    def create_forward_task_data(
        source_chat_id: int = -1001234567890,
        target_chat_id: int = -1001234567891,
        message_ids: Optional[list] = None,
    ) -> Dict[str, Any]:
        """生成转发任务数据。

        Args:
            source_chat_id: 源频道 ID
            target_chat_id: 目标频道 ID
            message_ids: 消息 ID 列表

        Returns:
            转发任务数据字典
        """
        return {
            "task_type": "forward",
            "chat_id": source_chat_id,
            "params": {
                "target_chat_id": target_chat_id,
                "message_ids": message_ids or [123, 124, 125],
            },
        }


class TokenFactory:
    """Token 测试数据工厂。"""

    @staticmethod
    def create_token_data(
        user_id: int = 1,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """生成 Token 数据。

        Args:
            user_id: 用户 ID
            expires_at: 过期时间

        Returns:
            Token 数据字典
        """
        return {
            "user_id": user_id,
            "expires_at": expires_at or datetime.now(),
            "created_at": datetime.now(),
            "usage_count": 0,
        }


class ConfigFactory:
    """配置测试数据工厂。"""

    @staticmethod
    def create_test_config(
        download_type: Optional[list] = None,
        max_retry_count: int = 3,
        save_directory: str = "/tmp/downloads",
    ) -> Dict[str, Any]:
        """生成测试配置。

        Args:
            download_type: 下载类型列表
            max_retry_count: 最大重试次数
            save_directory: 保存目录

        Returns:
            配置数据字典
        """
        return {
            "download_type": download_type or ["video", "photo"],
            "max_retry_count": max_retry_count,
            "save_directory": save_directory,
            "resource_limits": {
                "task_size_warning_gb": 5,
                "task_size_max_gb": 10,
                "min_disk_space_gb": 2,
                "memory_limit_mb": 512,
                "max_concurrent_tasks": 1,
                "max_download_concurrency": 3,
                "max_upload_concurrency": 1,
                "max_forward_concurrency": 1,
            },
            "upload": {
                "delete_after_upload": False,
                "max_group_size": 10,
            },
        }
