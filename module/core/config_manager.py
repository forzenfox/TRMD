# coding=UTF-8
"""ConfigManager - 配置管理器

包装现有的 UserConfig，提供统一的配置读写接口。
支持 Web API 配置管理，敏感字段脱敏处理。
所有配置已合并到单一 config.yaml，不再依赖独立的 GlobalConfig。

位置：module/core/config_manager.py（统一到核心业务层）
"""

import copy
import logging
import re
from typing import Any, Optional

from module.yaml_utils import deep_merge

log = logging.getLogger(__name__)

# 敏感字段列表（Web 接口返回时脱敏）
SENSITIVE_FIELDS = {"api_id", "api_hash", "bot_token"}

# 默认资源配置
DEFAULT_RESOURCE_LIMITS = {
    "task_size_warning_gb": 5,
    "task_size_max_gb": 10,
    "min_disk_space_gb": 2,
    "memory_limit_mb": 512,
    "max_concurrent_tasks": 1,
    "max_download_concurrency": 3,
    "max_upload_concurrency": 1,
    "max_forward_concurrency": 1,
}

# 默认上传配置
DEFAULT_UPLOAD_CONFIG = {
    "delete_after_upload": False,
    "max_group_size": 10,
}


class ConfigManagerError(Exception):
    """配置管理器异常基类。"""

    pass


class ConfigValidationError(ConfigManagerError):
    """配置验证错误。"""

    pass


class ConfigManager:
    """配置管理器 - Bot 和 WebUI 共享。

    包装 UserConfig，提供统一接口：
    - load_config(): 加载完整配置（敏感字段脱敏）
    - save_config(config_dict): 保存配置
    - get(key, default): 获取配置项
    - set(key, value): 设置配置项
    - validate_config(config_dict): 验证配置
    - get_repository_config(): 获取 repository 分组配置
    - set_repository_chat_id(chat_id): 设置 repository.chat_id
    - validate_repository_config(): 验证 repository 配置
    """

    def __init__(
        self,
        user_config: Optional[object] = None,
    ):
        """
        Args:
            user_config: UserConfig 实例（可选）
        """
        self._user_config = user_config
        self._resource_limits: dict = copy.deepcopy(DEFAULT_RESOURCE_LIMITS)
        self._upload_config: dict = copy.deepcopy(DEFAULT_UPLOAD_CONFIG)

    def _get_raw_config(self) -> dict:
        """获取原始配置字典。"""
        if self._user_config and hasattr(self._user_config, "config"):
            return getattr(self._user_config, "config", {})
        if self._user_config and hasattr(self._user_config, "get_config"):
            return self._user_config.get_config()
        return {}

    def _save_raw_config(self, config: dict) -> bool:
        """保存原始配置字典。"""
        if self._user_config and hasattr(self._user_config, "save_config"):
            try:
                self._user_config.save_config(config)
                return True
            except Exception as e:
                log.error(f"保存配置失败: {e}")
                return False
        return False

    def load_config(self, mask_sensitive: bool = True) -> dict:
        """加载完整配置。

        Args:
            mask_sensitive: 是否对敏感字段进行脱敏

        Returns:
            配置字典
        """
        raw_config = self._get_raw_config()
        result = copy.deepcopy(raw_config)

        if mask_sensitive:
            # 脱敏敏感字段
            for field in SENSITIVE_FIELDS:
                if field in result:
                    result[field] = "***"

        # 添加资源限制配置
        if "resource_limits" not in result:
            result["resource_limits"] = copy.deepcopy(self._resource_limits)
        else:
            # 合并默认值（如果用户配置中缺少某些字段）
            for key, default_value in self._resource_limits.items():
                if key not in result["resource_limits"]:
                    result["resource_limits"][key] = default_value

        # 添加上传配置
        if "upload" not in result:
            result["upload"] = copy.deepcopy(self._upload_config)
        else:
            for key, default_value in self._upload_config.items():
                if key not in result["upload"]:
                    result["upload"][key] = default_value

        return result

    def save_config(self, config: dict) -> bool:
        """保存配置。

        Args:
            config: 要保存的配置字典

        Returns:
            是否保存成功
        """
        # 验证配置
        is_valid, errors = self.validate_config(config)
        if not is_valid:
            raise ConfigValidationError(f"配置验证失败: {', '.join(errors)}")

        # 获取当前完整配置（包含敏感字段）
        current_config = self._get_raw_config()

        # 提取资源限制（不保存到 UserConfig，而是存储到内部）
        if "resource_limits" in config:
            for key, value in config["resource_limits"].items():
                if key in self._resource_limits:
                    self._resource_limits[key] = value

        # 提取上传配置
        if "upload" in config:
            for key, value in config["upload"].items():
                if key in self._upload_config:
                    self._upload_config[key] = value

        # 更新可保存的配置项（忽略敏感字段和只读字段）
        update_config = copy.deepcopy(config)
        # 移除不应该由 Web 更新的字段
        update_config.pop("resource_limits", None)
        update_config.pop("upload", None)

        # 合并到当前配置（使用 deep_merge 保留 CommentedMap 注释元数据）
        merged_config = deep_merge(current_config, update_config)

        return self._save_raw_config(merged_config)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项。

        Args:
            key: 配置键（支持嵌套，如 'proxy.enable'）
            default: 默认值

        Returns:
            配置值
        """
        config = self._get_raw_config()

        # 支持嵌套键
        keys = key.split(".")
        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        # 敏感字段脱敏
        if key in SENSITIVE_FIELDS:
            return "***"

        return value

    def set(self, key: str, value: Any) -> bool:
        """设置配置项。

        Args:
            key: 配置键（支持嵌套）
            value: 配置值

        Returns:
            是否设置成功
        """
        # 敏感字段禁止通过 set 修改
        if key in SENSITIVE_FIELDS:
            log.warning(f"禁止通过 set 修改敏感字段: {key}")
            return False

        config = self._get_raw_config()
        keys = key.split(".")

        # 导航到嵌套字典
        target = config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value

        return self._save_raw_config(config)

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        """验证配置。

        Args:
            config: 要验证的配置字典

        Returns:
            (是否有效, 错误列表)
        """
        errors: list[str] = []

        # 验证资源限制
        if "resource_limits" in config:
            rl = config["resource_limits"]

            # 任务大小限制
            warning_gb = rl.get("task_size_warning_gb", 5)
            max_gb = rl.get("task_size_max_gb", 10)

            if not isinstance(warning_gb, (int, float)) or warning_gb <= 0:
                errors.append("task_size_warning_gb 必须是正数")

            if not isinstance(max_gb, (int, float)) or max_gb <= 0:
                errors.append("task_size_max_gb 必须是正数")

            if warning_gb >= max_gb:
                errors.append("task_size_warning_gb 必须小于 task_size_max_gb")

            # 磁盘空间
            min_disk = rl.get("min_disk_space_gb", 2)
            if not isinstance(min_disk, (int, float)) or min_disk <= 0:
                errors.append("min_disk_space_gb 必须是正数")

            # 内存限制
            memory_limit = rl.get("memory_limit_mb", 512)
            if not isinstance(memory_limit, (int, float)) or memory_limit <= 0:
                errors.append("memory_limit_mb 必须是正数")

            # 并发数
            for key in [
                "max_concurrent_tasks",
                "max_download_concurrency",
                "max_upload_concurrency",
                "max_forward_concurrency",
            ]:
                val = rl.get(key)
                if val is not None:
                    if not isinstance(val, int) or val < 1:
                        errors.append(f"{key} 必须是正整数")

        # 验证代理配置
        if "proxy" in config:
            proxy = config["proxy"]
            if proxy.get("enable", False):
                if not proxy.get("hostname"):
                    errors.append("启用代理时必须指定 hostname")
                if not proxy.get("port"):
                    errors.append("启用代理时必须指定 port")

        # 验证下载类型
        if "download_type" in config:
            valid_types = ["all", "photo", "video", "audio", "animation", "document"]
            dt = config["download_type"]
            if isinstance(dt, str) and dt not in valid_types:
                errors.append(f"download_type 必须是以下之一: {', '.join(valid_types)}")

        return (len(errors) == 0, errors)

    # ---------- 便捷属性 ----------

    @property
    def resource_limits(self) -> dict:
        """获取资源限制配置。"""
        return copy.deepcopy(self._resource_limits)

    @property
    def upload_config(self) -> dict:
        """获取上传配置。"""
        return copy.deepcopy(self._upload_config)

    @property
    def save_directory(self) -> str:
        """获取下载保存目录。"""
        return self.get("save_directory", "downloads")

    @property
    def task_size_warning_gb(self) -> float:
        """获取任务大小告警阈值（GB）。"""
        return self._resource_limits.get("task_size_warning_gb", 5)

    @property
    def task_size_max_gb(self) -> float:
        """获取任务大小最大限制（GB）。"""
        return self._resource_limits.get("task_size_max_gb", 10)

    @property
    def min_disk_space_gb(self) -> float:
        """获取最小剩余磁盘空间（GB）。"""
        return self._resource_limits.get("min_disk_space_gb", 2)

    @property
    def memory_limit_mb(self) -> int:
        """获取单文件内存缓存上限（MB）。"""
        return self._resource_limits.get("memory_limit_mb", 512)

    @property
    def max_concurrent_tasks(self) -> int:
        """获取最大并发任务数。"""
        return self._resource_limits.get("max_concurrent_tasks", 1)

    # ---------- Repository 配置方法 ----------

    def get_repository_config(self) -> dict:
        """获取 repository 分组配置。

        Returns:
            repository 配置字典，如果不存在则返回空字典
        """
        config = self._get_raw_config()
        repo = config.get("repository", {})
        return copy.deepcopy(repo) if isinstance(repo, dict) else {}

    def set_repository_chat_id(self, chat_id: str) -> bool:
        """设置 repository.chat_id 并保存。

        Args:
            chat_id: 要设置的 chat_id 值

        Returns:
            是否设置成功
        """
        config = self._get_raw_config()
        if "repository" not in config or not isinstance(config.get("repository"), dict):
            config["repository"] = {
                "enabled": True,
                "chat_id": "",
                "auto_sync_enabled": False,
                "auto_sync_interval_minutes": 60,
            }
        config["repository"]["chat_id"] = chat_id
        return self._save_raw_config(config)

    def validate_repository_config(self) -> tuple[bool, str]:
        """验证 repository 配置。

        验证规则：
        - 如果 repository.enabled 为 True，chat_id 不能为空且格式必须合法
        - auto_sync_interval_minutes 如果 auto_sync_enabled 为 True，必须为正整数

        Returns:
            (是否有效, 错误消息)
        """
        repo = self.get_repository_config()

        if not repo:
            return (True, "")

        enabled = repo.get("enabled", False)

        # 未启用时不验证 chat_id
        if enabled:
            chat_id = repo.get("chat_id", "")
            if not chat_id:
                return (False, "repository 启用时 chat_id 不能为空")

            # 验证 chat_id 格式：应为数字字符串，可带负号前缀
            if not re.match(r"^-?\d+$", str(chat_id)):
                return (
                    False,
                    f"repository.chat_id 格式无效: '{chat_id}'，应为数字字符串",
                )

        # 验证自动同步间隔
        auto_sync_enabled = repo.get("auto_sync_enabled", False)
        if auto_sync_enabled:
            interval = repo.get("auto_sync_interval_minutes", 60)
            if not isinstance(interval, (int, float)) or interval <= 0:
                return (False, "repository.auto_sync_interval_minutes 必须是正数")

        return (True, "")
