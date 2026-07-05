# coding=UTF-8
"""集成模块 - 将新模块集成到现有代码。

本模块负责：
- 创建共享管理器实例（TokenManager、TaskManager、CacheManager、FileManager）
- 初始化 Web API 服务
- 集成 Bot 新增命令
- 提供统一的应用上下文
"""

import os
import logging
from typing import Optional

from module.core.token_manager import TokenManager
from module.core.task_manager import TaskManager
from module.core.cache_manager import CacheManager
from module.core.file_manager import FileManager
from module.core.repository_db import RepositoryDB
from module.core.repository_sync import RepositorySync
from module.core.config_manager import ConfigManager
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
        self.config_manager = self._init_config_manager()
        self.task_manager = self._init_task_manager()
        self.cache_manager = self._init_cache_manager()
        self.file_manager = self._init_file_manager()
        self.interaction_manager = self._init_interaction_manager()
        self.repository_db = self._init_repository_db()
        self.repository_manager = self._init_repository_manager()
        self.repository_sync = None  # 延迟初始化，需要 client

        # 延迟初始化（需在 client 启动后调用 init_task_executor）
        self.task_executor = None

        # Telegram Client（延迟注入，client 启动后设置）
        self.client = None

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
        rl = self.config_manager.resource_limits
        tm = TaskManager(
            db_path=self.db_path,
            max_concurrent_tasks=rl.get("max_concurrent_tasks", 1),
            max_retry_count=5,
            task_size_warning_gb=rl.get("task_size_warning_gb", 5),
            task_size_max_gb=rl.get("task_size_max_gb", 10),
            min_disk_space_gb=rl.get("min_disk_space_gb", 2),
            config_manager=self.config_manager,
        )
        log.info("TaskManager 已初始化（配置来自 ConfigManager）")
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

    def _init_config_manager(self) -> ConfigManager:
        """初始化 ConfigManager。"""
        cm = ConfigManager(user_config=None)
        log.info("ConfigManager 已初始化")
        return cm

    def _init_repository_db(self) -> RepositoryDB:
        """初始化 RepositoryDB。"""
        db_path = os.path.join(self.data_dir, "repository.db")
        repo_db = RepositoryDB(db_path=db_path)
        log.info(f"RepositoryDB 已初始化，数据库路径: {db_path}")
        return repo_db

    def _init_repository_manager(self):
        """初始化 RepositoryManager。"""
        from module.core.repository_manager import RepositoryManager

        rm = RepositoryManager(
            repository_db=self.repository_db,
            config_manager=self.config_manager,
        )
        log.info("RepositoryManager 已初始化")
        return rm

    def init_repository_sync(self, client) -> None:
        """延迟初始化并启动 RepositorySync。

        需在 Pyrogram Client 启动后调用。

        Args:
            client: 已启动的 Pyrogram Client 实例
        """
        if self.repository_sync is not None:
            log.warning("RepositorySync 已经初始化，跳过重复启动")
            return

        self.repository_sync = RepositorySync(
            repository_db=self.repository_db,
            config_manager=self.config_manager,
        )
        self.repository_sync.start()
        log.info("RepositorySync 已初始化并启动")

    def stop_repository_sync(self) -> None:
        """停止 RepositorySync 同步任务。"""
        if self.repository_sync is not None and self.repository_sync.is_running:
            self.repository_sync.stop()
            log.info("RepositorySync 已停止")

    def init_task_manager_services(self, client) -> None:
        """在 Telegram Client 启动后向 TaskManager 注入 IdentifierService。

        由于 client 在 AppContext 初始化时尚未启动，IdentifierService 需要延迟注入。
        本方法幂等：若 task_manager 已持有 IdentifierService 则跳过。

        Args:
            client: 已启动的 Pyrogram Client 实例
        """
        if self.task_manager is None:
            log.warning("TaskManager 未初始化，跳过 IdentifierService 注入")
            return

        if getattr(self.task_manager, "_identifier_service", None) is not None:
            log.info("TaskManager 已注入 IdentifierService，跳过重复注入")
            return

        from module.core.identifier_service import IdentifierService

        self.task_manager._identifier_service = IdentifierService(client)
        log.info("TaskManager 已注入 IdentifierService")

    async def init_task_executor(self, client, downloader=None, uploader=None):
        """初始化任务执行器（需在 client 启动后调用）。

        Args:
            client: Pyrogram Client 实例
            downloader: 下载器实例（可选，不传则走降级方案）
            uploader: 上传器实例（可选）
        """
        from module.core.task_executor import TaskExecutor

        self.task_executor = TaskExecutor(
            task_manager=self.task_manager,
            file_manager=self.file_manager,
            client=client,
            downloader=downloader,
            uploader=uploader,
            config_manager=self.config_manager,
            repository_manager=self.repository_manager,
        )
        log.info("TaskExecutor 已初始化")

        # 恢复 running 状态的监听任务
        await self.task_executor.recover_listeners()

    def get_webui_url(self, token: str) -> str:
        """生成 WebUI 访问链接。"""
        return f"http://{self.web_host}:{self.web_port}?token={token}"

    def cleanup(self):
        """清理资源。"""
        self.stop_repository_sync()
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
