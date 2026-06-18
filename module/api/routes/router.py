# coding=UTF-8
"""FastAPI 路由注册。

将所有路由模块组合为统一的 APIRouter。
"""

from fastapi import APIRouter

from module.api.routes import auth, tasks, chats, files, config

# 主 API 路由器
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(chats.router)
api_router.include_router(files.router)
api_router.include_router(config.router)
