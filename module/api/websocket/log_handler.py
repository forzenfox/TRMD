# coding=UTF-8
"""WebSocket 日志推送处理器。

自定义 logging.Handler，将日志记录推送到 WebSocket 连接池。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional


class WebSocketLogHandler(logging.Handler):
    """WebSocket 日志处理器。

    将 Python logging 记录推送到已连接的 WebSocket 客户端。
    支持按级别过滤。
    """

    def __init__(self, level: int = logging.INFO):
        super().__init__(level)
        self._connections: dict[str, "LogSubscription"] = {}

    def emit(self, record: logging.LogRecord):
        """处理日志记录并推送到所有已订阅的 WebSocket 连接。"""
        try:
            log_entry = {
                "type": "log_entry",
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "payload": {
                    "level": record.levelname,
                    "level_no": record.levelno,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "funcName": record.funcName,
                    "lineno": record.lineno,
                },
            }

            # 推送到所有已订阅的连接
            for client_id, subscription in list(self._connections.items()):
                if record.levelno >= subscription.min_level:
                    asyncio.create_task(subscription.send_log(log_entry))

        except Exception:
            # 日志处理器不应抛出异常
            self.handleError(record)

    def add_subscription(self, client_id: str, subscription: "LogSubscription"):
        """添加 WebSocket 连接订阅。"""
        self._connections[client_id] = subscription

    def remove_subscription(self, client_id: str):
        """移除 WebSocket 连接订阅。"""
        self._connections.pop(client_id, None)

    @property
    def subscriber_count(self) -> int:
        """当前订阅者数量。"""
        return len(self._connections)


class LogSubscription:
    """单个 WebSocket 日志订阅。"""

    def __init__(self, websocket, min_level: int = logging.INFO):
        self.websocket = websocket
        self.min_level = min_level
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def send_log(self, log_entry: dict):
        """将日志记录放入发送队列。"""
        try:
            await self._queue.put(log_entry)
        except Exception:
            pass

    async def start(self):
        """开始从队列中读取并推送日志。"""
        self._running = True
        while self._running:
            try:
                log_entry = await asyncio.wait_for(self._queue.get(), timeout=30)
                await self.websocket.send_json(log_entry)
            except asyncio.TimeoutError:
                # 超时发送心跳
                try:
                    await self.websocket.send_json({
                        "type": "log_heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    break
            except Exception:
                break

    def stop(self):
        """停止推送。"""
        self._running = False


# 全局日志处理器实例
websocket_log_handler: Optional[WebSocketLogHandler] = None


def get_log_handler() -> WebSocketLogHandler:
    """获取或创建全局 WebSocket 日志处理器。"""
    global websocket_log_handler
    if websocket_log_handler is None:
        websocket_log_handler = WebSocketLogHandler(level=logging.INFO)
        # 添加到 root logger
        logging.getLogger().addHandler(websocket_log_handler)
    return websocket_log_handler
