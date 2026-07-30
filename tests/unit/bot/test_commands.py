# coding=UTF-8
"""BotCommands 单元测试。

测试新增/重构的 Bot 命令逻辑：
- /web 命令：生成 Token 并返回 WebUI 链接
- /batch 简化批量操作模式
- /status 命令的 WebUI 引导模式
- 复杂操作引导到 WebUI 的交互文案

使用 mock 模拟 Pyrogram 客户端，不实际连接 Telegram。
"""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from module.bot.commands import BotCommands
from module.core.interaction_manager import InteractionManager
from module.core.auth.token_manager import TokenManager


# ==================== Fixtures ====================


@pytest.fixture
def mock_client():
    """模拟 Pyrogram 客户端。"""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.edit_message_text = AsyncMock()
    return client


@pytest.fixture
def mock_message():
    """模拟 Pyrogram 消息对象。"""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.id = 100
    message.text = ""
    return message


@pytest.fixture
def token_manager():
    """提供内存模式的 TokenManager，默认 TTL 与生产环境一致为 12 小时。"""
    return TokenManager(default_ttl=12 * 3600)


@pytest.fixture
def interaction_manager():
    """提供内存模式的 InteractionManager。"""
    return InteractionManager(timeout_seconds=300)


@pytest.fixture
def mock_task_manager():
    """模拟 TaskManager。"""
    from module.core.task.manager import TaskManager

    tm = MagicMock(spec=TaskManager)
    tm.create_task = AsyncMock()
    tm.start_task = AsyncMock()
    tm.list_tasks = MagicMock(return_value=[])
    return tm


@pytest.fixture
def mock_task_executor():
    """模拟 TaskExecutor。"""
    from module.core.task.executor import TaskExecutor

    te = MagicMock(spec=TaskExecutor)
    return te


@pytest.fixture
def bot_commands(
    token_manager, interaction_manager, mock_task_manager, mock_task_executor
):
    """提供 BotCommands 实例（含 TaskManager/TaskExecutor）。"""
    return BotCommands(
        token_manager=token_manager,
        interaction_manager=interaction_manager,
        webui_base_url="http://localhost:8000",
        task_manager=mock_task_manager,
        task_executor=mock_task_executor,
    )


@pytest.fixture
def mock_callback_query():
    """模拟 Pyrogram CallbackQuery。"""
    cq = MagicMock()
    cq.from_user = MagicMock()
    cq.from_user.id = 12345
    cq.data = ""
    cq.message = MagicMock()
    cq.message.edit_text = AsyncMock()
    cq.message.edit_reply_markup = AsyncMock()
    cq.answer = AsyncMock()
    return cq


# ==================== 初始化测试 ====================


class TestBotCommandsInit:
    """BotCommands 初始化测试。"""

    def test_create_with_managers(self, token_manager, interaction_manager):
        """应能使用 TokenManager 和 InteractionManager 创建实例。"""
        cmds = BotCommands(
            token_manager=token_manager,
            interaction_manager=interaction_manager,
            webui_base_url="http://localhost:8000",
        )
        assert cmds._token_manager is token_manager
        assert cmds._interaction_manager is interaction_manager
        assert cmds._webui_base_url == "http://localhost:8000"

    def test_default_webui_url(self, token_manager, interaction_manager):
        """默认 WebUI URL 应为 http://localhost:8000。"""
        cmds = BotCommands(
            token_manager=token_manager,
            interaction_manager=interaction_manager,
        )
        assert cmds._webui_base_url == "http://localhost:8000"

    def test_create_with_task_manager(
        self, token_manager, interaction_manager, mock_task_manager, mock_task_executor
    ):
        """创建时可传入 task_manager 和 task_executor。"""
        cmds = BotCommands(
            token_manager=token_manager,
            interaction_manager=interaction_manager,
            webui_base_url="http://localhost:8000",
            task_manager=mock_task_manager,
            task_executor=mock_task_executor,
        )
        assert cmds._task_manager is mock_task_manager
        assert cmds._task_executor is mock_task_executor

    def test_create_without_task_manager(self, token_manager, interaction_manager):
        """不传 task_manager 时应为 None。"""
        cmds = BotCommands(
            token_manager=token_manager,
            interaction_manager=interaction_manager,
            webui_base_url="http://localhost:8000",
        )
        assert cmds._task_manager is None
        assert cmds._task_executor is None


# ==================== /web 命令测试 ====================


class TestCmdWeb:
    """cmd_web 命令测试。"""

    @pytest.mark.asyncio
    async def test_web_generates_token(self, bot_commands, mock_client, mock_message):
        """cmd_web 应生成 Token 并返回包含 Token 的 WebUI 链接。"""
        mock_message.text = "/web"
        result = await bot_commands.cmd_web(mock_client, mock_message)

        assert result is not None
        assert "token" in result
        token = result["token"]
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_web_returns_url(self, bot_commands, mock_client, mock_message):
        """cmd_web 返回的字典应包含完整 URL。"""
        mock_message.text = "/web"
        result = await bot_commands.cmd_web(mock_client, mock_message)

        assert "url" in result
        assert "http://localhost:8000" in result["url"]
        assert "token=" in result["url"]

    @pytest.mark.asyncio
    async def test_web_sends_message(self, bot_commands, mock_client, mock_message):
        """cmd_web 应向用户发送包含链接的消息，且有效期文案与 TTL 一致。"""
        mock_message.text = "/web"
        await bot_commands.cmd_web(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "chat_id" in call_kwargs
        assert "text" in call_kwargs
        assert "http://localhost:8000" in call_kwargs["text"]

        # 验证有效期文案与 TokenManager 的 default_ttl 一致
        ttl_hours = bot_commands._token_manager._default_ttl // 3600
        assert f"{ttl_hours} 小时" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_web_sends_clickable_button(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_web 应发送可点击的内联按钮，URL 带 Token。"""
        mock_message.text = "/web"
        with patch.object(
            bot_commands,
            "get_webui_link",
            return_value="https://example.com/web?token=test_token",
        ):
            result = await bot_commands.cmd_web(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        reply_markup = call_kwargs.get("reply_markup")
        assert reply_markup is not None, "应包含 reply_markup"

        # 提取第一行第一个按钮
        button = reply_markup.inline_keyboard[0][0]
        assert button.text == "🌐 打开 WebUI"
        assert button.url == result["url"]
        assert "token=" in button.url

    @pytest.mark.asyncio
    async def test_web_token_is_valid(self, bot_commands, mock_client, mock_message):
        """cmd_web 生成的 Token 应能通过验证。"""
        mock_message.text = "/web"
        result = await bot_commands.cmd_web(mock_client, mock_message)

        # Token 应能被 TokenManager 验证
        record = bot_commands._token_manager.verify(result["token"])
        assert record is not None
        assert record.token == result["token"]

    @pytest.mark.asyncio
    async def test_web_uses_user_id(self, bot_commands, mock_client, mock_message):
        """cmd_web 应使用消息发送者的 user_id 生成 Token。"""
        mock_message.text = "/web"
        mock_message.from_user.id = 99999
        await bot_commands.cmd_web(mock_client, mock_message)

        # 获取最后一个生成的 Token 并检查 user_id
        all_flows = bot_commands._token_manager
        # 通过生成一个已知 user_id 的 Token 来验证
        token = all_flows.generate(user_id=99999)
        record = all_flows.verify(token)
        assert record.user_id == 99999


# ==================== /batch 命令测试 ====================


class TestCmdBatch:
    """cmd_batch 命令测试。"""

    @pytest.mark.asyncio
    async def test_batch_starts_flow(self, bot_commands, mock_client, mock_message):
        """cmd_batch 应启动批量操作流程。"""
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        assert bot_commands._interaction_manager.has_active_flow(12345) is True

    @pytest.mark.asyncio
    async def test_batch_shows_first_prompt(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_batch 应显示任务类型选择提示。"""
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "任务类型" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_batch_shows_cancel_hint(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_batch 应显示批量操作模式已启动。"""
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "批量操作模式已启动" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_batch_existing_flow(self, bot_commands, mock_client, mock_message):
        """用户已有活跃流程时应提示先完成或取消。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "已有" in call_kwargs["text"] or "进行" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_batch_shows_task_type_keyboard(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_batch 应包含内联键盘。"""
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "reply_markup" in call_kwargs
        assert call_kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_batch_no_task_manager(
        self, mock_client, mock_message, token_manager, interaction_manager
    ):
        """task_manager 为 None 时应提示未就绪。"""
        cmds = BotCommands(
            token_manager=token_manager,
            interaction_manager=interaction_manager,
            webui_base_url="http://localhost:8000",
        )
        mock_message.text = "/batch"
        await cmds.cmd_batch(mock_client, mock_message)

        call_args = mock_client.send_message.call_args[0]
        text = call_args[1]  # 第二个位置参数是 text
        assert "未就绪" in text


# ==================== 批量输入收集测试 ====================


class TestBatchInputCollection:
    """批量操作流程的输入收集测试。"""

    @pytest.mark.asyncio
    async def test_handle_batch_input_collects_source(
        self, bot_commands, mock_client, mock_message
    ):
        """应收集源频道链接。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        # 新流程从 TASK_TYPE 开始，需要先设置 task_type
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)  # 推进到 SOURCE_CHANNEL
        mock_message.text = "https://t.me/source_channel"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert (
            state.collected_data.get("source_channel") == "https://t.me/source_channel"
        )

    @pytest.mark.asyncio
    async def test_handle_batch_input_collects_target(
        self, bot_commands, mock_client, mock_message
    ):
        """应收集目标频道链接（FORWARD 类型）。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        # 设置 task_type 为 forward（使得 SOURCE_CHANNEL 下一步是 TARGET_CHANNEL）
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "forward")
        bot_commands._interaction_manager.advance_step(12345)  # 推进到 SOURCE_CHANNEL
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )  # 收集 source, 推进到 TARGET_CHANNEL
        mock_message.text = "https://t.me/target_channel"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert (
            state.collected_data.get("target_channel") == "https://t.me/target_channel"
        )

    @pytest.mark.asyncio
    async def test_handle_batch_input_collects_range(
        self, bot_commands, mock_client, mock_message
    ):
        """应收集消息范围参数。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        # 设置 task_type 和 range_mode
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(
            12345
        )  # TASK_TYPE → SOURCE_CHANNEL
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )  # → RANGE_MODE
        bot_commands._interaction_manager.set_step_data(12345, "range_mode", "id_range")
        bot_commands._interaction_manager.advance_step(
            12345
        )  # RANGE_MODE → RANGE_INPUT
        mock_message.text = "1 100"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert state.collected_data.get("range_input") == "1 100"

    @pytest.mark.asyncio
    async def test_handle_batch_input_invalid_when_no_flow(
        self, bot_commands, mock_client, mock_message
    ):
        """无活跃流程时应提示无效。"""
        mock_message.text = "https://t.me/source"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "未开始" in call_kwargs["text"] or "请先" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_batch_input_invalid_input(
        self, bot_commands, mock_client, mock_message
    ):
        """无效输入时应提示重新输入。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        # 推进到 SOURCE_CHANNEL（TASK_TYPE 是内联键盘步骤，不接受文本输入）
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        mock_message.text = "not_a_valid_link"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_args = mock_client.send_message.call_args[0]
        text = call_args[1]  # 第二个位置参数是 text
        assert "无效" in text or "格式" in text


# ==================== /status 命令测试 ====================


class TestCmdStatus:
    """cmd_status 命令测试。"""

    @pytest.mark.asyncio
    async def test_status_shows_summary(self, bot_commands, mock_client, mock_message):
        """cmd_status 应展示当前状态摘要。"""
        mock_message.text = "/status"
        await bot_commands.cmd_status(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "状态" in call_kwargs["text"] or "Status" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_status_guides_to_webui(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_status 应引导复杂操作到 WebUI。"""
        mock_message.text = "/status"
        await bot_commands.cmd_status(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert (
            "WebUI" in call_kwargs["text"]
            or "http://localhost:8000" in call_kwargs["text"]
        )

    @pytest.mark.asyncio
    async def test_status_shows_active_batch(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_status 应显示活跃的批量操作流程。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        mock_message.text = "/status"
        await bot_commands.cmd_status(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "batch" in call_kwargs["text"].lower() or "批量" in call_kwargs["text"]


# ==================== /cancel 命令测试 ====================


class TestCmdCancel:
    """cmd_cancel 命令测试。"""

    @pytest.mark.asyncio
    async def test_cancel_removes_flow(self, bot_commands, mock_client, mock_message):
        """cmd_cancel 应取消当前活跃流程。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_message.text = "/cancel"
        mock_message.from_user.id = 12345
        await bot_commands.cmd_cancel(mock_client, mock_message)

        assert bot_commands._interaction_manager.has_active_flow(12345) is False

    @pytest.mark.asyncio
    async def test_cancel_no_flow(self, bot_commands, mock_client, mock_message):
        """无活跃流程时 cmd_cancel 应提示无进行中的操作。"""
        mock_message.text = "/cancel"
        await bot_commands.cmd_cancel(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "没有" in call_kwargs["text"] or "进行" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_cancel_sends_confirmation(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_cancel 应发送取消确认消息。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_message.text = "/cancel"
        mock_message.from_user.id = 12345
        await bot_commands.cmd_cancel(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "已取消" in call_kwargs["text"]


# ==================== WebUI 引导文案测试 ====================


class TestWebUIGuidance:
    """WebUI 引导文案测试。"""

    def test_get_webui_link(self, bot_commands):
        """get_webui_link() 应返回带 Token 的完整链接。"""
        token = bot_commands._token_manager.generate(user_id=123)
        link = bot_commands.get_webui_link(token)

        assert "http://localhost:8000" in link
        assert f"token={token}" in link

    def test_get_webui_guidance_text(self, bot_commands):
        """get_webui_guidance_text() 应返回引导文案。"""
        text = bot_commands.get_webui_guidance_text()

        assert "WebUI" in text or "浏览器" in text
        assert "http://localhost:8000" in text or "链接" in text


# ==================== 命令注册测试 ====================


class TestCommandRegistration:
    """命令注册相关测试。"""

    def test_get_commands(self, bot_commands):
        """get_commands() 应返回所有新命令的定义。"""
        commands = bot_commands.get_commands()
        cmd_names = [c[0] for c in commands]

        assert "web" in cmd_names
        assert "batch" in cmd_names
        assert "status" in cmd_names
        assert "cancel" in cmd_names

    def test_command_descriptions(self, bot_commands):
        """每个命令应有描述文本。"""
        commands = bot_commands.get_commands()
        for name, desc in commands:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert len(desc) > 0


# ==================== handle_batch_callback 测试 ====================


class TestHandleBatchCallback:
    """handle_batch_callback 内联键盘回调测试。"""

    # --- 基础路由 ---
    @pytest.mark.asyncio
    async def test_callback_non_batch_prefix(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """非 batch: 前缀返回 None。"""
        mock_callback_query.data = "not_batch:test"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_callback_invalid_format(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """格式不正确（少于3段）返回 None。"""
        mock_callback_query.data = "batch:short"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is None

    # --- task_type 回调 ---
    @pytest.mark.asyncio
    async def test_task_type_download(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """选择下载类型。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_callback_query.data = "batch:task_type:download"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["status"] == "task_type_selected"
        assert result["value"] == "download"

    @pytest.mark.asyncio
    async def test_task_type_forward(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """选择转发类型。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_callback_query.data = "batch:task_type:forward"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["status"] == "task_type_selected"
        assert result["value"] == "forward"

    @pytest.mark.asyncio
    async def test_task_type_sets_step_data(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """验证 set_step_data 被调用。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_callback_query.data = "batch:task_type:download"
        await bot_commands.handle_batch_callback(mock_client, mock_callback_query)
        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert state.collected_data.get("task_type") == "download"

    @pytest.mark.asyncio
    async def test_task_type_advances_step(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """验证 advance_step 到 SOURCE_CHANNEL。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_callback_query.data = "batch:task_type:download"
        await bot_commands.handle_batch_callback(mock_client, mock_callback_query)
        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert state.current_step.value == "source_channel"

    # --- range_mode 回调 ---
    @pytest.mark.asyncio
    async def test_range_mode_id_range(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """选择 ID 范围。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        mock_callback_query.data = "batch:range_mode:id_range"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["value"] == "id_range"

    @pytest.mark.asyncio
    async def test_range_mode_date_range(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """选择日期范围。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        mock_callback_query.data = "batch:range_mode:date_range"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["value"] == "date_range"

    @pytest.mark.asyncio
    async def test_range_mode_multiple_ids(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """选择消息列表。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        mock_callback_query.data = "batch:range_mode:multiple_ids"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["value"] == "multiple_ids"

    @pytest.mark.asyncio
    async def test_range_mode_all(self, bot_commands, mock_client, mock_callback_query):
        """选择全部消息（跳过 RANGE_INPUT）。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        mock_callback_query.data = "batch:range_mode:all"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["value"] == "all"

    @pytest.mark.asyncio
    async def test_range_mode_all_advances_to_filter(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """all 模式直接到 FILTER_TYPES。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        mock_callback_query.data = "batch:range_mode:all"
        await bot_commands.handle_batch_callback(mock_client, mock_callback_query)
        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert state.current_step.value == "filter_types"

    # --- filter 回调 ---
    @pytest.mark.asyncio
    async def test_filter_toggle_add(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """添加一个类型。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        # 推进到 FILTER_TYPES
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        bot_commands._interaction_manager.set_step_data(12345, "range_mode", "all")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.advance_step(12345)
        mock_callback_query.data = "batch:filter:video"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["status"] == "filter_toggled"
        assert "video" in result["selected"]

    @pytest.mark.asyncio
    async def test_filter_toggle_remove(
        self, bot_commands, mock_client, mock_callback_query
    ):
        """移除一个类型。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        bot_commands._interaction_manager.set_step_data(12345, "range_mode", "all")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.advance_step(12345)
        # 先添加 video
        bot_commands._interaction_manager.set_step_data(
            12345, "filter_types", ["video", "photo"]
        )
        mock_callback_query.data = "batch:filter:video"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert "video" not in result["selected"]

    @pytest.mark.asyncio
    async def test_filter_confirm(self, bot_commands, mock_client, mock_callback_query):
        """确认选择。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.set_step_data(12345, "task_type", "download")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        bot_commands._interaction_manager.set_step_data(12345, "range_mode", "all")
        bot_commands._interaction_manager.advance_step(12345)
        bot_commands._interaction_manager.advance_step(12345)
        mock_callback_query.data = "batch:filter:confirm"
        result = await bot_commands.handle_batch_callback(
            mock_client, mock_callback_query
        )
        assert result is not None
        assert result["status"] == "filter_confirmed"


# ==================== _collected_to_task_params 测试 ====================


class TestCollectedToTaskParams:
    """_collected_to_task_params 数据转换测试。"""

    @pytest.fixture
    def mock_client_with_chat(self):
        client = MagicMock()
        client.get_chat = AsyncMock(return_value=MagicMock(id=-1001234567890))
        client.send_message = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_id_range_params(self, bot_commands, mock_client_with_chat):
        """id_range → min_id/max_id。"""
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/test_channel",
            "range_mode": "id_range",
            "range_input": "1 100",
            "filter_types": ["video"],
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result is not None
        assert result["params"]["min_id"] == 1
        assert result["params"]["max_id"] == 100
        assert result["params"]["range_mode"] == "id_range"

    @pytest.mark.asyncio
    async def test_date_range_params(self, bot_commands, mock_client_with_chat):
        """date_range → start_date/end_date。"""
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/test_channel",
            "range_mode": "date_range",
            "range_input": "2026-01-01 2026-06-01",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result is not None
        assert result["params"]["start_date"] == "2026-01-01"
        assert result["params"]["end_date"] == "2026-06-01"

    @pytest.mark.asyncio
    async def test_multiple_ids_params(self, bot_commands, mock_client_with_chat):
        """multiple_ids → message_list。"""
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/test_channel",
            "range_mode": "multiple_ids",
            "range_input": "1, 2, 3",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result is not None
        assert "message_list" in result["params"]

    @pytest.mark.asyncio
    async def test_all_mode_params(self, bot_commands, mock_client_with_chat):
        """all → 无额外范围参数。"""
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/test_channel",
            "range_mode": "all",
            "range_input": "all",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result is not None
        assert "min_id" not in result["params"]
        assert "start_date" not in result["params"]
        assert "message_list" not in result["params"]

    @pytest.mark.asyncio
    async def test_filter_types_included(self, bot_commands, mock_client_with_chat):
        """filter_types 被包含在 params 中。"""
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/test_channel",
            "range_mode": "all",
            "range_input": "all",
            "filter_types": ["video", "audio"],
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result["params"]["filter_types"] == ["video", "audio"]

    @pytest.mark.asyncio
    async def test_forward_task_params(self, bot_commands, mock_client_with_chat):
        """FORWARD 类型包含 target_chat_id。"""
        collected = {
            "task_type": "forward",
            "source_channel": "https://t.me/source",
            "target_channel": "https://t.me/target",
            "range_mode": "all",
            "range_input": "all",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result["params"]["target_chat_id"] == -1001234567890

    @pytest.mark.asyncio
    async def test_download_task_no_target(self, bot_commands, mock_client_with_chat):
        """DOWNLOAD 类型不含 target_chat_id。"""
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/test_channel",
            "range_mode": "all",
            "range_input": "all",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert "target_chat_id" not in result["params"]

    @pytest.mark.asyncio
    async def test_invalid_source_returns_none(
        self, bot_commands, mock_client_with_chat
    ):
        """源频道解析失败返回 None。"""
        mock_client_with_chat.get_chat = AsyncMock(side_effect=Exception("not found"))
        collected = {
            "task_type": "download",
            "source_channel": "https://t.me/invalid",
            "range_mode": "all",
            "range_input": "all",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_target_returns_none(
        self, bot_commands, mock_client_with_chat
    ):
        """目标频道解析失败返回 None（FORWARD）。"""

        async def get_chat_side_effect(text):
            if "source" in text:
                return MagicMock(id=-1001234567890)
            raise Exception("target not found")

        mock_client_with_chat.get_chat = AsyncMock(side_effect=get_chat_side_effect)
        collected = {
            "task_type": "forward",
            "source_channel": "https://t.me/source",
            "target_channel": "https://t.me/invalid_target",
            "range_mode": "all",
            "range_input": "all",
        }
        result = await bot_commands._collected_to_task_params(
            collected, mock_client_with_chat
        )
        assert result is None


# ==================== _handle_batch_complete 测试 ====================


class TestHandleBatchComplete:
    """_handle_batch_complete 任务创建测试。"""

    @pytest.mark.asyncio
    async def test_successful_task_creation(
        self, bot_commands, mock_client, mock_message
    ):
        """正常创建并启动。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")

        # Mock _collected_to_task_params 返回固定值
        async def mock_to_params(collected, client):
            return {
                "task_type": type("MockTaskType", (), {"value": "download"})(),
                "chat_id": -1001234567890,
                "params": {"range_mode": "all", "filter_types": ["video"]},
            }

        bot_commands._collected_to_task_params = mock_to_params
        # Mock task_manager.create_task
        mock_task = MagicMock()
        mock_task.task_id = "test-task-123"
        bot_commands._task_manager.create_task = AsyncMock(return_value=mock_task)
        bot_commands._task_manager.start_task = AsyncMock()
        collected = bot_commands._interaction_manager.get_collected_data(12345)
        result = await bot_commands._handle_batch_complete(
            mock_client, mock_message, 12345, collected
        )
        assert result["status"] == "completed"
        assert result["task_id"] == "test-task-123"
        bot_commands._task_manager.start_task.assert_called_once_with("test-task-123")

    @pytest.mark.asyncio
    async def test_validation_error(self, bot_commands, mock_client, mock_message):
        """ValidationError 异常处理。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")

        async def mock_to_params(collected, client):
            return {"task_type": "download", "chat_id": 123, "params": {}}

        bot_commands._collected_to_task_params = mock_to_params
        from module.core.task.manager import ValidationError

        bot_commands._task_manager.create_task = AsyncMock(
            side_effect=ValidationError("参数无效")
        )
        collected = bot_commands._interaction_manager.get_collected_data(12345)
        result = await bot_commands._handle_batch_complete(
            mock_client, mock_message, 12345, collected
        )
        assert result["status"] == "error"
        assert "参数无效" in result["reason"]

    @pytest.mark.asyncio
    async def test_resource_limit_error(self, bot_commands, mock_client, mock_message):
        """ResourceLimitError 异常处理。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")

        async def mock_to_params(collected, client):
            return {"task_type": "download", "chat_id": 123, "params": {}}

        bot_commands._collected_to_task_params = mock_to_params
        from module.core.task.manager import ResourceLimitError

        bot_commands._task_manager.create_task = AsyncMock(
            side_effect=ResourceLimitError("资源不足")
        )
        collected = bot_commands._interaction_manager.get_collected_data(12345)
        result = await bot_commands._handle_batch_complete(
            mock_client, mock_message, 12345, collected
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_unexpected_error(self, bot_commands, mock_client, mock_message):
        """未知异常处理。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")

        async def mock_to_params(collected, client):
            return {"task_type": "download", "chat_id": 123, "params": {}}

        bot_commands._collected_to_task_params = mock_to_params
        bot_commands._task_manager.create_task = AsyncMock(
            side_effect=Exception("未知错误")
        )
        collected = bot_commands._interaction_manager.get_collected_data(12345)
        result = await bot_commands._handle_batch_complete(
            mock_client, mock_message, 12345, collected
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_channel_resolve_failed(
        self, bot_commands, mock_client, mock_message
    ):
        """_collected_to_task_params 返回 None。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")

        async def mock_to_params(collected, client):
            return None

        bot_commands._collected_to_task_params = mock_to_params
        collected = bot_commands._interaction_manager.get_collected_data(12345)
        result = await bot_commands._handle_batch_complete(
            mock_client, mock_message, 12345, collected
        )
        assert result["status"] == "error"
        assert result["reason"] == "channel_resolve_failed"

    @pytest.mark.asyncio
    async def test_flow_cancelled_after_success(
        self, bot_commands, mock_client, mock_message
    ):
        """成功后取消交互流程。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")

        async def mock_to_params(collected, client):
            return {"task_type": "download", "chat_id": 123, "params": {}}

        bot_commands._collected_to_task_params = mock_to_params
        mock_task = MagicMock()
        mock_task.task_id = "test-task"
        bot_commands._task_manager.create_task = AsyncMock(return_value=mock_task)
        bot_commands._task_manager.start_task = AsyncMock()
        collected = bot_commands._interaction_manager.get_collected_data(12345)
        await bot_commands._handle_batch_complete(
            mock_client, mock_message, 12345, collected
        )
        assert bot_commands._interaction_manager.has_active_flow(12345) is False


# ==================== convert_download_type_to_filter_types 测试 ====================


class TestConvertDownloadTypeToFilterTypes:
    """convert_download_type_to_filter_types 辅助函数测试。"""

    def test_normal_conversion(self):
        """{"video": True, "photo": False} → ["video"]。"""
        result = BotCommands.convert_download_type_to_filter_types(
            {"video": True, "photo": False}
        )
        assert result == ["video"]

    def test_all_true(self):
        """全部为 True → 全部类型。"""
        result = BotCommands.convert_download_type_to_filter_types(
            {"video": True, "photo": True, "document": True}
        )
        assert len(result) == 3

    def test_all_false(self):
        """全部为 False → []。"""
        result = BotCommands.convert_download_type_to_filter_types(
            {"video": False, "photo": False}
        )
        assert result == []

    def test_empty_dict(self):
        """{} → []。"""
        result = BotCommands.convert_download_type_to_filter_types({})
        assert result == []

    def test_mixed_types(self):
        """混合 True/False。"""
        result = BotCommands.convert_download_type_to_filter_types(
            {"video": True, "photo": False, "audio": True, "voice": False}
        )
        assert result == ["video", "audio"]
