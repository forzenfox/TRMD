# coding=UTF-8
"""FastAPI 应用工厂。

提供 create_app() 函数，支持注入 Mock 依赖用于测试。
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from module.api.routes.router import api_router
from module.api.middleware import setup_middleware
from module.api.exceptions import setup_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化异步数据库，关闭时清理资源。"""
    from module.core import db

    ctx = app.state.app_context
    # is_initialized() 对同步引擎也返回 True，但 API 路由需要异步引擎；
    # 因此使用 is_async_initialized() 精确检查。
    if ctx is not None and not db.is_async_initialized():
        await db.init_db(ctx.db_path)
        logger.info("异步数据库引擎已初始化（lifespan）")

    yield  # 应用运行中

    # 关闭异步数据库连接
    if db.is_async_initialized():
        await db.close_db()
        logger.info("异步数据库引擎已关闭（lifespan）")


def create_app(
    token_manager=None,
    task_manager=None,
    file_manager=None,
    config_manager=None,
    monitor=None,
) -> FastAPI:
    """创建 FastAPI 应用实例。

    :param token_manager: TokenManager 实例（测试时可注入 Mock）
    :param task_manager: TaskManager 实例（测试时可注入 Mock）
    :param file_manager: FileManager 实例（测试时可注入 Mock）
    :param config_manager: 配置管理器实例（测试时可注入 Mock）
    :param monitor: Monitor 实例（测试时可注入 Mock）
    :return: 配置完成的 FastAPI 应用
    """
    # 根据环境变量决定是否启用 Swagger UI
    is_prod = os.getenv("TRMD_ENV") == "production"

    # 通过 AppContext 获取共享的管理器实例（与 BOT 共享同一 TokenManager）
    from module.core.monitor import Monitor

    ctx = None
    if token_manager is None:
        from module.core.integration import init_context

        ctx = init_context()
        token_manager = ctx.token_manager
        if config_manager is None:
            config_manager = ctx.config_manager

    app = FastAPI(
        title="TRMD Web API",
        version="1.0.0",
        description="Telegram Restricted Media Downloader Web API",
        lifespan=_lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # 保存 AppContext 供 lifespan 使用（初始化异步 DB 需要 db_path）
    app.state.app_context = ctx

    # 挂载核心管理器到应用状态
    app.state.token_manager = token_manager
    app.state.task_manager = task_manager or (ctx.task_manager if ctx else None)
    app.state.file_manager = file_manager or (ctx.file_manager if ctx else None)
    app.state.config_manager = config_manager
    app.state.monitor = monitor or Monitor()
    # TaskExecutor 由 downloader 在 client 启动后延迟初始化，此处先挂载 None
    app.state.task_executor = getattr(ctx, "task_executor", None) if ctx else None

    # 注册中间件
    setup_middleware(app)

    # 注册异常处理器
    setup_exception_handlers(app)

    # 注册 REST 路由
    app.include_router(api_router, prefix="/api")

    # 根路径：重定向到登录页（保留 token 参数）
    from fastapi.responses import RedirectResponse

    @app.get("/")
    async def root(token: str = None):
        if token:
            return RedirectResponse(url=f"/web/login.html?token={token}")
        return RedirectResponse(url="/web/login.html")

    # 提供 WebUI 静态文件（如果存在）
    web_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "module", "web"
    )
    if os.path.isdir(web_dir):
        app.mount("/web", StaticFiles(directory=web_dir), name="web")

    return app
