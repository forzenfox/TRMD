# coding=UTF-8
"""FastAPI 路由注册。

将所有路由模块组合为统一的 APIRouter。
设计依据: module-design-web-api.md §2.3 路由组织
"""

from fastapi import APIRouter

from module.api.routes import auth, tasks, chats, files, config, monitor, repository

# 主 API 路由器
api_router = APIRouter()

# 注册子路由（按设计文档顺序）
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(chats.router)
api_router.include_router(files.router)
api_router.include_router(config.router)
api_router.include_router(monitor.router)
api_router.include_router(repository.router)  # 仓库模式路由
