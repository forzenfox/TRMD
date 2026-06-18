# coding=UTF-8
"""Web API 模块集成测试。

使用 httpx.AsyncClient 测试 FastAPI 路由、中间件、认证、WebSocket 等。
Mock TokenManager、TaskManager 等核心模块。
"""

import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from module.api.app import create_app
from module.core.token_manager import TokenManager
from module.core.task_manager import TaskManager, TaskType, TaskStatus


# ==================== 测试工具 ====================


@pytest.fixture
def token_manager():
    """提供内存模式 TokenManager。"""
    tm = TokenManager(db_path=None, default_ttl=3600)
    return tm


@pytest.fixture
def valid_token(token_manager):
    """生成有效 Token。"""
    return token_manager.generate(user_id=1)


@pytest.fixture
def task_manager():
    """提供内存模式 TaskManager（不持久化）。"""
    tm = TaskManager(db_path=":memory:", max_concurrent_tasks=2)
    return tm


@pytest.fixture
def config_manager():
    """提供 Mock 配置管理器。"""
    mock = MagicMock()
    mock.config = {
        "api_id": "12345",
        "api_hash": "test_hash",
        "bot_token": "test_bot_token",
        "save_directory": tempfile.gettempdir(),
        "download_type": ["video", "photo"],
        "max_tasks": {"download": 3, "upload": 3},
        "max_retries": {"download": 3, "upload": 3},
        "proxy": {
            "enable_proxy": False,
            "scheme": None,
            "hostname": None,
            "port": None,
            "username": None,
            "password": None,
        },
    }
    mock.save_directory = tempfile.gettempdir()
    mock.save_config = MagicMock()
    return mock


@pytest_asyncio.fixture
async def client(token_manager, task_manager, config_manager):
    """提供已认证的测试客户端。"""
    app = create_app(
        token_manager=token_manager,
        task_manager=task_manager,
        config_manager=config_manager,
        file_manager=None,
        monitor=None,
    )
    token = token_manager.generate(user_id=1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac, app, token


@pytest_asyncio.fixture
async def unauthenticated_client(token_manager, task_manager, config_manager):
    """提供未认证的测试客户端。"""
    app = create_app(
        token_manager=token_manager,
        task_manager=task_manager,
        config_manager=config_manager,
        file_manager=None,
        monitor=None,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, app


# ==================== 认证测试 ====================


class TestAuthEndpoints:
    """认证端点测试。"""

    @pytest.mark.asyncio
    async def test_get_token_status(self, client):
        """测试获取 Token 状态。"""
        ac, app, token = client
        resp = await ac.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["valid"] is True

    @pytest.mark.asyncio
    async def test_refresh_token(self, client):
        """测试刷新 Token。"""
        ac, app, token = client
        resp = await ac.post("/api/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "token" in data["data"]
        assert data["data"]["token"] != token

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, unauthenticated_client):
        """测试无效 Token 刷新。"""
        ac, app = unauthenticated_client
        ac.headers.update({"Authorization": "Bearer invalid_token_xyz"})
        resp = await ac.post("/api/auth/refresh")
        assert resp.status_code == 401


# ==================== 认证中间件测试 ====================


class TestAuthenticationMiddleware:
    """Token 认证测试。"""

    @pytest.mark.asyncio
    async def test_unauthenticated_request(self, unauthenticated_client):
        """测试未认证请求返回 401。"""
        ac, app = unauthenticated_client
        resp = await ac.get("/api/tasks")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_token_header(self, unauthenticated_client):
        """测试缺少 Token 头返回 401。"""
        ac, app = unauthenticated_client
        resp = await ac.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token(self, unauthenticated_client):
        """测试过期 Token 返回 401。"""
        ac, app = unauthenticated_client
        # 使用已撤销的 Token
        tm = app.state.token_manager
        expired_token = tm.generate(user_id=1)
        tm.revoke(expired_token)
        ac.headers.update({"Authorization": f"Bearer {expired_token}"})
        resp = await ac.get("/api/tasks")
        assert resp.status_code == 401


# ==================== 任务路由测试 ====================


class TestTaskEndpoints:
    """任务管理端点测试。"""

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client):
        """测试空任务列表。"""
        ac, app, token = client
        resp = await ac.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_create_download_task(self, client):
        """测试创建下载任务。"""
        ac, app, token = client
        body = {
            "task_type": "download",
            "params": {
                "chat_id": "-1001234567890",
                "range_mode": "id_range",
                "min_id": 100,
                "max_id": 500,
                "download_type": ["video", "photo"],
            },
        }
        resp = await ac.post("/api/tasks", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["task_type"] == "download"
        assert data["data"]["status"] == "pending"
        assert data["data"]["id"].startswith("task_")

    @pytest.mark.asyncio
    async def test_create_upload_task(self, client):
        """测试创建上传任务。"""
        ac, app, token = client
        body = {
            "task_type": "upload",
            "params": {
                "file_paths": ["/tmp/test.mp4"],
                "target_chat": "-1001234567890",
            },
        }
        resp = await ac.post("/api/tasks", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["data"]["task_type"] == "upload"

    @pytest.mark.asyncio
    async def test_create_task_size_exceeded(self, client):
        """测试创建超过大小限制的任务。"""
        ac, app, token = client
        body = {
            "task_type": "download",
            "params": {
                "chat_id": "-1001234567890",
                "estimated_size": 15 * 1024 * 1024 * 1024,  # 15GB
            },
        }
        resp = await ac.post("/api/tasks", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data["code"] == 1001

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, client):
        """测试通过 ID 获取任务。"""
        ac, app, token = client
        # 先创建任务
        body = {
            "task_type": "download",
            "params": {"chat_id": "-1001234567890"},
        }
        create_resp = await ac.post("/api/tasks", json=body)
        task_id = create_resp.json()["data"]["id"]

        # 获取任务
        resp = await ac.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["id"] == task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client):
        """测试获取不存在的任务。"""
        ac, app, token = client
        resp = await ac.get("/api/tasks/nonexistent_task")
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == 404

    @pytest.mark.asyncio
    async def test_start_task(self, client):
        """测试启动任务。"""
        ac, app, token = client
        body = {
            "task_type": "download",
            "params": {"chat_id": "-1001234567890"},
        }
        create_resp = await ac.post("/api/tasks", json=body)
        task_id = create_resp.json()["data"]["id"]

        resp = await ac.post(f"/api/tasks/{task_id}/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] in ("running", "queued")

    @pytest.mark.asyncio
    async def test_cancel_task(self, client):
        """测试取消任务。"""
        ac, app, token = client
        body = {
            "task_type": "download",
            "params": {"chat_id": "-1001234567890"},
        }
        create_resp = await ac.post("/api/tasks", json=body)
        task_id = create_resp.json()["data"]["id"]

        # 先启动
        await ac.post(f"/api/tasks/{task_id}/start")

        # 再取消
        resp = await ac.post(f"/api/tasks/{task_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, client):
        """测试取消不存在的任务。"""
        ac, app, token = client
        resp = await ac.post("/api/tasks/nonexistent/cancel")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_failed_task(self, client):
        """测试重试失败任务。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        # 创建并标记为失败
        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        await task_manager.start_task(task.task_id)
        await task_manager.fail_task(task.task_id, reason="测试失败")

        # 重试
        resp = await ac.post(f"/api/tasks/{task.task_id}/retry")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_delete_completed_task(self, client):
        """测试删除已完成任务。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        await task_manager.start_task(task.task_id)
        await task_manager.complete_task(task.task_id)

        resp = await ac.delete(f"/api/tasks/{task.task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "任务记录已删除"

    @pytest.mark.asyncio
    async def test_delete_running_task_raises(self, client):
        """测试删除运行中任务失败。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        await task_manager.start_task(task.task_id)

        resp = await ac.delete(f"/api/tasks/{task.task_id}")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, client):
        """测试按状态过滤任务列表。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        await task_manager.start_task(task.task_id)
        await task_manager.complete_task(task.task_id)

        resp = await ac.get("/api/tasks?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_tasks_with_invalid_status(self, client):
        """测试无效状态过滤。"""
        ac, app, token = client
        resp = await ac.get("/api/tasks?status=invalid_status")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, client):
        """测试任务列表分页。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        for _ in range(5):
            await task_manager.create_task(
                task_type=TaskType.DOWNLOAD,
                chat_id=-1001234567890,
            )

        resp = await ac.get("/api/tasks?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["limit"] == 2
        assert data["data"]["offset"] == 0
        assert len(data["data"]["items"]) <= 2


# ==================== 频道路由测试 ====================


class TestChatEndpoints:
    """频道端点测试。"""

    @pytest.mark.asyncio
    async def test_list_chats(self, client):
        """测试获取频道列表。"""
        ac, app, token = client
        resp = await ac.get("/api/chats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_estimate_messages(self, client):
        """测试消息估算。"""
        ac, app, token = client
        body = {
            "range_mode": "id_range",
            "min_id": 100,
            "max_id": 500,
            "download_type": ["video", "photo"],
        }
        resp = await ac.post("/api/chats/chat_1/messages/estimate", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["message_count"] > 0
        assert data["data"]["sampled"] is True

    @pytest.mark.asyncio
    async def test_analyze_messages(self, client):
        """测试消息精确分析。"""
        ac, app, token = client
        body = {
            "range_mode": "id_range",
            "min_id": 100,
            "max_id": 500,
        }
        resp = await ac.post("/api/chats/chat_1/messages/analyze", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["sampled"] is False


# ==================== 文件路由测试 ====================


class TestFileEndpoints:
    """文件端点测试。"""

    @pytest.mark.asyncio
    async def test_list_files(self, client):
        """测试获取文件列表。"""
        ac, app, token = client
        resp = await ac.get("/api/files")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "path" in data["data"]
        assert "items" in data["data"]

    @pytest.mark.asyncio
    async def test_list_files_with_path(self, client):
        """测试指定路径获取文件列表。"""
        ac, app, token = client
        resp = await ac.get(f"/api/files?path={tempfile.gettempdir()}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["path"] == os.path.abspath(tempfile.gettempdir())

    @pytest.mark.asyncio
    async def test_list_files_nonexistent_path(self, client):
        """测试不存在路径返回空列表。"""
        ac, app, token = client
        resp = await ac.get("/api/files?path=/nonexistent/path/xyz123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []


# ==================== 配置路由测试 ====================


class TestConfigEndpoints:
    """配置端点测试。"""

    @pytest.mark.asyncio
    async def test_get_config(self, client):
        """测试获取配置。"""
        ac, app, token = client
        resp = await ac.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["api_id"] == "12345"
        assert "resource_limits" in data["data"]
        assert "proxy" in data["data"]

    @pytest.mark.asyncio
    async def test_update_config(self, client):
        """测试更新配置。"""
        ac, app, token = client
        body = {
            "download_type": ["video", "photo", "document"],
            "max_retry_count": 5,
        }
        resp = await ac.put("/api/config", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    @pytest.mark.asyncio
    async def test_update_config_resource_limits(self, client):
        """测试更新资源限制配置。"""
        ac, app, token = client
        body = {
            "resource_limits": {
                "max_concurrent_tasks": 2,
                "max_download_concurrency": 5,
                "max_upload_concurrency": 2,
                "task_size_warning_gb": 3,
                "task_size_max_gb": 8,
            },
        }
        resp = await ac.put("/api/config", json=body)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_config_invalid_limits(self, client):
        """测试无效资源限制（max < warning）。"""
        ac, app, token = client
        body = {
            "resource_limits": {
                "task_size_warning_gb": 10,
                "task_size_max_gb": 5,
            },
        }
        resp = await ac.put("/api/config", json=body)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_config_proxy(self, client):
        """测试更新代理配置。"""
        ac, app, token = client
        body = {
            "proxy": {
                "enable_proxy": True,
                "scheme": "socks5",
                "hostname": "127.0.0.1",
                "port": 1080,
            },
        }
        resp = await ac.put("/api/config", json=body)
        assert resp.status_code == 200


# ==================== Pydantic 模型测试 ====================


class TestPydanticModels:
    """Pydantic 数据模型测试。"""

    def test_api_response_default(self):
        """测试 APIResponse 默认值。"""
        from module.api.models.common import APIResponse
        resp = APIResponse()
        assert resp.code == 0
        assert resp.message == "success"
        assert resp.data is None

    def test_api_response_with_data(self):
        """测试带数据的 APIResponse。"""
        from module.api.models.common import APIResponse
        resp = APIResponse(data={"key": "value"}, message="custom")
        assert resp.code == 0
        assert resp.message == "custom"
        assert resp.data == {"key": "value"}

    def test_pagination_params_default(self):
        """测试分页参数默认值。"""
        from module.api.models.common import PaginationParams
        params = PaginationParams()
        assert params.limit == 20
        assert params.offset == 0

    def test_task_create(self):
        """测试 TaskCreate 模型。"""
        from module.api.models.task import TaskCreate
        task = TaskCreate(task_type="download", params={"chat_id": "123"})
        assert task.task_type == "download"
        assert task.params["chat_id"] == "123"

    def test_task_out(self):
        """测试 TaskOut 模型。"""
        from module.api.models.task import TaskOut
        out = TaskOut(
            id="task_001",
            task_type="download",
            status="running",
            progress=50.0,
        )
        assert out.id == "task_001"
        assert out.progress == 50.0

    def test_chat_out(self):
        """测试 ChatOut 模型。"""
        from module.api.models.chat import ChatOut
        chat = ChatOut(id="1", title="Test", type="channel")
        assert chat.title == "Test"
        assert chat.type == "channel"

    def test_file_info(self):
        """测试 FileInfo 模型。"""
        from module.api.models.file import FileInfo
        info = FileInfo(name="test.mp4", path="/tmp/test.mp4", type="file", size=1024)
        assert info.type == "file"
        assert info.size == 1024

    def test_config_out(self):
        """测试 ConfigOut 模型。"""
        from module.api.models.config import ConfigOut
        config = ConfigOut(api_id="123")
        assert config.api_id == "123"
        assert config.resource_limits is not None
        assert config.proxy is not None

    def test_message_estimate_out(self):
        """测试 MessageEstimateOut 模型。"""
        from module.api.models.chat import MessageEstimateOut
        estimate = MessageEstimateOut(
            message_count=100,
            total_size_bytes=1024,
            total_size_human="1 KB",
            estimated_duration_seconds=10,
            sampled=True,
        )
        assert estimate.message_count == 100
        assert estimate.sampled is True

    def test_config_update(self):
        """测试 ConfigUpdate 模型。"""
        from module.api.models.config import ConfigUpdate
        update = ConfigUpdate(max_retry_count=5)
        assert update.max_retry_count == 5
        assert update.resource_limits is None


# ==================== 异常处理测试 ====================


class TestExceptionHandlers:
    """异常处理器测试。"""

    @pytest.mark.asyncio
    async def test_business_exception(self, client):
        """测试业务异常处理。"""
        ac, app, token = client
        resp = await ac.get("/api/tasks/nonexistent_task")
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == 404

    @pytest.mark.asyncio
    async def test_validation_error(self, client):
        """测试参数校验错误。"""
        ac, app, token = client
        # 发送无效的 JSON body
        resp = await ac.post("/api/tasks", json={"invalid_field": "value"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["code"] == 422


# ==================== 响应格式测试 ====================


class TestResponseFormat:
    """统一响应格式测试。"""

    def test_success_response(self):
        """测试成功响应构造。"""
        from module.api.responses import success_response
        resp = success_response(data={"key": "value"})
        assert resp["code"] == 0
        assert resp["message"] == "success"
        assert resp["data"] == {"key": "value"}

    def test_error_response(self):
        """测试错误响应构造。"""
        from module.api.responses import error_response
        resp = error_response(code=1001, message="错误消息")
        assert resp["code"] == 1001
        assert resp["message"] == "错误消息"
        assert resp["data"] is None

    def test_json_response(self):
        """测试 JSONResponse 构造。"""
        from module.api.responses import json_response
        resp = json_response(data={"test": True})
        assert resp.status_code == 200
        assert resp.body is not None

    def test_error_json_response(self):
        """测试错误 JSONResponse 构造。"""
        from module.api.responses import error_json_response
        resp = error_json_response(code=500, message="内部错误", status_code=500)
        assert resp.status_code == 500


# ==================== 依赖注入测试 ====================


class TestDependencies:
    """依赖注入测试。"""

    @pytest.mark.asyncio
    async def test_require_token_from_header(self, client):
        """测试从 Header 获取 Token。"""
        ac, app, token = client
        resp = await ac.get("/api/auth/me")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_require_token_from_query(self, token_manager, task_manager, config_manager):
        """测试从 Query 参数获取 Token。"""
        app = create_app(
            token_manager=token_manager,
            task_manager=task_manager,
            config_manager=config_manager,
        )
        token = token_manager.generate(user_id=1)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/tasks?token={token}")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_require_token_missing(self, unauthenticated_client):
        """测试缺少 Token 返回 401。"""
        ac, app = unauthenticated_client
        resp = await ac.get("/api/tasks")
        assert resp.status_code == 401
        data = resp.json()
        assert data["detail"] == "MISSING_TOKEN"

    @pytest.mark.asyncio
    async def test_require_token_invalid(self, unauthenticated_client):
        """测试无效 Token 返回 401。"""
        ac, app = unauthenticated_client
        ac.headers.update({"Authorization": "Bearer invalid_token"})
        resp = await ac.get("/api/tasks")
        assert resp.status_code == 401


# ==================== WebSocket 测试 ====================


class TestWebSocketConnection:
    """WebSocket 连接测试。"""

    @pytest.mark.asyncio
    async def test_connection_manager_connect_disconnect(self):
        """测试连接管理器连接/断开。"""
        from module.api.websocket.connection import ConnectionManager
        manager = ConnectionManager()
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self):
        """测试广播功能（无连接时不报错）。"""
        from module.api.websocket.connection import ConnectionManager
        manager = ConnectionManager()
        await manager.broadcast({"type": "test"})

    @pytest.mark.asyncio
    async def test_connection_manager_send_to_nonexistent(self):
        """测试向不存在客户端发送返回 False。"""
        from module.api.websocket.connection import ConnectionManager
        manager = ConnectionManager()
        result = await manager.send_to("nonexistent", {"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_manager_get_count(self):
        """测试获取连接数。"""
        from module.api.websocket.connection import ConnectionManager
        manager = ConnectionManager()
        assert manager.get_connection_count() == 0


# ==================== 中间件测试 ====================


class TestMiddleware:
    """中间件测试。"""

    def test_security_headers_middleware(self):
        """测试安全头中间件初始化。"""
        from module.api.middleware import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware.SECURITY_HEADERS is not None
        assert "X-Content-Type-Options" in SecurityHeadersMiddleware.SECURITY_HEADERS

    def test_process_time_middleware(self):
        """测试响应时间中间件初始化。"""
        from module.api.middleware import ProcessTimeMiddleware
        assert ProcessTimeMiddleware.THRESHOLD_MS == 1000


# ==================== 应用工厂测试 ====================


class TestAppFactory:
    """应用工厂测试。"""

    def test_create_app_with_defaults(self):
        """测试使用默认参数创建应用。"""
        app = create_app()
        assert app.title == "TRMD Web API"
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.state.token_manager is not None

    def test_create_app_with_mocks(self, token_manager, task_manager, config_manager):
        """测试注入 Mock 依赖创建应用。"""
        app = create_app(
            token_manager=token_manager,
            task_manager=task_manager,
            config_manager=config_manager,
        )
        assert app.state.token_manager == token_manager
        assert app.state.task_manager == task_manager
        assert app.state.config_manager == config_manager


# ==================== 异常类测试 ====================


class TestExceptionClasses:
    """异常类测试。"""

    def test_task_not_found_exception(self):
        """测试 TaskNotFoundError。"""
        from module.api.exceptions import TaskNotFoundError
        exc = TaskNotFoundError("task_123")
        assert exc.code == 404
        assert exc.status_code == 404

    def test_task_size_exceeded_exception(self):
        """测试 TaskSizeExceeded。"""
        from module.api.exceptions import TaskSizeExceeded
        exc = TaskSizeExceeded("12 GB")
        assert exc.code == 1001
        assert "12 GB" in exc.message

    def test_task_size_warning_exception(self):
        """测试 TaskSizeWarning。"""
        from module.api.exceptions import TaskSizeWarning
        exc = TaskSizeWarning("7 GB")
        assert exc.code == 1002
        assert "7 GB" in exc.message

    def test_insufficient_disk_space_exception(self):
        """测试 InsufficientDiskSpace。"""
        from module.api.exceptions import InsufficientDiskSpace
        exc = InsufficientDiskSpace()
        assert exc.code == 1003

    def test_task_conflict_exception(self):
        """测试 TaskConflictError。"""
        from module.api.exceptions import TaskConflictError
        exc = TaskConflictError("自定义冲突消息")
        assert exc.code == 409
        assert exc.status_code == 409

    def test_chat_not_found_exception(self):
        """测试 ChatNotFoundError。"""
        from module.api.exceptions import ChatNotFoundError
        exc = ChatNotFoundError("chat_123")
        assert exc.code == 404


# ==================== 任务路由额外测试 ====================


class TestTaskRouteExtras:
    """任务路由边界测试。"""

    @pytest.mark.asyncio
    async def test_create_task_invalid_type(self, client):
        """测试创建无效类型的任务（Pydantic 校验拦截返回 422）。"""
        ac, app, token = client
        body = {"task_type": "invalid", "params": {}}
        resp = await ac.post("/api/tasks", json=body)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_task_conflict(self, client):
        """测试取消状态冲突的任务。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        await task_manager.start_task(task.task_id)
        await task_manager.complete_task(task.task_id)

        resp = await ac.post(f"/api/tasks/{task.task_id}/cancel")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_retry_task_conflict(self, client):
        """测试重试状态冲突的任务。"""
        ac, app, token = client
        task_manager = app.state.task_manager

        task = await task_manager.create_task(
            task_type=TaskType.DOWNLOAD,
            chat_id=-1001234567890,
        )
        # pending 状态不能重试（只能 failed/cancelled）
        resp = await ac.post(f"/api/tasks/{task.task_id}/retry")
        assert resp.status_code == 409


# ==================== WebSocket push 函数测试 ====================


class TestWebSocketPushFunctions:
    """WebSocket 推送函数测试。"""

    @pytest.mark.asyncio
    async def test_push_task_update(self):
        """测试 push_task_update 不报错。"""
        from module.api.websocket.router import push_task_update
        await push_task_update("task_1", "running", 50.0, "测试中")

    @pytest.mark.asyncio
    async def test_push_log(self):
        """测试 push_log 不报错。"""
        from module.api.websocket.router import push_log
        await push_log("INFO", "test_logger", "测试日志")
