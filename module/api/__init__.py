# coding=UTF-8
"""Web API 模块。

提供 FastAPI 应用工厂、路由注册和核心依赖注入。
详见 `docs/模块设计-WebAPI.md`。
"""

from module.api.app import create_app

__all__ = ["create_app"]
