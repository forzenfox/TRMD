# coding=UTF-8
"""Bot 新增命令模块。

实现 M2 阶段的简化 Bot 命令：
- /web：生成 Token 并返回 WebUI 链接
- /batch：简化批量操作模式（通过状态机收集用户输入 + 内联键盘选择）
- /status：展示当前任务状态摘要，引导复杂操作到 WebUI
- /cancel：取消当前交互流程
- /setup_repository：设置仓库频道

批次8 扩展：/batch 支持任务类型/范围模式内联键盘选择、完成后自动创建任务。
"""

import logging
import re
from typing import Optional

from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified

from module.bot.keyboard_manager import KeyboardManager
from module.core.config_manager import ConfigManager
from module.core.task_manager import (
    TaskManager,
    TaskType,
    ValidationError,
    ResourceLimitError,
)
from module.core.task_executor import TaskExecutor
from module.core.token_manager import TokenManager
from module.interaction_manager import InteractionManager, BatchStep

logger = logging.getLogger(__name__)

# WebUI 基础 URL 默认值
DEFAULT_WEBUI_URL = "http://localhost:8000"


class BotCommands:
    """新增/重构的 Bot 命令处理器。

    与原有 Bot 类解耦，通过组合 TokenManager、InteractionManager、TaskManager
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
        task_manager: Optional[TaskManager] = None,
        task_executor: Optional[TaskExecutor] = None,
    ) -> None:
        """
        :param token_manager: Token 管理器实例
        :param interaction_manager: 交互状态管理器实例
        :param config_manager: 配置管理器实例（可选）
        :param webui_base_url: WebUI 基础 URL
        :param task_manager: 任务管理器实例（可选，批次8 新增）
        :param task_executor: 任务执行器实例（可选，批次8 新增）
        """
        self._token_manager = token_manager
        self._interaction_manager = interaction_manager
        self._config_manager = config_manager
        self._webui_base_url = webui_base_url
        self._task_manager = task_manager
        self._task_executor = task_executor

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

    @staticmethod
    def convert_download_type_to_filter_types(download_type: dict) -> list[str]:
        """将 StateManager.download_chat_filter 的 download_type 字典转换为 filter_types 列表。

        Args:
            download_type: 如 {"video": True, "photo": False, "document": True, ...}

        Returns:
            如 ["video", "document"]
        """
        return [k for k, v in download_type.items() if v is True]

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

        通过内联键盘和文本输入引导用户逐步配置：
        1. 任务类型（下载/转发）— 内联键盘
        2. 源频道链接 — 文本输入
        3. 目标频道链接（仅转发）— 文本输入
        4. 范围模式 — 内联键盘
        5. 范围参数 — 文本输入
        6. 类型过滤 — 内联键盘多选
        7. 完成后自动创建任务

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

        # 检查 TaskManager 是否可用
        if self._task_manager is None:
            await client.send_message(
                user_id,
                "❌ 任务管理器未就绪，请稍后重试",
            )
            return None

        # 启动新流程
        state = self._interaction_manager.start_flow(user_id=user_id, command="/batch")

        text = "📦 批量操作模式已启动\n\n请选择任务类型："
        keyboard = KeyboardManager.build_task_type_keyboard()

        await client.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
        )

        logger.info("/batch 命令已执行: user_id=%s", user_id)
        return {"state": state.to_dict()}

    async def handle_batch_input(self, client, message) -> Optional[dict]:
        """处理用户在批量操作流程中输入的文本数据。

        仅处理文本输入步骤（SOURCE_CHANNEL、TARGET_CHANNEL、RANGE_INPUT），
        内联键盘步骤由 handle_batch_callback 处理。

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
                text="❌ 当前未开始批量操作流程\n请先发送 /batch 启动批量操作",
            )
            return None

        state = self._interaction_manager.get_active_flow(user_id)
        current_step = state.current_step

        # 内联键盘步骤不应有文本输入，提示用户使用键盘
        if current_step in (
            BatchStep.TASK_TYPE,
            BatchStep.RANGE_MODE,
            BatchStep.FILTER_TYPES,
        ):
            await client.send_message(user_id, "👆 请使用上方按钮选择")
            return None

        # 文本输入步骤：使用 collect 收集并验证
        result = self._interaction_manager.collect(
            user_id=user_id,
            input_text=input_text,
        )

        if result is None:
            return None

        if not result.success:
            await client.send_message(user_id, result.message)
            return None

        # SOURCE_CHANNEL 完成后，根据 task_type 决定下一步
        if result.current_step == BatchStep.RANGE_MODE:
            # DOWNLOAD: SOURCE_CHANNEL → RANGE_MODE，显示键盘
            keyboard = KeyboardManager.build_range_mode_keyboard()
            prompt = BatchStep.get_prompt(
                BatchStep.RANGE_MODE,
                self._interaction_manager.get_collected_data(user_id),
            )
            await client.send_message(user_id, prompt, reply_markup=keyboard)
            return {"status": "in_progress", "step": result.current_step.value}

        if result.current_step == BatchStep.TARGET_CHANNEL:
            # FORWARD: SOURCE_CHANNEL → TARGET_CHANNEL
            await client.send_message(user_id, result.message)
            return {"status": "in_progress", "step": result.current_step.value}

        # TARGET_CHANNEL 完成后 → RANGE_MODE
        if result.current_step == BatchStep.RANGE_INPUT:
            # 上一步是 RANGE_MODE（内联键盘），但如果是文本输入到达这里，
            # 说明是从 TARGET_CHANNEL 收集后推进的
            # 不应该出现，因为 RANGE_MODE 是键盘步骤
            pass

        # RANGE_INPUT 完成后 → FILTER_TYPES，显示键盘
        if result.current_step == BatchStep.FILTER_TYPES:
            keyboard = KeyboardManager.build_filter_types_keyboard()
            prompt = BatchStep.get_prompt(BatchStep.FILTER_TYPES)
            await client.send_message(user_id, prompt, reply_markup=keyboard)
            return {"status": "in_progress", "step": result.current_step.value}

        # COMPLETE 状态
        if result.current_step == BatchStep.COMPLETE:
            collected = result.collected_data
            return await self._handle_batch_complete(
                client, message, user_id, collected
            )

        # 其他步骤推进（兜底）
        await client.send_message(user_id, result.message)
        return {"status": "in_progress", "step": result.current_step.value}

    async def handle_batch_callback(self, client, callback_query) -> Optional[dict]:
        """处理 /batch 流程中的内联键盘回调。

        回调数据格式：
        - batch:task_type:download / batch:task_type:forward
        - batch:range_mode:id_range / batch:range_mode:date_range / ...
        - batch:filter:video / batch:filter:photo / ... / batch:filter:confirm
        """
        user_id = callback_query.from_user.id
        data = callback_query.data

        if not data.startswith("batch:"):
            return None

        parts = data.split(":")
        if len(parts) < 3:
            return None

        action = parts[1]
        value = parts[2]

        if action == "task_type":
            return await self._handle_task_type_callback(
                client, callback_query, user_id, value
            )
        elif action == "range_mode":
            return await self._handle_range_mode_callback(
                client, callback_query, user_id, value
            )
        elif action == "filter":
            return await self._handle_filter_callback(
                client, callback_query, user_id, value
            )

        return None

    async def _handle_task_type_callback(self, client, callback_query, user_id, value):
        """处理任务类型选择回调。"""
        im = self._interaction_manager

        # 保存选择
        im.set_step_data(user_id, "task_type", value)

        # 推进步骤到 SOURCE_CHANNEL
        im.advance_step(user_id)

        # 更新消息
        task_label = "下载" if value == "download" else "转发"
        prompt = im.get_step_prompt(user_id)
        try:
            await callback_query.message.edit_text(
                f"✅ 已选择：{task_label}\n\n{prompt}\n\n💡 输入 /cancel 可随时取消操作",
                reply_markup=None,
            )
        except MessageNotModified:
            pass
        await callback_query.answer()
        return {"status": "task_type_selected", "value": value}

    async def _handle_range_mode_callback(self, client, callback_query, user_id, value):
        """处理范围模式选择回调。"""
        im = self._interaction_manager

        # 保存选择
        im.set_step_data(user_id, "range_mode", value)

        # all 模式无需输入，直接推进到 FILTER_TYPES
        if value == "all":
            im.set_step_data(user_id, "range_input", "all")
            im.advance_step(user_id)  # RANGE_MODE → RANGE_INPUT
            im.advance_step(user_id)  # RANGE_INPUT → FILTER_TYPES

            collected = im.get_collected_data(user_id)
            prompt = BatchStep.get_prompt(BatchStep.FILTER_TYPES, collected)
            keyboard = KeyboardManager.build_filter_types_keyboard()
            try:
                await callback_query.message.edit_text(
                    f"✅ 已选择：全部消息\n\n{prompt}",
                    reply_markup=keyboard,
                )
            except MessageNotModified:
                pass
        else:
            # 推进步骤到 RANGE_INPUT
            im.advance_step(user_id)

            collected = im.get_collected_data(user_id)
            prompt = BatchStep.get_prompt(BatchStep.RANGE_INPUT, collected)
            mode_labels = {
                "id_range": "ID 范围",
                "date_range": "日期范围",
                "multiple_ids": "消息列表",
            }
            try:
                await callback_query.message.edit_text(
                    f"✅ 已选择：{mode_labels.get(value, value)}\n\n{prompt}",
                    reply_markup=None,
                )
            except MessageNotModified:
                pass

        await callback_query.answer()
        return {"status": "range_mode_selected", "value": value}

    async def _handle_filter_callback(self, client, callback_query, user_id, value):
        """处理类型过滤选择回调（多选 toggle）。"""
        im = self._interaction_manager

        if value == "confirm":
            # 确认选择，推进到 COMPLETE 并创建任务
            im.advance_step(user_id)
            collected = im.get_collected_data(user_id)
            await self._handle_batch_complete(
                client, callback_query.message, user_id, collected
            )
            await callback_query.answer()
            return {"status": "filter_confirmed"}

        # toggle 某个类型
        collected = im.get_collected_data(user_id) or {}
        filter_types = list(collected.get("filter_types", []))

        if value in filter_types:
            filter_types.remove(value)
        else:
            filter_types.append(value)

        im.set_step_data(user_id, "filter_types", filter_types)

        # 更新键盘（显示选中状态）
        keyboard = KeyboardManager.build_filter_types_keyboard(filter_types)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        except MessageNotModified:
            pass
        await callback_query.answer()
        return {"status": "filter_toggled", "value": value, "selected": filter_types}

    async def _collected_to_task_params(
        self,
        collected: dict,
        client,
    ) -> Optional[dict]:
        """将 /batch 收集的数据转换为 TaskManager.create_task 参数。

        Args:
            collected: InteractionManager 收集的数据字典
            client: Pyrogram Client（用于频道 ID 解析）

        Returns:
            转换后的参数字典，包含 task_type/chat_id/params，或 None（解析失败）
        """
        # 1. 任务类型
        task_type_str = collected.get("task_type", "download")
        task_type = (
            TaskType.DOWNLOAD if task_type_str == "download" else TaskType.FORWARD
        )

        # 2. 源频道 ID（URL → int）
        source_url = collected.get("source_channel", "")
        try:
            chat_id_str = await self.resolve_channel_id(client, source_url)
            chat_id = int(chat_id_str)
        except (ValueError, TypeError, Exception) as e:
            logger.warning("源频道解析失败: %s, error=%s", source_url, e)
            return None

        # 3. 范围参数
        range_mode = collected.get("range_mode", "id_range")
        range_input = collected.get("range_input", "")
        params = {"range_mode": range_mode}

        if range_mode == "id_range":
            parts = range_input.split()
            if len(parts) >= 2:
                params["min_id"] = int(parts[0])
                params["max_id"] = int(parts[1])
        elif range_mode == "date_range":
            parts = range_input.split()
            if len(parts) >= 2:
                params["start_date"] = parts[0]
                params["end_date"] = parts[1]
        elif range_mode == "multiple_ids":
            items = [
                x.strip()
                for x in range_input.replace(",", "\n").split("\n")
                if x.strip()
            ]
            params["message_list"] = items
        # all 模式无需额外参数

        # 4. 类型过滤
        filter_types = collected.get("filter_types", [])
        if filter_types:
            params["filter_types"] = filter_types

        # 5. 目标频道（仅 FORWARD）
        if task_type == TaskType.FORWARD:
            target_url = collected.get("target_channel", "")
            try:
                target_chat_id_str = await self.resolve_channel_id(client, target_url)
                params["target_chat_id"] = int(target_chat_id_str)
            except (ValueError, TypeError, Exception) as e:
                logger.warning("目标频道解析失败: %s, error=%s", target_url, e)
                return None

        return {
            "task_type": task_type,
            "chat_id": chat_id,
            "params": params,
        }

    async def _handle_batch_complete(
        self, client, message, user_id: int, collected: dict
    ) -> Optional[dict]:
        """处理 /batch 流程完成，转换数据并创建任务。

        Args:
            client: Pyrogram 客户端
            message: 消息对象（用于发送回复）
            user_id: 用户 ID
            collected: 已收集的数据字典
        """
        # 转换为 TaskManager 参数
        task_params = await self._collected_to_task_params(collected, client)

        if task_params is None:
            await client.send_message(user_id, "❌ 频道解析失败，请检查链接是否正确")
            self._interaction_manager.cancel_flow(user_id)
            return {"status": "error", "reason": "channel_resolve_failed"}

        # 创建任务
        try:
            task = await self._task_manager.create_task(
                task_type=task_params["task_type"],
                chat_id=task_params["chat_id"],
                params=task_params["params"],
            )
            # 自动启动
            await self._task_manager.start_task(task.task_id)
        except (ValidationError, ResourceLimitError) as e:
            await client.send_message(user_id, f"❌ 任务创建失败：{e}")
            self._interaction_manager.cancel_flow(user_id)
            return {"status": "error", "reason": str(e)}
        except Exception as e:
            logger.error("创建任务异常: %s", e)
            await client.send_message(user_id, f"❌ 创建任务时发生错误：{e}")
            self._interaction_manager.cancel_flow(user_id)
            return {"status": "error", "reason": str(e)}

        # 构建成功消息
        task_type_label = (
            "下载" if task_params["task_type"] == TaskType.DOWNLOAD else "转发"
        )
        range_mode_labels = {
            "id_range": "ID 范围",
            "date_range": "日期范围",
            "multiple_ids": "消息列表",
            "all": "全部消息",
        }
        range_label = range_mode_labels.get(
            task_params["params"].get("range_mode", ""), "未知"
        )
        filter_types = task_params["params"].get("filter_types", [])
        filter_label = ", ".join(filter_types) if filter_types else "全部类型"

        text = (
            f"✅ 任务已创建并开始执行！\n\n"
            f"📋 任务 ID：`{task.task_id}`\n"
            f"📊 类型：{task_type_label}\n"
            f"📐 范围模式：{range_label}\n"
            f"🔍 媒体类型：{filter_label}\n\n"
            f"💡 发送 /status 查看任务进度"
        )
        await client.send_message(user_id, text)
        self._interaction_manager.cancel_flow(user_id)
        return {"status": "completed", "task_id": task.task_id}

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
                f"  • 当前步骤：{BatchStep.get_prompt(user_flow.current_step, user_flow.collected_data)}"
            )
            parts.append(f"  • 已收集数据：{len(user_flow.collected_data)} 项\n")
        else:
            parts.append("✅ 当前没有正在进行的交互流程\n")

        # 统计信息
        total_flows = len(active_flows)
        if total_flows > 0:
            parts.append(f"📈 全局活跃流程数：{total_flows}\n")

        # 任务统计
        if self._task_manager is not None:
            try:
                tasks = self._task_manager.list_tasks()
                running = sum(1 for t in tasks if t.status.value == "running")
                completed = sum(1 for t in tasks if t.status.value == "completed")
                failed = sum(1 for t in tasks if t.status.value == "failed")
                parts.append(
                    f"\n📋 任务统计：运行中 {running} | 已完成 {completed} | 失败 {failed}"
                )
            except Exception:
                pass

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
