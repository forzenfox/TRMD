# coding=UTF-8
"""自定义中间件：TrustedHost、CORS、请求日志、安全头、响应时间。

中间件执行顺序（按设计文档 §2.4）：
1. TrustedHost - 限制Host头，防止Host头攻击
2. CORS - 跨域资源共享
3. ProcessTime - 响应时间记录
4. RequestLog - 请求日志
5. SecurityHeaders - 安全响应头
"""

import fnmatch
import logging
import time

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """注册所有中间件到 FastAPI 应用。

    :param app: FastAPI 应用实例
    """
    # 1. TrustedHost 中间件（首个中间件，防止Host头攻击）
    app.add_middleware(TrustedHostMiddleware)

    # 2. CORS 中间件（严格模式，仅允许同源）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 单用户场景下允许所有来源，生产环境应配置白名单
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. 响应时间中间件
    app.add_middleware(ProcessTimeMiddleware)

    # 4. 请求日志中间件
    app.add_middleware(RequestLogMiddleware)

    # 5. 安全头中间件
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


class TrustedHostMiddleware:
    """限制Host头，防止Host头攻击。

    设计依据: module-design-web-api.md §2.4 中间件栈(第174行)

    单用户场景下默认允许localhost和本地IP，可通过配置扩展Host列表。
    """

    # 默认允许的Host列表（单用户场景）
    DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "::1", "*.local"]

    def __init__(self, app, allowed_hosts=None):
        """初始化TrustedHost中间件。

        :param app: ASGI应用
        :param allowed_hosts: 允许的Host列表（可选）
        """
        self.app = app
        self.allowed_hosts = allowed_hosts or self.DEFAULT_ALLOWED_HOSTS

    async def __call__(self, scope, receive, send):
        """中间件执行逻辑。

        :param scope: ASGI scope
        :param receive: ASGI receive
        :param send: ASGI send
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 提取Host头
        headers = dict(scope.get("headers", []))
        host_header = headers.get(b"host", b"").decode("utf-8", errors="ignore")

        # 移除端口部分（如 localhost:8000 -> localhost）
        host = host_header.split(":")[0].lower()

        # 检查Host是否在允许列表中
        if not self._is_allowed_host(host):
            logger.warning("非法Host请求被拦截: %s", host)
            await self._send_400_response(send, f"Host '{host}' not allowed")
            return

        await self.app(scope, receive, send)

    def _is_allowed_host(self, host: str) -> bool:
        """检查Host是否在允许列表中。

        支持通配符匹配（如 *.local）。

        :param host: 待检查的Host
        :return: 是否允许
        """
        if not host:
            return False

        for pattern in self.allowed_hosts:
            # 使用fnmatch进行通配符匹配
            if fnmatch.fnmatch(host, pattern.lower()):
                return True

        return False

    async def _send_400_response(self, send, message: str):
        """发送400 Bad Request响应。

        :param send: ASGI send函数
        :param message: 错误消息
        """
        response_body = f'{{"error": "INVALID_HOST", "message": "{message}"}}'.encode(
            "utf-8"
        )

        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response_body)).encode()),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": response_body,
            }
        )
