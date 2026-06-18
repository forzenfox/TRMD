# coding=UTF-8
"""Bot 新增命令模块。

实现 M2 阶段的简化 Bot 命令：
- /web：生成 Token 并返回 WebUI 链接
- /batch：简化批量操作模式（通过状态机收集用户输入）
- /status：展示当前任务状态摘要，引导复杂操作到 WebUI
- /cancel：取消当前交互流程

保持与原有 module/bot.py 的兼容性，不修改原有文件。
详见 `docs/module-design-bot-refactor.md`。
"""

import logging
from typing import Optional

from module.core.token_manager import TokenManager
from module.interaction_manager import InteractionManager, BatchStep

logger = logging.getLogger(__name__)

# WebUI 基础 URL 默认值
DEFAULT_WEBUI_URL = "http://localhost:8000"


class BotCommands:
    """新增/重构的 Bot 命令处理器。

    与原有 Bot 类解耦，通过组合 TokenManager 和 InteractionManager
    实现新功能。可独立测试，不与 Pyrogram 客户端紧耦合。
    """

    # 命令定义（命令名, 描述）
    COMMANDS = [
        ("web", "生成 WebUI 访问链接（带一次性 Token）"),
        ("batch", "简化批量操作：转发/下载任务（多步引导）"),
        ("status", "查看当前任务状态摘要（复杂操作请前往 WebUI）"),
        ("cancel", "取消当前正在进行的交互流程"),
    ]

    def __init__(
        self,
        token_manager: TokenManager,
        interaction_manager: InteractionManager,
        webui_base_url: str = DEFAULT_WEBUI_URL,
    ) -> None:
        """
        :param token_manager: Token 管理器实例
        :param interaction_manager: 交互状态管理器实例
        :param webui_base_url: WebUI 基础 URL
        """
        self._token_manager = token_manager
        self._interaction_manager = interaction_manager
        self._webui_base_url = webui_base_url

    # ==================== 公共工具方法 ====================

    def get_webui_link(self, token: str) -> str:
        """生成带 Token 的完整 WebUI 链接。

        :param token: 认证 Token
        :return: 完整 URL
        """
        return f"{self._webui_base_url}?token={token}"

    def get_webui_guidance_text(self) -> str:
        """获取引导用户前往 WebUI 的文案。

        :return: 引导文本
        """
        return (
            "💡 提示：复杂操作建议前往 WebUI 完成\n"
            f"🌐 访问链接：{self._webui_base_url}\n"
            "✨ WebUI 提供更直观的图形界面，支持：\n"
            "  • 批量任务配置与管理\n"
            "  • 实时进度监控\n"
            "  • 高级过滤条件设置\n"
            "  • 任务历史记录查看"
        )

    def get_commands(self) -> list:
        """返回所有新增命令的定义列表。

        :return: [(命令名, 描述), ...]
        """
        return list(self.COMMANDS)

    # ==================== /web 命令 ====================

    async def cmd_web(self, client, message) -> dict:
        """生成 Token 并返回 WebUI 访问链接。

        用户发送 /web 后，系统生成一个带有效期的 Token，
        返回包含该 Token 的 WebUI 访问链接。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: {"token": str, "url": str}
        """
        user_id = message.from_user.id

        # 生成 Token
        token = self._token_manager.generate(user_id=user_id)
        url = self.get_webui_link(token)

        # 构建回复文本
        text = (
            "🌐 WebUI 访问链接已生成\n\n"
            f"🔗 链接：`{url}`\n\n"
            "⏰ 链接有效期：1 小时\n"
            "⚠️ 请勿将此链接分享给他人\n\n"
            f"{self.get_webui_guidance_text()}"
        )

        # 发送消息
        await client.send_message(
            chat_id=user_id,
            text=text,
        )

        logger.info("/web 命令已执行: user_id=%s", user_id)
        return {"token": token, "url": url}

    # ==================== /batch 命令 ====================

    async def cmd_batch(self, client, message) -> Optional[dict]:
        """启动简化批量操作流程。

        通过状态机引导用户逐步输入：
        1. 源频道链接
        2. 目标频道链接
        3. 消息范围
        4. 过滤条件（可选）

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: None 或 流程状态字典
        """
        user_id = message.from_user.id

        # 检查是否已有活跃流程
        if self._interaction_manager.has_active_flow(user_id):
            await client.send_message(
                chat_id=user_id,
                text=(
                    "⚠️ 你已有一个正在进行的批量操作流程\n"
                    "请先完成当前流程或使用 /cancel 取消\n\n"
                    f"{self._interaction_manager.get_step_prompt(user_id)}"
                ),
            )
            return None

        # 启动新流程
        state = self._interaction_manager.start_flow(user_id=user_id, command="/batch")
        prompt = self._interaction_manager.get_step_prompt(user_id)

        text = (
            "📦 批量操作模式已启动\n\n"
            "我将引导你逐步配置批量任务，请按提示输入信息。\n\n"
            f"{prompt}\n\n"
            "💡 输入 /cancel 可随时取消操作"
        )

        await client.send_message(
            chat_id=user_id,
            text=text,
        )

        logger.info("/batch 命令已执行: user_id=%s", user_id)
        return {"state": state.to_dict()}

    async def handle_batch_input(self, client, message) -> Optional[dict]:
        """处理用户在批量操作流程中输入的数据。

        由 Bot 的关键词输入模式或专门的消息处理器调用。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: None 或 处理结果
        """
        user_id = message.from_user.id
        input_text = message.text.strip()

        # 检查是否有活跃流程
        if not self._interaction_manager.has_active_flow(user_id):
            await client.send_message(
                chat_id=user_id,
                text=(
                    "❌ 当前未开始批量操作流程\n"
                    "请先发送 /batch 启动批量操作"
                ),
            )
            return None

        # 收集并验证输入
        result = self._interaction_manager.collect(user_id=user_id, input_text=input_text)

        if result is None:
            return None

        if not result.success:
            # 输入无效，提示重新输入
            await client.send_message(
                chat_id=user_id,
                text=result.message,
            )
            return None

        if result.current_step == BatchStep.COMPLETE:
            # 所有步骤完成
            collected = result.collected_data
            text = (
                "✅ 批量操作配置已完成！\n\n"
                "📋 配置摘要：\n"
                f"  • 源频道：`{collected.get('source_channel', 'N/A')}`\n"
                f"  • 目标频道：`{collected.get('target_channel', 'N/A')}`\n"
                f"  • 消息范围：`{collected.get('message_range', 'N/A')}`\n"
                f"  • 过滤条件：`{collected.get('filter_condition', '无') or '无'}`\n\n"
                f"{self.get_webui_guidance_text()}\n\n"
                "⚡ 任务将在 WebUI 中自动开始执行"
            )
            await client.send_message(
                chat_id=user_id,
                text=text,
            )
            # 清理已完成的流程
            self._interaction_manager.cancel_flow(user_id)
            return {"status": "completed", "data": collected}

        # 步骤推进成功，显示下一步提示
        await client.send_message(
            chat_id=user_id,
            text=result.message,
        )

        state = self._interaction_manager.get_active_flow(user_id)
        return {"status": "in_progress", "step": state.current_step.value if state else None}

    # ==================== /status 命令 ====================

    async def cmd_status(self, client, message) -> dict:
        """展示当前任务状态摘要，引导复杂操作到 WebUI。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: 状态摘要字典
        """
        user_id = message.from_user.id

        # 获取活跃流程
        active_flows = self._interaction_manager.get_all_active_flows()
        user_flow = active_flows.get(user_id)

        # 构建状态文本
        parts = []
        parts.append("📊 当前状态摘要\n")

        if user_flow:
            parts.append(f"🔄 正在进行的批量操作：\n")
            parts.append(f"  • 当前步骤：{BatchStep.get_prompt(user_flow.current_step)}")
            parts.append(f"  • 已收集数据：{len(user_flow.collected_data)} 项\n")
        else:
            parts.append("✅ 当前没有正在进行的交互流程\n")

        # 统计信息
        total_flows = len(active_flows)
        if total_flows > 0:
            parts.append(f"📈 全局活跃流程数：{total_flows}\n")

        # WebUI 引导
        parts.append(f"\n{self.get_webui_guidance_text()}")

        text = "\n".join(parts)

        await client.send_message(
            chat_id=user_id,
            text=text,
        )

        logger.info("/status 命令已执行: user_id=%s", user_id)
        return {
            "user_has_active_flow": user_flow is not None,
            "total_active_flows": total_flows,
        }

    # ==================== /cancel 命令 ====================

    async def cmd_cancel(self, client, message) -> dict:
        """取消当前交互流程。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: 取消结果
        """
        user_id = message.from_user.id

        success = self._interaction_manager.cancel_flow(user_id)

        if success:
            text = (
                "❌ 操作已取消\n\n"
                "当前交互流程已清除。\n"
                "发送 /batch 可重新开始批量操作。"
            )
        else:
            text = (
                "ℹ️ 当前没有正在进行的交互流程\n\n"
                "发送 /batch 开始新的批量操作。"
            )

        await client.send_message(
            chat_id=user_id,
            text=text,
        )

        logger.info("/cancel 命令已执行: user_id=%s, success=%s", user_id, success)
        return {"cancelled": success}
