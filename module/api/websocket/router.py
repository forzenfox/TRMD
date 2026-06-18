# coding=UTF-8
"""WebSocket 路由。

注册任务状态、监控、日志推送的 WebSocket 端点。
"""

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from module.api.websocket.connection import ConnectionManager
from module.core.token_manager import TokenManager

websocket_router = APIRouter(tags=["WebSocket"])

# 全局连接管理器
ws_manager = ConnectionManager()


async def _validate_token(token_manager: TokenManager, token: str) -> bool:
    """校验 WebSocket Token。"""
    return token_manager.is_valid(token)


def _now_iso() -> str:
    """获取当前 ISO 8601 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


@websocket_router.websocket("/ws/tasks")
async def websocket_tasks(websocket: WebSocket, token: str = Query(...)):
    """任务状态推送 WebSocket。

    客户端连接后接收任务状态变更通知。
    """
    client_id = f"tasks_{uuid.uuid4().hex[:8]}"

    # 校验 Token
    token_manager: TokenManager = websocket.app.state.token_manager
    if not await _validate_token(token_manager, token):
        await websocket.close(code=1008, reason="INVALID_TOKEN")
        return

    await ws_manager.connect(websocket, client_id)

    # 发送连接成功消息
    await websocket.send_json({
        "type": "connected",
        "timestamp": _now_iso(),
        "payload": {"client_id": client_id},
    })

    try:
        while True:
            # 等待客户端消息（心跳等）
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await ws_manager.handle_heartbeat(client_id)
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": _now_iso(),
                    "payload": {},
                })
    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
    except Exception as e:
        await ws_manager.disconnect(client_id)


@websocket_router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket, token: str = Query(...)):
    """监控数据推送 WebSocket。

    定期推送系统资源使用情况。
    """
    client_id = f"monitor_{uuid.uuid4().hex[:8]}"

    token_manager: TokenManager = websocket.app.state.token_manager
    if not await _validate_token(token_manager, token):
        await websocket.close(code=1008, reason="INVALID_TOKEN")
        return

    await ws_manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await ws_manager.handle_heartbeat(client_id)
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": _now_iso(),
                    "payload": {},
                })
    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
    except Exception:
        await ws_manager.disconnect(client_id)


@websocket_router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, token: str = Query(...)):
    """日志流推送 WebSocket。

    实时推送结构化日志。
    """
    client_id = f"logs_{uuid.uuid4().hex[:8]}"

    token_manager: TokenManager = websocket.app.state.token_manager
    if not await _validate_token(token_manager, token):
        await websocket.close(code=1008, reason="INVALID_TOKEN")
        return

    await ws_manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await ws_manager.handle_heartbeat(client_id)
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": _now_iso(),
                    "payload": {},
                })
    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
    except Exception:
        await ws_manager.disconnect(client_id)


# ==================== 推送辅助函数 ====================


async def push_task_update(task_id: str, status: str, progress: float, message: str = "") -> None:
    """推送任务状态更新。

    :param task_id: 任务 ID
    :param status: 任务状态
    :param progress: 进度百分比
    :param message: 状态消息
    """
    await ws_manager.broadcast({
        "type": "task_update",
        "timestamp": _now_iso(),
        "payload": {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
        },
    })


async def push_log(level: str, logger_name: str, message: str) -> None:
    """推送日志消息。

    :param level: 日志级别
    :param logger_name: 日志器名称
    :param message: 日志内容
    """
    await ws_manager.broadcast({
        "type": "log",
        "timestamp": _now_iso(),
        "payload": {
            "level": level,
            "logger": logger_name,
            "message": message,
        },
    })
