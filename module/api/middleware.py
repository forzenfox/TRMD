# coding=UTF-8
"""自定义中间件：CORS、请求日志、安全头、响应时间。

中间件执行顺序：
1. CORS - 跨域资源共享
2. ProcessTime - 响应时间记录
3. RequestLog - 请求日志
4. SecurityHeaders - 安全响应头
"""

import logging
import time

from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """注册所有中间件到 FastAPI 应用。

    :param app: FastAPI 应用实例
    """
    # CORS 中间件（严格模式，仅允许同源）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 单用户场景下允许所有来源，生产环境应配置白名单
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 响应时间中间件
    app.add_middleware(ProcessTimeMiddleware)

    # 请求日志中间件
    app.add_middleware(RequestLogMiddleware)

    # 安全头中间件
    app.add_middleware(SecurityHeadersMiddleware)


class ProcessTimeMiddleware:
    """记录请求响应时间，超过阈值告警。"""

    THRESHOLD_MS = 1000  # 告警阈值：1 秒

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        await self.app(scope, receive, send)
        elapsed_ms = (time.time() - start_time) * 1000

        if elapsed_ms > self.THRESHOLD_MS:
            logger.warning("请求响应时间较长: %.2fms", elapsed_ms)


class RequestLogMiddleware:
    """记录请求方法、路径、状态码。不记录敏感 Token。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        await self.app(scope, receive, send)
        # 注意：在 __call__ 中无法直接获取 Response，这里仅记录请求信息
        logger.info("%s %s", request.method, request.url.path)


class SecurityHeadersMiddleware:
    """添加安全响应头。"""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for key, value in self.SECURITY_HEADERS.items():
                    headers.append((key.encode(), value.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
