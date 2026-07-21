# coding=UTF-8
"""ClientManager - Telegram Client 连接管理模块

提供自动重连和手动重连机制,确保 Telegram Client 的持续可用性。
"""

import asyncio
import logging
import time
from typing import Optional

from pyrogram.errors import (
    AuthKeyUnregistered,
    SessionExpired,
    SessionRevoked,
    Unauthorized,
)

log = logging.getLogger(__name__)


class ClientManager:
    """Telegram Client 连接管理器

    职责:
    - 检测 client 连接状态
    - 自动重连(指数退避策略)
    - 提供手动重连接口
    - 记录重连日志和状态
    - 处理认证失败等不可恢复错误
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: int = 5,
        cooldown: int = 30,
        health_check_interval: int = 30,
    ):
        """初始化 ClientManager

        Args:
            max_retries: 最大自动重试次数(默认3次)
            base_delay: 基础延迟秒数(默认5秒,指数退避: 5s, 10s, 20s)
            cooldown: 自动重连冷却期(秒),防止频繁重试(默认30秒)
            health_check_interval: 健康检查间隔(秒,默认30秒)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.cooldown = cooldown
        self.health_check_interval = health_check_interval
        self.reconnect_count = 0
        self.is_reconnecting = False
        self.last_reconnect_attempt: Optional[float] = None
        self.manual_reconnect_required = False
        self.auth_failed = False  # 认证失败标记,不可恢复
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._client_ref: Optional[object] = None  # 弱引用 client

        log.info(
            f"ClientManager 已初始化: max_retries={max_retries}, "
            f"base_delay={base_delay}s, cooldown={cooldown}s, "
            f"health_check_interval={health_check_interval}s"
        )

    async def check_and_reconnect(self, client) -> dict:
        """检查连接状态,断线时自动重连

        Args:
            client: Pyrogram Client 实例

        Returns:
            dict: 包含重连状态信息
            {
                "connected": bool,
                "is_reconnecting": bool,
                "reconnect_count": int,
                "manual_required": bool,
                "message": str
            }
        """
        if client is None:
            return {
                "connected": False,
                "is_reconnecting": False,
                "reconnect_count": 0,
                "manual_required": True,
                "message": "Client 未初始化",
            }

        # 认证失败,不可恢复
        if self.auth_failed:
            return {
                "connected": False,
                "is_reconnecting": False,
                "reconnect_count": self.reconnect_count,
                "manual_required": True,
                "message": "认证失败,需要重新登录",
            }

        # 检查连接状态
        try:
            is_connected = getattr(client, "is_connected", False)
        except Exception as e:
            log.warning(f"检查连接状态失败: {e}")
            is_connected = False

        if is_connected:
            # 连接正常,重置重连计数
            if self.reconnect_count > 0:
                log.info("Client 连接已恢复,重置重连计数")
                self.reconnect_count = 0
                self.manual_reconnect_required = False

            return {
                "connected": True,
                "is_reconnecting": False,
                "reconnect_count": 0,
                "manual_required": False,
                "message": "连接正常",
            }

        # 连接断开,检查是否在冷却期
        if self.last_reconnect_attempt is not None:
            elapsed = time.time() - self.last_reconnect_attempt
            if elapsed < self.cooldown:
                return {
                    "connected": False,
                    "is_reconnecting": False,
                    "reconnect_count": self.reconnect_count,
                    "manual_required": self.manual_reconnect_required,
                    "message": f"冷却期内({int(self.cooldown - elapsed)}秒后可重试)",
                }

        # 连接断开,尝试自动重连
        if self.is_reconnecting:
            return {
                "connected": False,
                "is_reconnecting": True,
                "reconnect_count": self.reconnect_count,
                "manual_required": self.manual_reconnect_required,
                "message": f"正在重连中(第{self.reconnect_count}次)",
            }

        # 检查是否已超过最大重试次数
        if self.reconnect_count >= self.max_retries:
            self.manual_reconnect_required = True
            return {
                "connected": False,
                "is_reconnecting": False,
                "reconnect_count": self.reconnect_count,
                "manual_required": True,
                "message": f"自动重连失败({self.reconnect_count}次),请手动重连",
            }

        # 执行自动重连
        return await self._attempt_reconnect(client, auto=True)

    async def manual_reconnect(self, client) -> dict:
        """手动触发重连

        Args:
            client: Pyrogram Client 实例

        Returns:
            dict: 重连结果
        """
        if client is None:
            return {"success": False, "message": "Client 未初始化"}

        # 认证失败,不可恢复
        if self.auth_failed:
            return {"success": False, "message": "认证失败,需要重新登录"}

        # 重置手动重连标记
        self.manual_reconnect_required = False

        # 执行重连
        result = await self._attempt_reconnect(client, auto=False)

        if result["connected"]:
            # 重连成功,重置计数
            self.reconnect_count = 0
            self.manual_reconnect_required = False

        return result

    async def _attempt_reconnect(self, client, auto: bool = True) -> dict:
        """尝试重连

        Pyrogram Client 重连流程:
        1. 先 disconnect() 清理残留连接状态
        2. 等待短暂间隔确保资源释放
        3. 调用 connect() 建立新连接
        4. 验证 is_connected 确认成功

        Args:
            client: Pyrogram Client 实例
            auto: 是否为自动重连(True)或手动重连(False)

        Returns:
            dict: 重连结果
        """
        if self.is_reconnecting:
            return {
                "connected": False,
                "is_reconnecting": True,
                "reconnect_count": self.reconnect_count,
                "manual_required": self.manual_reconnect_required,
                "message": "重连已在进行中",
            }

        self.is_reconnecting = True
        self.last_reconnect_attempt = time.time()

        if auto:
            self.reconnect_count += 1

        mode_str = "自动" if auto else "手动"
        log.info(f"开始{mode_str}重连(第{self.reconnect_count}次)")

        try:
            # 步骤1: 先断开残留连接,清理底层 session 状态
            try:
                if getattr(client, "is_connected", False):
                    await client.disconnect()
                    log.debug("已断开残留连接")
            except Exception as e:
                # disconnect 失败不影响后续重连,仅记录
                log.debug(f"断开残留连接时出错(可忽略): {e}")

            # 步骤2: 等待底层资源释放(TCP socket、session 等)
            await asyncio.sleep(1)

            # 步骤3: 建立新连接
            # Pyrogram Client.connect() 会复用已有的 auth_key 和 session,
            # 不需要重新登录,只是重建 TCP 连接和 session 通道
            await client.connect()

            # 步骤4: 短暂等待后验证连接状态
            await asyncio.sleep(0.5)
            is_connected = getattr(client, "is_connected", False)

            if not is_connected:
                raise ConnectionError("connect() 后 is_connected 仍为 False")

            log.info(f"{mode_str}重连成功")
            self.is_reconnecting = False
            self.reconnect_count = 0
            self.manual_reconnect_required = False

            return {
                "connected": True,
                "is_reconnecting": False,
                "reconnect_count": 0,
                "manual_required": False,
                "message": "重连成功",
            }

        except (AuthKeyUnregistered, SessionExpired, SessionRevoked, Unauthorized) as e:
            # 认证类错误不可恢复,标记后不再自动重试
            log.error(f"{mode_str}重连失败(认证失效,需重新登录): {e}")
            self.auth_failed = True
            self.is_reconnecting = False
            self.manual_reconnect_required = True

            return {
                "connected": False,
                "is_reconnecting": False,
                "reconnect_count": self.reconnect_count,
                "manual_required": True,
                "message": f"认证失效,需要重新登录: {e}",
            }

        except Exception as e:
            log.warning(f"{mode_str}重连失败: {e}")
            self.is_reconnecting = False

            if not auto:
                # 手动重连失败,始终允许再次手动尝试
                return {
                    "connected": False,
                    "is_reconnecting": False,
                    "reconnect_count": self.reconnect_count,
                    "manual_required": True,
                    "message": f"手动重连失败: {e}",
                }

            if self.reconnect_count >= self.max_retries:
                # 自动重连耗尽,转手动
                self.manual_reconnect_required = True
                return {
                    "connected": False,
                    "is_reconnecting": False,
                    "reconnect_count": self.reconnect_count,
                    "manual_required": True,
                    "message": f"自动重连失败({self.reconnect_count}次),请手动重连",
                }

            # 还有重试机会,计算下次退避延迟
            delay = self.base_delay * (2 ** (self.reconnect_count - 1))
            return {
                "connected": False,
                "is_reconnecting": False,
                "reconnect_count": self.reconnect_count,
                "manual_required": False,
                "message": f"重连失败,{delay}秒后重试",
            }

    def get_status(self) -> dict:
        """获取当前重连状态

        Returns:
            dict: 状态信息
        """
        return {
            "is_reconnecting": self.is_reconnecting,
            "reconnect_count": self.reconnect_count,
            "max_retries": self.max_retries,
            "manual_required": self.manual_reconnect_required,
            "auth_failed": self.auth_failed,
            "last_reconnect_attempt": self.last_reconnect_attempt,
        }

    def reset(self):
        """重置重连状态"""
        self.reconnect_count = 0
        self.is_reconnecting = False
        self.manual_reconnect_required = False
        self.auth_failed = False
        self.last_reconnect_attempt = None
        log.info("ClientManager 状态已重置")

    def start_health_check(self, client) -> None:
        """启动后台健康检查循环

        Args:
            client: Pyrogram Client 实例
        """
        if self._health_check_task is not None:
            log.warning("健康检查已在运行")
            return

        self._client_ref = client
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        log.info(f"健康检查已启动(间隔 {self.health_check_interval}s)")

    def stop_health_check(self) -> None:
        """停止后台健康检查循环"""
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            self._health_check_task = None
            self._client_ref = None
            log.info("健康检查已停止")

    async def _health_check_loop(self) -> None:
        """后台健康检查循环

        定期检查 client 连接状态,断线时自动触发重连。
        """
        try:
            while True:
                await asyncio.sleep(self.health_check_interval)

                if self._client_ref is None:
                    continue

                # 认证失败,不再自动重连
                if self.auth_failed:
                    continue

                # 检查连接状态
                try:
                    is_connected = getattr(self._client_ref, "is_connected", False)
                except Exception as e:
                    log.warning(f"健康检查: 获取连接状态失败: {e}")
                    is_connected = False

                if not is_connected:
                    log.warning("健康检查: 检测到连接断开,触发自动重连")
                    result = await self.check_and_reconnect(self._client_ref)

                    if result["connected"]:
                        log.info("健康检查: 自动重连成功")
                    else:
                        log.warning(f"健康检查: 自动重连失败 - {result['message']}")

        except asyncio.CancelledError:
            log.info("健康检查循环已取消")
            raise
        except Exception as e:
            log.error(f"健康检查循环异常退出: {e}")
