# coding=UTF-8
"""WebSocket 连接管理器。

负责管理 WebSocket 连接生命周期、广播消息、心跳等。
"""

import asyncio
import logging
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器。

    管理多个 WebSocket 客户端连接，支持广播和单播。
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self._heartbeat_timeouts: Dict[str, float] = {}
        self._heartbeat_interval = 30  # 心跳间隔（秒）

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """接受并注册 WebSocket 连接。

        :param websocket: WebSocket 实例
        :param client_id: 客户端唯一标识
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self._heartbeat_timeouts[client_id] = self._heartbeat_interval
        logger.info("WebSocket 连接已建立: %s", client_id)

    async def disconnect(self, client_id: str) -> None:
        """断开并移除 WebSocket 连接。

        :param client_id: 客户端唯一标识
        """
        self.active_connections.pop(client_id, None)
        self._heartbeat_timeouts.pop(client_id, None)
        logger.info("WebSocket 连接已断开: %s", client_id)

    async def broadcast(self, message: dict) -> None:
        """向所有客户端广播消息。

        :param message: JSON 消息字典
        """
        disconnected = []
        for client_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("广播消息失败 [%s]: %s", client_id, e)
                disconnected.append(client_id)

        # 清理断开的连接
        for client_id in disconnected:
            await self.disconnect(client_id)

    async def send_to(self, client_id: str, message: dict) -> bool:
        """向指定客户端发送消息。

        :param client_id: 客户端唯一标识
        :param message: JSON 消息字典
        :return: 发送是否成功
        """
        ws = self.active_connections.get(client_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as e:
            logger.warning("发送消息失败 [%s]: %s", client_id, e)
            await self.disconnect(client_id)
            return False

    async def handle_heartbeat(self, client_id: str) -> None:
        """处理客户端心跳。

        :param client_id: 客户端唯一标识
        """
        self._heartbeat_timeouts[client_id] = self._heartbeat_interval

    def get_connection_count(self) -> int:
        """获取当前活跃连接数。"""
        return len(self.active_connections)


# 全局连接管理器实例
manager = ConnectionManager()
