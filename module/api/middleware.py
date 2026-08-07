# coding=UTF-8
"""自定义中间件：CORS、请求日志、安全头、响应时间。

中间件执行顺序（按设计文档 §2.4）：
1. CORS - 跨域资源共享
2. ProcessTime - 响应时间记录
3. RequestLog - 请求日志
4. SecurityHeaders - 安全响应头
"""

import logging
import time

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """注册所有中间件到 FastAPI 应用。

    :param app: FastAPI 应用实例
    """
    # 1. CORS 中间件（单用户场景下允许所有来源，认证由 Token 机制保障）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. 响应时间中间件
    app.add_middleware(ProcessTimeMiddleware)

    # 3. 请求日志中间件
    app.add_middleware(RequestLogMiddleware)

    # 4. 安全头中间件
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
    """记录请求方法、路径、状态码。不记录敏感 Token。

    被前端定时轮询的 GET 接口不记录日志（太频繁，无诊断价值），
    非轮询路径和非 GET 方法（如 POST/PUT）仍正常记录。
    """

    # 被前端定时轮询的接口路径，无需记录每次请求
    _POLLING_PATHS = frozenset({
        "/api/tasks",
        "/api/auth/me",
        "/api/monitor/resource/status",
        "/api/config",
    })

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        await self.app(scope, receive, send)
        # 注意：在 __call__ 中无法直接获取 Response，这里仅记录请求信息
        path = request.url.path
        # 轮询接口的 GET 请求不记录日志（太频繁，无诊断价值）
        if request.method == "GET" and path in self._POLLING_PATHS:
            return
        logger.debug("%s %s", request.method, path)


class SecurityHeadersMiddleware:
    """添加安全响应头。"""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;",
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
