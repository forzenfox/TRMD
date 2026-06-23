# coding=UTF-8
"""FastAPI 应用工厂。

提供 create_app() 函数，支持注入 Mock 依赖用于测试。
"""

import os
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from module.api.routes.router import api_router
from module.api.middleware import setup_middleware
from module.api.exceptions import setup_exception_handlers

logger = logging.getLogger(__name__)


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

    app = FastAPI(
        title="TRMD Web API",
        version="1.0.0",
        description="Telegram Restricted Media Downloader Web API",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # 挂载核心管理器到应用状态
    from module.core.monitor import Monitor

    # 通过 AppContext 获取共享的管理器实例（与 BOT 共享同一 TokenManager）
    ctx = None
    if token_manager is None:
        from module.integration import init_context
        ctx = init_context()
        token_manager = ctx.token_manager

    app.state.token_manager = token_manager
    app.state.task_manager = task_manager or (ctx.task_manager if ctx else None)
    app.state.file_manager = file_manager or (ctx.file_manager if ctx else None)
    app.state.config_manager = config_manager
    app.state.monitor = monitor or Monitor()

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
