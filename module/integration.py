# coding=UTF-8
"""集成模块 - 将新模块集成到现有代码。

本模块负责：
- 创建共享管理器实例（TokenManager、TaskManager、CacheManager、FileManager）
- 初始化 Web API 服务
- 集成 Bot 新增命令
- 提供统一的应用上下文
"""

import os
import asyncio
import logging
from typing import Optional

from module.core.token_manager import TokenManager
from module.core.task_manager import TaskManager
from module.core.cache_manager import CacheManager
from module.core.file_manager import FileManager
from module.interaction_manager import InteractionManager

log = logging.getLogger("rich")


class AppContext:
    """应用上下文，管理所有共享管理器实例。

    单例模式，确保 Bot 和 Web API 使用同一套管理器。
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        data_dir: Optional[str] = None,
        root_user_id: Optional[int] = None,
        web_host: str = "127.0.0.1",
        web_port: int = 8000,
    ):
        # 防止重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".trmd"
        )
        os.makedirs(self.data_dir, exist_ok=True)

        self.root_user_id = root_user_id
        self.web_host = web_host
        self.web_port = web_port

        # 数据库路径
        self.db_path = os.path.join(self.data_dir, "trmd.db")

        # 初始化核心管理器
        self.token_manager = self._init_token_manager()
        self.task_manager = self._init_task_manager()
        self.cache_manager = self._init_cache_manager()
        self.file_manager = self._init_file_manager()
        self.interaction_manager = self._init_interaction_manager()

        # 全部初始化成功后才标记，避免部分失败导致单例残缺
        self._initialized = True

        log.info(f"应用上下文已初始化，数据目录: {self.data_dir}")

    def _init_token_manager(self) -> TokenManager:
        """初始化 TokenManager。"""
        db_path = os.path.join(self.data_dir, "tokens.db")
        tm = TokenManager(db_path=db_path)
        log.info("TokenManager 已初始化")
        return tm

    def _init_task_manager(self) -> TaskManager:
        """初始化 TaskManager。"""
        tm = TaskManager(
            db_path=self.db_path,
            max_concurrent_tasks=1,
            max_retries=3,
        )
        log.info("TaskManager 已初始化")
        return tm

    def _init_cache_manager(self) -> CacheManager:
        """初始化 CacheManager。"""
        cm = CacheManager(db_path=self.db_path)
        log.info("CacheManager 已初始化")
        return cm

    def _init_file_manager(self) -> FileManager:
        """初始化 FileManager（延迟初始化，config/client 由外部注入）。"""
        fm = FileManager(config={}, client=None)
        log.info("FileManager 已初始化（待外部注入 config/client）")
        return fm

    def _init_interaction_manager(self) -> InteractionManager:
        """初始化 InteractionManager。"""
        state_file = os.path.join(self.data_dir, "interaction_state.json")
        im = InteractionManager(state_file=state_file, timeout_seconds=300)
        log.info("InteractionManager 已初始化")
        return im

    def get_webui_url(self, token: str) -> str:
        """生成 WebUI 访问链接。"""
        return f"http://{self.web_host}:{self.web_port}?token={token}"

    def cleanup(self):
        """清理资源。"""
        if hasattr(self, "_initialized"):
            self._initialized = False
            AppContext._instance = None
            log.info("应用上下文已清理")


def get_context() -> Optional[AppContext]:
    """获取当前应用上下文实例。"""
    return AppContext._instance


def init_context(**kwargs) -> AppContext:
    """初始化应用上下文。"""
    # 若未显式传入 data_dir，尝试从 config.yaml 读取
    if "data_dir" not in kwargs or kwargs["data_dir"] is None:
        _config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
        )
        try:
            import yaml

            with open(_config_path, "r", encoding="UTF-8") as _f:
                _cfg = yaml.safe_load(_f)
            if _cfg and isinstance(_cfg, dict) and _cfg.get("data_directory"):
                _resolved = _cfg["data_directory"]
                # 相对路径基于项目根目录解析
                if not os.path.isabs(_resolved):
                    _resolved = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        _resolved,
                    )
                kwargs["data_dir"] = os.path.normpath(_resolved)
        except Exception:
            pass
    return AppContext(**kwargs)
