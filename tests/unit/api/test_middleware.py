# coding=UTF-8
"""中间件测试。

验证 RequestLogMiddleware 的轮询路径过滤行为：
- 轮询路径的 GET 请求不产生 DEBUG 日志
- 非轮询路径的请求仍正常记录 DEBUG 日志
- 轮询路径的 POST/PUT 等非 GET 请求仍正常记录
"""

import logging

import pytest

from module.api.middleware import RequestLogMiddleware


class TestRequestLogMiddlewarePollingFilter:
    """验证 RequestLogMiddleware 的轮询路径过滤。"""

    def test_polling_paths_defined(self):
        """应定义轮询路径集合。"""
        assert hasattr(RequestLogMiddleware, "_POLLING_PATHS")
        polling_paths = RequestLogMiddleware._POLLING_PATHS
        assert "/api/tasks" in polling_paths
        assert "/api/auth/me" in polling_paths
        assert "/api/monitor/resource/status" in polling_paths
        assert "/api/config" in polling_paths

    def test_polling_get_request_skipped(self, caplog):
        """轮询路径的 GET 请求不应产生 DEBUG 日志。"""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def tasks_endpoint(request):
            return JSONResponse({"tasks": []})

        app = Starlette(
            routes=[Route("/api/tasks", tasks_endpoint)],
        )
        # 添加 RequestLogMiddleware
        app.add_middleware(RequestLogMiddleware)

        client = TestClient(app)
        with caplog.at_level(logging.DEBUG, logger="module.api.middleware"):
            response = client.get("/api/tasks")
            assert response.status_code == 200

        # 不应有 DEBUG 日志记录此 GET 请求
        debug_logs = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "GET /api/tasks" in r.message
        ]
        assert len(debug_logs) == 0, "轮询 GET 请求不应产生 DEBUG 日志"

    def test_non_polling_get_request_logged(self, caplog):
        """非轮询路径的 GET 请求应正常记录 DEBUG 日志。"""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def chats_endpoint(request):
            return JSONResponse({"chats": []})

        app = Starlette(
            routes=[Route("/api/chats", chats_endpoint)],
        )
        app.add_middleware(RequestLogMiddleware)

        client = TestClient(app)
        with caplog.at_level(logging.DEBUG, logger="module.api.middleware"):
            response = client.get("/api/chats")
            assert response.status_code == 200

        # 应有 DEBUG 日志记录此 GET 请求
        debug_logs = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "GET /api/chats" in r.message
        ]
        assert len(debug_logs) == 1, "非轮询 GET 请求应产生 DEBUG 日志"

    def test_polling_post_request_logged(self, caplog):
        """轮询路径的 POST 请求应正常记录 DEBUG 日志（POST 不是轮询）。"""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def create_task_endpoint(request):
            return JSONResponse({"id": "test"}, status_code=201)

        app = Starlette(
            routes=[Route("/api/tasks", create_task_endpoint, methods=["POST"])],
        )
        app.add_middleware(RequestLogMiddleware)

        client = TestClient(app)
        with caplog.at_level(logging.DEBUG, logger="module.api.middleware"):
            response = client.post("/api/tasks", json={"type": "download"})
            assert response.status_code == 201

        # 应有 DEBUG 日志记录此 POST 请求
        debug_logs = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "POST /api/tasks" in r.message
        ]
        assert len(debug_logs) == 1, "轮询路径的 POST 请求应产生 DEBUG 日志"
