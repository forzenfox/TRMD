# coding=UTF-8
"""BotCommands /setup_repository 命令单元测试。

测试 /setup_repository 命令逻辑：
- 命令注册在 COMMANDS 列表中
- 频道 ID 格式验证
- 邀请链接解析（mock client）
- 成功时保存配置
- 无效输入的错误处理
- 权限不足的错误处理

使用 mock 模拟 Pyrogram 客户端，不实际连接 Telegram。
"""

from unittest.mock import MagicMock, AsyncMock

import pytest

from module.bot_commands import BotCommands
from module.interaction_manager import InteractionManager
from module.core.token_manager import TokenManager
from module.core.config_manager import ConfigManager


# ==================== Fixtures ====================


@pytest.fixture
def mock_client():
    """模拟 Pyrogram 客户端。"""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.get_chat = AsyncMock()
    client.get_chat_member = AsyncMock()
    return client


@pytest.fixture
def mock_message():
    """模拟 Pyrogram 消息对象。"""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.id = 100
    message.text = "/setup_repository"
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
def mock_user_config():
    """模拟 UserConfig。"""
    user_config = MagicMock()
    user_config.config = {}
    user_config.get_config.return_value = {}
    user_config.save_config.return_value = True
    return user_config


@pytest.fixture
def config_manager(mock_user_config):
    """提供 ConfigManager 实例。"""
    return ConfigManager(user_config=mock_user_config)


@pytest.fixture
def bot_commands(token_manager, interaction_manager, config_manager):
    """提供 BotCommands 实例（含 config_manager）。"""
    return BotCommands(
        token_manager=token_manager,
        interaction_manager=interaction_manager,
        config_manager=config_manager,
        webui_base_url="http://localhost:8000",
    )


# ==================== 命令注册测试 ====================


class TestSetupRepositoryRegistration:
    """setup_repository 命令注册测试。"""

    def test_setup_repository_in_commands_list(self, bot_commands):
        """setup_repository 应在 COMMANDS 列表中。"""
        cmd_names = [c[0] for c in bot_commands.get_commands()]
        assert "setup_repository" in cmd_names

    def test_setup_repository_has_description(self, bot_commands):
        """setup_repository 命令应有描述文本。"""
        commands = bot_commands.get_commands()
        for name, desc in commands:
            if name == "setup_repository":
                assert isinstance(desc, str)
                assert len(desc) > 0
                return
        pytest.fail("setup_repository 命令未在 COMMANDS 中找到")


# ==================== 频道 ID 格式验证测试 ====================


class TestChannelIdValidation:
    """频道 ID 格式验证测试。"""

    def test_valid_numeric_channel_id(self, bot_commands):
        """纯数字频道 ID（带负号前缀）应通过验证。"""
        assert bot_commands.validate_channel_input("-1001234567890") is not None

    def test_valid_positive_channel_id(self, bot_commands):
        """正数频道 ID 应通过验证。"""
        assert bot_commands.validate_channel_input("1234567890") is not None

    def test_valid_username_with_at(self, bot_commands):
        """@username 格式应通过验证。"""
        result = bot_commands.validate_channel_input("@my_repo")
        assert result is not None

    def test_valid_t_me_link(self, bot_commands):
        """https://t.me/channel 格式应通过验证。"""
        result = bot_commands.validate_channel_input("https://t.me/my_repo")
        assert result is not None

    def test_valid_invite_link(self, bot_commands):
        """https://t.me/+AbCdEf 邀请链接格式应通过验证。"""
        result = bot_commands.validate_channel_input("https://t.me/+AbCdEfGhIjK")
        assert result is not None

    def test_invalid_empty_input(self, bot_commands):
        """空输入应验证失败。"""
        assert bot_commands.validate_channel_input("") is None

    def test_invalid_random_text(self, bot_commands):
        """随机文本应验证失败。"""
        assert bot_commands.validate_channel_input("hello world") is None

    def test_invalid_partial_link(self, bot_commands):
        """不完整的链接应验证失败。"""
        assert bot_commands.validate_channel_input("https://t.me/") is None


# ==================== 邀请链接解析测试 ====================


class TestInviteLinkResolution:
    """邀请链接解析测试。"""

    @pytest.mark.asyncio
    async def test_resolve_numeric_id_directly(self, bot_commands, mock_client):
        """纯数字 ID 应直接返回，无需网络请求。"""
        result = await bot_commands.resolve_channel_id(mock_client, "-1001234567890")
        assert result == "-1001234567890"
        mock_client.get_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_username_via_get_chat(self, bot_commands, mock_client):
        """@username 应通过 get_chat 解析。"""
        mock_chat = MagicMock()
        mock_chat.id = -1001234567890
        mock_client.get_chat.return_value = mock_chat

        result = await bot_commands.resolve_channel_id(mock_client, "@my_repo")
        assert result == "-1001234567890"
        mock_client.get_chat.assert_called_once_with("@my_repo")

    @pytest.mark.asyncio
    async def test_resolve_t_me_link_via_get_chat(self, bot_commands, mock_client):
        """https://t.me/channel 应通过 get_chat 解析。"""
        mock_chat = MagicMock()
        mock_chat.id = -1001234567890
        mock_client.get_chat.return_value = mock_chat

        result = await bot_commands.resolve_channel_id(
            mock_client, "https://t.me/my_repo"
        )
        assert result == "-1001234567890"
        mock_client.get_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_invite_link_via_get_chat(self, bot_commands, mock_client):
        """https://t.me/+xxx 邀请链接应通过 get_chat 解析。"""
        mock_chat = MagicMock()
        mock_chat.id = -1001234567890
        mock_client.get_chat.return_value = mock_chat

        result = await bot_commands.resolve_channel_id(
            mock_client, "https://t.me/+AbCdEfGhIjK"
        )
        assert result == "-1001234567890"
        mock_client.get_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_invalid_channel_raises(self, bot_commands, mock_client):
        """无法解析的频道应抛出异常。"""
        mock_client.get_chat.side_effect = Exception("Channel not found")

        with pytest.raises(Exception, match="Channel not found"):
            await bot_commands.resolve_channel_id(mock_client, "@nonexistent_channel")


# ==================== /setup_repository 命令测试 ====================


class TestCmdSetupRepository:
    """cmd_setup_repository 命令测试。"""

    @pytest.mark.asyncio
    async def test_no_argument_sends_welcome(
        self, bot_commands, mock_client, mock_message
    ):
        """无参数时应发送欢迎消息和使用说明。"""
        mock_message.text = "/setup_repository"
        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert (
            "仓库" in call_kwargs["text"] or "repository" in call_kwargs["text"].lower()
        )

    @pytest.mark.asyncio
    async def test_valid_channel_id_saves_config(
        self, bot_commands, mock_client, mock_message, config_manager
    ):
        """有效频道 ID 应保存到配置。"""
        mock_message.text = "/setup_repository -1001234567890"

        # mock get_chat_member for permission check
        mock_member = MagicMock()
        mock_member.status = "administrator"
        mock_client.get_chat_member.return_value = mock_member

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        # 验证配置已保存
        saved_config = config_manager.get_repository_config()
        assert saved_config.get("chat_id") == "-1001234567890"

    @pytest.mark.asyncio
    async def test_valid_channel_id_sends_success(
        self, bot_commands, mock_client, mock_message
    ):
        """有效频道 ID 应发送成功消息。"""
        mock_message.text = "/setup_repository -1001234567890"

        mock_member = MagicMock()
        mock_member.status = "administrator"
        mock_client.get_chat_member.return_value = mock_member

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "成功" in call_kwargs["text"] or "设置" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_invalid_input_sends_error(
        self, bot_commands, mock_client, mock_message
    ):
        """无效输入应发送错误消息。"""
        mock_message.text = "/setup_repository invalid_input"

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert (
            "无效" in call_kwargs["text"]
            or "格式" in call_kwargs["text"]
            or "错误" in call_kwargs["text"]
        )

    @pytest.mark.asyncio
    async def test_permission_denied_sends_error(
        self, bot_commands, mock_client, mock_message
    ):
        """权限不足应发送错误消息。"""
        mock_message.text = "/setup_repository -1001234567890"

        mock_member = MagicMock()
        mock_member.status = "member"
        mock_client.get_chat_member.return_value = mock_member

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "权限" in call_kwargs["text"] or "管理员" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_permission_check_not_admin(
        self, bot_commands, mock_client, mock_message
    ):
        """非管理员状态应被拒绝。"""
        mock_message.text = "/setup_repository -1001234567890"

        mock_member = MagicMock()
        mock_member.status = "left"
        mock_client.get_chat_member.return_value = mock_member

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "权限" in call_kwargs["text"] or "管理员" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_resolve_username_and_save(
        self, bot_commands, mock_client, mock_message, config_manager
    ):
        """@username 输入应解析并保存。"""
        mock_message.text = "/setup_repository @my_repo"

        mock_chat = MagicMock()
        mock_chat.id = -1009999999999
        mock_client.get_chat.return_value = mock_chat

        mock_member = MagicMock()
        mock_member.status = "administrator"
        mock_client.get_chat_member.return_value = mock_member

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        saved_config = config_manager.get_repository_config()
        assert saved_config.get("chat_id") == "-1009999999999"

    @pytest.mark.asyncio
    async def test_resolve_invite_link_and_save(
        self, bot_commands, mock_client, mock_message, config_manager
    ):
        """邀请链接输入应解析并保存。"""
        mock_message.text = "/setup_repository https://t.me/+AbCdEfGhIjK"

        mock_chat = MagicMock()
        mock_chat.id = -1008888888888
        mock_client.get_chat.return_value = mock_chat

        mock_member = MagicMock()
        mock_member.status = "administrator"
        mock_client.get_chat_member.return_value = mock_member

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        saved_config = config_manager.get_repository_config()
        assert saved_config.get("chat_id") == "-1008888888888"

    @pytest.mark.asyncio
    async def test_channel_not_found_sends_error(
        self, bot_commands, mock_client, mock_message
    ):
        """频道不存在应发送错误消息。"""
        mock_message.text = "/setup_repository @nonexistent_channel"

        mock_client.get_chat.side_effect = Exception("Channel not found")

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert (
            "不存在" in call_kwargs["text"]
            or "找不到" in call_kwargs["text"]
            or "错误" in call_kwargs["text"]
        )

    @pytest.mark.asyncio
    async def test_config_save_failure_sends_error(
        self, bot_commands, mock_client, mock_message, mock_user_config
    ):
        """配置保存失败应发送错误消息。"""
        mock_message.text = "/setup_repository -1001234567890"

        mock_member = MagicMock()
        mock_member.status = "administrator"
        mock_client.get_chat_member.return_value = mock_member

        # 让保存失败
        mock_user_config.save_config.return_value = False

        await bot_commands.cmd_setup_repository(mock_client, mock_message)

        # 应该发送了消息（可能是错误消息）
        assert mock_client.send_message.call_count >= 1
