# coding=UTF-8
"""BotCommands 单元测试。

测试新增/重构的 Bot 命令逻辑：
- /web 命令：生成 Token 并返回 WebUI 链接
- /batch 简化批量操作模式
- /status 命令的 WebUI 引导模式
- 复杂操作引导到 WebUI 的交互文案

使用 mock 模拟 Pyrogram 客户端，不实际连接 Telegram。
"""

from unittest.mock import MagicMock, AsyncMock

import pytest

from module.bot.commands import BotCommands
from module.interaction_manager import InteractionManager
from module.core.token_manager import TokenManager


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
    """提供内存模式的 TokenManager。"""
    return TokenManager(db_path=None, default_ttl=3600)


@pytest.fixture
def interaction_manager():
    """提供内存模式的 InteractionManager。"""
    return InteractionManager(timeout_seconds=300)


@pytest.fixture
def bot_commands(token_manager, interaction_manager):
    """提供 BotCommands 实例。"""
    return BotCommands(
        token_manager=token_manager,
        interaction_manager=interaction_manager,
        webui_base_url="http://localhost:8000",
    )


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
        """cmd_web 应向用户发送包含链接的消息。"""
        mock_message.text = "/web"
        await bot_commands.cmd_web(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "chat_id" in call_kwargs
        assert "text" in call_kwargs
        assert "http://localhost:8000" in call_kwargs["text"]

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
        """cmd_batch 应显示第一步的提示（源频道）。"""
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "源频道" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_batch_shows_cancel_hint(
        self, bot_commands, mock_client, mock_message
    ):
        """cmd_batch 应提示用户可以使用 /cancel 取消。"""
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "/cancel" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_batch_existing_flow(self, bot_commands, mock_client, mock_message):
        """用户已有活跃流程时应提示先完成或取消。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        mock_message.text = "/batch"
        await bot_commands.cmd_batch(mock_client, mock_message)

        call_kwargs = mock_client.send_message.call_args[1]
        assert "已有" in call_kwargs["text"] or "进行" in call_kwargs["text"]


# ==================== 批量输入收集测试 ====================


class TestBatchInputCollection:
    """批量操作流程的输入收集测试。"""

    @pytest.mark.asyncio
    async def test_handle_batch_input_collects_source(
        self, bot_commands, mock_client, mock_message
    ):
        """应收集源频道链接。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
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
        """应收集目标频道链接。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
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
        """应收集消息范围。"""
        bot_commands._interaction_manager.start_flow(user_id=12345, command="/batch")
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/source"
        )
        bot_commands._interaction_manager.collect(
            user_id=12345, input_text="https://t.me/target"
        )
        mock_message.text = "1 100"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        state = bot_commands._interaction_manager.get_active_flow(12345)
        assert state.collected_data.get("message_range") == "1 100"

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
        mock_message.text = "not_a_valid_link"
        mock_message.from_user.id = 12345
        await bot_commands.handle_batch_input(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "无效" in call_kwargs["text"] or "格式" in call_kwargs["text"]


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
