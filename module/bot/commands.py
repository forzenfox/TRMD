# coding=UTF-8
"""Bot 新增命令模块。

实现 M2 阶段的简化 Bot 命令：
- /web：生成 Token 并返回 WebUI 链接
- /batch：简化批量操作模式（通过状态机收集用户输入）
- /status：展示当前任务状态摘要，引导复杂操作到 WebUI
- /cancel：取消当前交互流程
- /setup_repository：设置仓库频道

保持与原有 module/bot.py 的兼容性，不修改原有文件。
详见 `docs/module-design-bot-refactor.md`。
"""

import logging
import re
from typing import Optional

from module.config.config_manager import ConfigManager
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
        ("web_revoke", "撤销所有 WebUI Token"),
        ("batch", "简化批量操作：转发/下载任务（多步引导）"),
        ("status", "查看当前任务状态摘要（复杂操作请前往 WebUI）"),
        ("cancel", "取消当前正在进行的交互流程"),
        ("setup_repository", "设置仓库频道（配置存储频道）"),
    ]

    # 频道输入格式正则
    _RE_NUMERIC_ID = re.compile(r"^-?\d+$")
    _RE_USERNAME = re.compile(r"^@[a-zA-Z]\w{3,30}$")
    _RE_T_ME_LINK = re.compile(r"^https?://t\.me/([a-zA-Z]\w{0,30})$")
    _RE_INVITE_LINK = re.compile(r"^https?://t\.me/\+[A-Za-z0-9_-]+$")

    def __init__(
        self,
        token_manager: TokenManager,
        interaction_manager: InteractionManager,
        config_manager: Optional[ConfigManager] = None,
        webui_base_url: str = DEFAULT_WEBUI_URL,
    ) -> None:
        """
        :param token_manager: Token 管理器实例
        :param interaction_manager: 交互状态管理器实例
        :param config_manager: 配置管理器实例（可选）
        :param webui_base_url: WebUI 基础 URL
        """
        self._token_manager = token_manager
        self._interaction_manager = interaction_manager
        self._config_manager = config_manager
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

    # ==================== /web_revoke 命令 ====================

    async def cmd_web_revoke(self, client, message) -> dict:
        """撤销所有已生成的 WebUI Token。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: {"revoked_count": int}
        """
        user_id = message.from_user.id

        # 撤销该用户的所有 Token
        revoked_count = self._token_manager.revoke_all(user_id=user_id)

        text = (
            f"🔒 WebUI Token 已撤销\n\n"
            f"已撤销 {revoked_count} 个有效 Token\n"
            f"所有已打开的 WebUI 页面将在 Token 过期后失效\n\n"
            "💡 如需重新访问 WebUI，请发送 /web 获取新链接"
        )

        await client.send_message(
            chat_id=user_id,
            text=text,
        )

        logger.info(
            "/web_revoke 命令已执行: user_id=%s, revoked_count=%s",
            user_id,
            revoked_count,
        )
        return {"revoked_count": revoked_count}

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
                text=("❌ 当前未开始批量操作流程\n请先发送 /batch 启动批量操作"),
            )
            return None

        # 收集并验证输入
        result = self._interaction_manager.collect(
            user_id=user_id, input_text=input_text
        )

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
        return {
            "status": "in_progress",
            "step": state.current_step.value if state else None,
        }

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
            parts.append("🔄 正在进行的批量操作：\n")
            parts.append(
                f"  • 当前步骤：{BatchStep.get_prompt(user_flow.current_step)}"
            )
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
            text = "ℹ️ 当前没有正在进行的交互流程\n\n发送 /batch 开始新的批量操作。"

        await client.send_message(
            chat_id=user_id,
            text=text,
        )

        logger.info("/cancel 命令已执行: user_id=%s, success=%s", user_id, success)
        return {"cancelled": success}

    # ==================== /setup_repository 命令 ====================

    def validate_channel_input(self, channel_input: str) -> Optional[str]:
        """验证频道输入格式是否合法。

        支持的输入格式：
        - 频道 ID（如 -1001234567890）
        - 用户名（如 @my_repo）
        - 链接（如 https://t.me/my_repo）
        - 邀请链接（如 https://t.me/+AbCdEf）

        :param channel_input: 用户输入的频道标识
        :return: 输入类型字符串（"numeric_id", "username", "t_me_link", "invite_link"）或 None
        """
        text = channel_input.strip()
        if not text:
            return None

        if self._RE_NUMERIC_ID.match(text):
            return "numeric_id"

        if self._RE_USERNAME.match(text):
            return "username"

        if self._RE_INVITE_LINK.match(text):
            return "invite_link"

        if self._RE_T_ME_LINK.match(text):
            return "t_me_link"

        return None

    async def resolve_channel_id(self, client, channel_input: str) -> str:
        """将用户输入的频道标识解析为数字 chat_id。

        - 纯数字 ID 直接返回
        - @username 通过 client.get_chat 解析
        - https://t.me/channel 通过 client.get_chat 解析
        - https://t.me/+xxx 邀请链接通过 client.get_chat 解析

        :param client: Pyrogram 客户端
        :param channel_input: 用户输入的频道标识
        :return: 解析后的数字 chat_id 字符串
        :raises Exception: 解析失败时抛出异常
        """
        text = channel_input.strip()

        # 纯数字 ID 直接返回
        if self._RE_NUMERIC_ID.match(text):
            return text

        # 需要通过网络请求解析
        chat = await client.get_chat(text)
        if chat is None or not hasattr(chat, "id"):
            raise ValueError(f"无法解析频道: {text}")

        return str(chat.id)

    async def _check_admin_permission(self, client, chat_id: str) -> bool:
        """检查 Bot 是否在指定频道中拥有管理员权限。

        :param client: Pyrogram 客户端
        :param chat_id: 频道 chat_id
        :return: 是否为管理员
        """
        try:
            member = await client.get_chat_member(chat_id, "me")
            return member.status in ("administrator", "creator")
        except Exception:
            return False

    async def cmd_setup_repository(self, client, message) -> dict:
        """设置仓库频道。

        用户发送 /setup_repository <频道标识> 后：
        1. 验证频道输入格式
        2. 解析频道 ID（支持邀请链接、用户名等）
        3. 检查 Bot 是否拥有管理员权限
        4. 保存到配置

        无参数时发送欢迎消息和使用说明。

        :param client: Pyrogram 客户端
        :param message: 用户消息
        :return: 结果字典
        """
        user_id = message.from_user.id
        text = message.text.strip()

        # 解析命令参数
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            # 无参数，发送欢迎消息
            welcome_text = (
                "🗄️ 仓库频道设置\n\n"
                "仓库模式会将下载的媒体文件自动存储到指定频道，"
                "实现去重和分发功能。\n\n"
                "📋 请使用以下命令格式设置仓库频道：\n"
                "`/setup_repository <频道标识>`\n\n"
                "支持的频道标识格式：\n"
                "  • 频道 ID：`-1001234567890`\n"
                "  • 用户名：`@my_repo`\n"
                "  • 频道链接：`https://t.me/my_repo`\n"
                "  • 邀请链接：`https://t.me/+AbCdEf`\n\n"
                "⚠️ Bot 需要在目标频道拥有管理员权限"
            )
            await client.send_message(chat_id=user_id, text=welcome_text)
            logger.info("/setup_repository 命令已执行（无参数）: user_id=%s", user_id)
            return {"status": "prompt_sent"}

        channel_input = parts[1].strip()

        # 验证输入格式
        input_type = self.validate_channel_input(channel_input)
        if input_type is None:
            error_text = (
                "❌ 无效的频道标识格式\n\n"
                f"输入：`{channel_input}`\n\n"
                "支持的格式：\n"
                "  • 频道 ID：`-1001234567890`\n"
                "  • 用户名：`@my_repo`\n"
                "  • 频道链接：`https://t.me/my_repo`\n"
                "  • 邀请链接：`https://t.me/+AbCdEf`"
            )
            await client.send_message(chat_id=user_id, text=error_text)
            logger.warning(
                "/setup_repository 无效输入: user_id=%s, input=%s",
                user_id,
                channel_input,
            )
            return {"status": "invalid_input", "input": channel_input}

        # 解析频道 ID
        try:
            chat_id = await self.resolve_channel_id(client, channel_input)
        except Exception as e:
            error_text = (
                "❌ 无法解析频道\n\n"
                f"输入：`{channel_input}`\n"
                f"错误：{e}\n\n"
                "请确认频道存在且 Bot 可以访问"
            )
            await client.send_message(chat_id=user_id, text=error_text)
            logger.error(
                "/setup_repository 解析失败: user_id=%s, input=%s, error=%s",
                user_id,
                channel_input,
                e,
            )
            return {"status": "resolve_error", "input": channel_input, "error": str(e)}

        # 检查管理员权限
        is_admin = await self._check_admin_permission(client, chat_id)
        if not is_admin:
            error_text = (
                "❌ 权限不足\n\n"
                f"频道 ID：`{chat_id}`\n\n"
                "Bot 需要在该频道拥有管理员权限才能使用仓库功能。\n"
                "请在频道设置中将 Bot 设为管理员后重试。"
            )
            await client.send_message(chat_id=user_id, text=error_text)
            logger.warning(
                "/setup_repository 权限不足: user_id=%s, chat_id=%s",
                user_id,
                chat_id,
            )
            return {"status": "permission_denied", "chat_id": chat_id}

        # 保存配置
        if self._config_manager is not None:
            save_ok = self._config_manager.set_repository_chat_id(chat_id)
            if not save_ok:
                error_text = (
                    "❌ 配置保存失败\n\n"
                    f"频道 ID：`{chat_id}`\n\n"
                    "请检查配置文件权限后重试。"
                )
                await client.send_message(chat_id=user_id, text=error_text)
                logger.error(
                    "/setup_repository 配置保存失败: user_id=%s, chat_id=%s",
                    user_id,
                    chat_id,
                )
                return {"status": "save_error", "chat_id": chat_id}
        else:
            logger.warning(
                "/setup_repository 无 config_manager，跳过保存: user_id=%s, chat_id=%s",
                user_id,
                chat_id,
            )

        # 成功
        success_text = (
            "✅ 仓库频道设置成功！\n\n"
            f"📁 频道 ID：`{chat_id}`\n\n"
            "仓库模式已启用，下载的媒体文件将自动存储到该频道。\n"
            "你可以通过 WebUI 查看和管理仓库内容。"
        )
        await client.send_message(chat_id=user_id, text=success_text)
        logger.info(
            "/setup_repository 命令已执行: user_id=%s, chat_id=%s",
            user_id,
            chat_id,
        )
        return {"status": "success", "chat_id": chat_id}
