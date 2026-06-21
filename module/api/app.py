# coding=UTF-8
"""FastAPI 应用工厂。

提供 create_app() 函数，支持注入 Mock 依赖用于测试。
"""

import os
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from module.api.routes.router import api_router
from module.api.websocket.router import websocket_router
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
    app = FastAPI(
        title="TRMD Web API",
        version="1.0.0",
        docs_url=None,  # 禁用 Swagger
        redoc_url=None,  # 禁用 ReDoc
    )

    # 挂载核心管理器到应用状态
    from module.core.token_manager import TokenManager
    from module.core.monitor import Monitor
    app.state.token_manager = token_manager or TokenManager()
    app.state.task_manager = task_manager
    app.state.file_manager = file_manager
    app.state.config_manager = config_manager
    app.state.monitor = monitor or Monitor()

    # 注册中间件
    setup_middleware(app)

    # 注册异常处理器
    setup_exception_handlers(app)

    # 注册 REST 路由
    app.include_router(api_router, prefix="/api")

    # 注册 WebSocket 路由
    app.include_router(websocket_router)

    # 提供 WebUI 静态文件（如果存在）
    web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "module", "web")
    if os.path.isdir(web_dir):
        app.mount("/web", StaticFiles(directory=web_dir), name="web")

    return app
