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

    定期推送系统资源使用情况（CPU、内存、磁盘、任务统计）。
    """
    import psutil
    from module.core.task_manager import TaskManager

    client_id = f"monitor_{uuid.uuid4().hex[:8]}"

    token_manager: TokenManager = websocket.app.state.token_manager
    if not await _validate_token(token_manager, token):
        await websocket.close(code=1008, reason="INVALID_TOKEN")
        return

    await ws_manager.connect(websocket, client_id)

    # 发送初始监控数据
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # 获取任务统计
        task_manager: TaskManager = getattr(websocket.app.state, "task_manager", None)
        task_stats = {}
        if task_manager:
            tasks = task_manager.list_tasks()
            task_stats = {
                "total": len(tasks),
                "running": sum(1 for t in tasks if t.status.value == "running"),
                "pending": sum(1 for t in tasks if t.status.value == "pending"),
                "completed": sum(1 for t in tasks if t.status.value == "completed"),
                "failed": sum(1 for t in tasks if t.status.value == "failed"),
            }

        await websocket.send_json({
            "type": "monitor_data",
            "timestamp": _now_iso(),
            "payload": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
                "task_stats": task_stats,
            },
        })
    except ImportError:
        # psutil 未安装时返回基础信息
        await websocket.send_json({
            "type": "monitor_data",
            "timestamp": _now_iso(),
            "payload": {"error": "psutil not installed"},
        })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await ws_manager.handle_heartbeat(client_id)
                # 推送最新监控数据
                try:
                    cpu_percent = psutil.cpu_percent(interval=None)
                    memory = psutil.virtual_memory()
                    await websocket.send_json({
                        "type": "monitor_data",
                        "timestamp": _now_iso(),
                        "payload": {
                            "cpu_percent": cpu_percent,
                            "memory_percent": memory.percent,
                        },
                    })
                except ImportError:
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

    # 获取日志处理器和订阅级别
    from module.api.websocket.log_handler import get_log_handler, LogSubscription
    import logging

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    log_handler = get_log_handler()
    min_level = logging.INFO  # 默认 INFO 级别

    # 创建日志订阅
    subscription = LogSubscription(websocket, min_level=min_level)
    log_handler.add_subscription(client_id, subscription)

    # 发送连接成功消息
    await websocket.send_json({
        "type": "log_connected",
        "timestamp": _now_iso(),
        "payload": {"client_id": client_id, "min_level": "INFO"},
    })

    # 启动日志推送任务
    log_task = asyncio.create_task(subscription.start())

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
            elif msg_type == "set_level":
                # 动态设置日志级别
                new_level = data.get("level", "INFO")
                if new_level in level_map:
                    subscription.min_level = level_map[new_level]
                    await websocket.send_json({
                        "type": "level_changed",
                        "timestamp": _now_iso(),
                        "payload": {"level": new_level},
                    })
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        subscription.stop()
        log_task.cancel()
        log_handler.remove_subscription(client_id)
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
