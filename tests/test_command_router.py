# coding=UTF-8
"""命令路由模块单元测试。

测试 module/command_router.py 中的 CommandRouter 类：
- 帮助/开始/表格命令
- 下载命令解析
- 转发命令解析
- 上传命令解析
- 监听命令解析
- 关键词输入处理
- 错误消息处理
- 回调数据处理

使用 mock 模拟 Pyrogram 客户端，不实际连接 Telegram。
"""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from module.bot.command_router import CommandRouter
from module.bot.state_manager import StateManager
from module.core.identifier_service import (
    IdentifierService,
    ResolvedChat,
    InvalidIdentifierError,
    UserNotFoundError,
    AccessDeniedError,
    RateLimitedError,
)
from module.core.enums import BotCallbackText


# ==================== Fixtures ====================


@pytest.fixture
def mock_identifier_service():
    """提供可配置的 mock IdentifierService。"""
    service = MagicMock(spec=IdentifierService)

    def _resolve_side_effect(link):
        # 根据输入返回不同 chat_id，便于 listen_forward 测试
        if "target" in link or "forward" in link:
            chat_id = -1009876543210
        elif "source" in link or "listen" in link:
            chat_id = -1001111111111
        else:
            chat_id = -1001234567890
        return ResolvedChat(
            chat_id=chat_id,
            chat_type="channel",
            chat_name="Test Channel",
            username="testchannel",
            message_count=-1,
            media_count=-1,
            has_access=True,
            is_private=False,
        )

    service.resolve = AsyncMock(side_effect=_resolve_side_effect)
    return service


@pytest.fixture(autouse=True)
def reset_bot_callback_text():
    """每个测试结束后重置 BotCallbackText.DOWNLOAD_CHAT_ID。"""
    original = BotCallbackText.DOWNLOAD_CHAT_ID
    yield
    BotCallbackText.DOWNLOAD_CHAT_ID = original


@pytest.fixture
def mock_client():
    """模拟 Pyrogram 客户端。"""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.edit_message_text = AsyncMock()
    client.delete_messages = AsyncMock()
    client.name = "test_bot"
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
def state():
    """提供 StateManager 实例。"""
    return StateManager()


@pytest.fixture
def mock_task_manager():
    """提供 mock TaskManager。"""

    tm = MagicMock()
    tm.create_task = AsyncMock()
    tm.get_task = AsyncMock()
    tm.list_tasks = AsyncMock(return_value=([], 0))
    tm.cancel_task = AsyncMock()
    return tm


@pytest.fixture
def mock_task_executor():
    """提供 mock TaskExecutor。"""
    te = MagicMock()
    te.cancel_listen_task = AsyncMock()
    return te


@pytest.fixture
def router(state, mock_identifier_service, mock_task_manager, mock_task_executor):
    """提供注入 mock 依赖的 CommandRouter 实例。"""
    return CommandRouter(
        state,
        identifier_service=mock_identifier_service,
        task_manager=mock_task_manager,
        task_executor=mock_task_executor,
    )


# ==================== 初始化测试 ====================


class TestCommandRouterInit:
    """CommandRouter 初始化测试。"""

    def test_create_with_state_manager(self, state):
        """应能使用 StateManager 创建实例。"""
        router = CommandRouter(state)
        assert router.state_manager is state

    def test_keyboard_manager_auto_create(self, state):
        """未传入 KeyboardManager 时应自动创建。"""
        router = CommandRouter(state)
        assert router.keyboard_manager is not None

    def test_create_with_custom_keyboard(self, state):
        """应支持传入自定义 KeyboardManager。"""
        from module.bot.keyboard_manager import KeyboardManager

        km = KeyboardManager()
        router = CommandRouter(state, km)
        assert router.keyboard_manager is km


# ==================== 帮助/开始/表格命令测试 ====================


class TestHelpStartTable:
    """帮助/开始/表格命令测试。"""

    @pytest.mark.asyncio
    async def test_help_sends_message(self, router, mock_client, mock_message):
        """help 应发送消息。"""
        await router.help(mock_client, mock_message)
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_returns_dict_without_client(self, router):
        """help 无 client 时应返回 dict。"""
        result = await router.help()
        assert result is not None
        assert "keyboard" in result
        assert "text" in result

    @pytest.mark.asyncio
    async def test_start_delegates_to_help(self, router, mock_client, mock_message):
        """start 应委托给 help。"""
        await router.start(mock_client, mock_message)
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_table_sends_message(self, router, mock_client, mock_message):
        """table 应发送消息。"""
        await router.table(mock_client, mock_message)
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_table_returns_dict_without_client(self, router):
        """table 无 client 时应返回 dict。"""
        result = await router.table()
        assert result is not None
        assert "keyboard" in result
        assert "text" in result


# ==================== 下载命令测试 ====================


class TestDownloadCommand:
    """下载命令解析测试。"""

    @pytest.mark.asyncio
    async def test_download_no_link(self, router, mock_client, mock_message):
        """/download 无链接时应提示错误。"""
        mock_message.text = "/download"
        await router.get_download_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "请提供下载链接" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_with_link(self, router, mock_client, mock_message):
        """/download 有链接时应返回解析结果。"""
        mock_message.text = "/download https://t.me/test/123"
        result = await router.get_download_link_from_bot(mock_client, mock_message)
        assert result is not None
        assert "right_link" in result
        assert "https://t.me/test/123" in str(result["right_link"])

    @pytest.mark.asyncio
    async def test_download_multiple_links(self, router, mock_client, mock_message):
        """/download 多条链接时应全部解析。"""
        mock_message.text = (
            "/download https://t.me/a/1 https://t.me/b/2 https://t.me/c/3"
        )
        result = await router.get_download_link_from_bot(mock_client, mock_message)
        assert result is not None
        assert len(result["right_link"]) == 3

    @pytest.mark.asyncio
    async def test_download_with_invalid_links(self, router, mock_client, mock_message):
        """/download 混合链接时应分离有效和无效。"""
        mock_message.text = "/download https://t.me/a/1 bad_link"
        result = await router.get_download_link_from_bot(mock_client, mock_message)
        assert result is not None
        assert len(result["right_link"]) == 1
        assert len(result["invalid_link"]) == 1

    @pytest.mark.asyncio
    async def test_download_from_telegram_link(self, router, mock_client, mock_message):
        """直接发送 Telegram 链接应尝试删除并重定向。"""
        mock_message.text = "https://t.me/test/123"
        mock_client.delete_messages = AsyncMock()
        mock_bot_client = MagicMock()
        mock_bot_client.get_me = AsyncMock(return_value=MagicMock(username="test_bot"))
        await router.get_download_link_from_bot(
            mock_client, mock_message, mock_bot_client, mock_bot_client
        )
        mock_client.delete_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_range(self, router, mock_client, mock_message):
        """/download 范围下载应生成范围内的所有链接。"""
        mock_message.text = "/download https://t.me/a 1 3"
        result = await router.get_download_link_from_bot(mock_client, mock_message)
        assert result is not None
        assert len(result["right_link"]) == 3
        assert "https://t.me/a/1?single" in result["right_link"]
        assert "https://t.me/a/3?single" in result["right_link"]

    @pytest.mark.asyncio
    async def test_download_range_invalid(self, router, mock_client, mock_message):
        """/download 范围错误时应返回 None。"""
        mock_message.text = "/download https://t.me/a 100 1"
        result = await router.get_download_link_from_bot(mock_client, mock_message)
        assert result is None
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "起始ID>结束ID" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_short_text(self, router, mock_client, mock_message):
        """短文本应触发帮助提示。"""
        mock_message.text = "hi"
        await router.get_download_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called()
        # 应调用两次：帮助 + 链接错误提示
        assert mock_client.send_message.call_count >= 2


# ==================== 转发命令测试 ====================


class TestForwardCommand:
    """转发命令解析测试。"""

    @pytest.mark.asyncio
    async def test_forward_no_args(self, router, mock_client, mock_message):
        """/forward 无参数时应提示语法错误。"""
        mock_message.text = "/forward"
        result = await router.get_forward_link_from_bot(mock_client, mock_message)
        assert result is None
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_valid_args(self, router, mock_client, mock_message):
        """/forward 有效参数时应返回解析结果。"""
        mock_message.text = "/forward https://t.me/source https://t.me/target 1 100"
        result = await router.get_forward_link_from_bot(mock_client, mock_message)
        assert result is not None
        assert result["origin_link"] == "https://t.me/source"
        assert result["target_link"] == "https://t.me/target"
        assert result["message_range"] == [1, 100]

    @pytest.mark.asyncio
    async def test_forward_invalid_range(self, router, mock_client, mock_message):
        """/forward 范围错误时应返回 None。"""
        mock_message.text = "/forward https://t.me/source https://t.me/target 100 1"
        result = await router.get_forward_link_from_bot(mock_client, mock_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_forward_bad_args(self, router, mock_client, mock_message):
        """/forward 参数格式错误时应提示。"""
        mock_message.text = "/forward https://t.me/source https://t.me/target abc def"
        result = await router.get_forward_link_from_bot(mock_client, mock_message)
        assert result is None
        mock_client.send_message.assert_called_once()


# ==================== 上传命令测试 ====================


class TestUploadCommand:
    """上传命令解析测试。"""

    @pytest.mark.asyncio
    async def test_upload_no_args(self, router, mock_client, mock_message):
        """/upload 无参数时应提示语法错误。"""
        mock_message.text = "/upload"
        result = await router.get_upload_link_from_bot(mock_client, mock_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, router, mock_client, mock_message):
        """/upload 文件不存在时应提示。"""
        mock_message.text = "/upload /nonexistent/file.txt https://t.me/target"
        with (
            patch("os.path.isfile", return_value=False),
            patch("os.path.isdir", return_value=False),
        ):
            result = await router.get_upload_link_from_bot(mock_client, mock_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_upload_no_command(self, router, mock_client, mock_message):
        """非 upload 命令应返回 None。"""
        mock_message.text = "/random_command"
        result = await router.get_upload_link_from_bot(mock_client, mock_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_upload_folder_empty(self, router, mock_client, mock_message):
        """/upload 文件夹为空时应提示。"""
        mock_message.text = "/upload /empty_folder https://t.me/target"
        with (
            patch("os.path.isdir", return_value=True),
            patch("module.utils.path_tool.safe_scan_directory_file", return_value=[]),
        ):
            result = await router.get_upload_link_from_bot(mock_client, mock_message)
        assert result is None


# ==================== 退出命令测试 ====================


class TestExit:
    """退出命令测试。"""

    @pytest.mark.asyncio
    async def test_exit_raises_system_exit(self, router, mock_client, mock_message):
        """exit_bot 应引发 SystemExit(0)。"""
        with pytest.raises(SystemExit) as exc_info:
            await router.exit_bot(mock_client, mock_message)
        assert exc_info.value.code == 0
        mock_client.send_message.assert_called_once()


# ==================== 监听命令测试 ====================


class TestListenCommands:
    """监听命令测试。"""

    @pytest.mark.asyncio
    async def test_listen_download_no_args(self, router, mock_client, mock_message):
        """/listen_download 无参数时应提示语法错误。"""
        mock_message.text = "/listen_download"
        result = await router.on_listen(mock_client, mock_message)
        assert result is None
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_download_valid(
        self, router, mock_client, mock_message, mock_task_manager
    ):
        """/listen_download 有效链接应调用 TaskManager.create_task。"""
        from module.core.task_manager import Task, TaskType, TaskStatus

        mock_task = Task(
            task_id="test_task_id_12345678",
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            status=TaskStatus.PENDING,
            params={"source_identifier": "https://t.me/channel1"},
        )
        mock_task_manager.create_task = AsyncMock(return_value=mock_task)
        mock_task_manager.get_task = AsyncMock(return_value=mock_task)

        mock_message.text = "/listen_download https://t.me/channel1"
        result = await router.on_listen(mock_client, mock_message)
        assert result is None
        mock_task_manager.create_task.assert_called_once()
        mock_client.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_listen_forward_no_args(self, router, mock_client, mock_message):
        """/listen_forward 无参数时应提示语法错误。"""
        mock_message.text = "/listen_forward"
        result = await router.on_listen(mock_client, mock_message)
        assert result is None
        mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_forward_one_arg(self, router, mock_client, mock_message):
        """/listen_forward 只有一个参数时应提示。"""
        mock_message.text = "/listen_forward https://t.me/source"
        result = await router.on_listen(mock_client, mock_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_listen_forward_valid(
        self,
        router,
        mock_client,
        mock_message,
        mock_task_manager,
        mock_identifier_service,
    ):
        """/listen_forward 有效参数应调用 TaskManager.create_task。"""
        from module.core.task_manager import Task, TaskType, TaskStatus

        mock_task = Task(
            task_id="test_task_id_87654321",
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            status=TaskStatus.PENDING,
            params={
                "source_identifier": "https://t.me/source",
                "target_identifier": "https://t.me/target",
                "target_chat_id": -1009876543210,
            },
        )
        mock_task_manager.create_task = AsyncMock(return_value=mock_task)
        mock_task_manager.get_task = AsyncMock(return_value=mock_task)

        mock_message.text = "/listen_forward https://t.me/source https://t.me/target"
        result = await router.on_listen(mock_client, mock_message)
        assert result is None
        mock_task_manager.create_task.assert_called_once()
        mock_client.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_listen_forward_invalid_link(
        self, router, mock_client, mock_message, mock_identifier_service
    ):
        """/listen_forward 无效链接时应提示。"""

        def _resolve(link):
            if link == "bad_link":
                raise InvalidIdentifierError()
            return ResolvedChat(
                chat_id=-1009876543210 if "target" in link else -1001111111111,
                chat_type="channel",
                chat_name="Test",
                username="test",
                message_count=-1,
                media_count=-1,
                has_access=True,
                is_private=False,
            )

        mock_identifier_service.resolve = AsyncMock(side_effect=_resolve)
        mock_message.text = "/listen_forward bad_link https://t.me/target"
        result = await router.on_listen(mock_client, mock_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_listen_info_no_listens(
        self, router, mock_client, mock_message, mock_task_manager
    ):
        """无监听任务时应提示没有监听。"""
        mock_task_manager.list_tasks = AsyncMock(return_value=([], 0))
        mock_message.text = "/listen_info"
        await router.listen_info(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "没有" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_listen_info_with_listens(
        self, router, mock_client, mock_message, mock_task_manager
    ):
        """有监听任务时应从 TaskManager 查询并显示。"""
        from module.core.task_manager import Task, TaskType, TaskStatus

        mock_download_task = Task(
            task_id="dl_task_id_12345678",
            task_type=TaskType.LISTEN_DOWNLOAD,
            chat_id=-1001234567890,
            status=TaskStatus.RUNNING,
            params={"source_identifier": "https://t.me/test"},
        )
        mock_task_manager.list_tasks = AsyncMock(return_value=([mock_download_task], 1))
        mock_message.text = "/listen_info"
        await router.listen_info(mock_client, mock_message)
        mock_client.send_message.assert_called()
        # 验证 list_tasks 被调用
        assert mock_task_manager.list_tasks.call_count >= 2

    @pytest.mark.asyncio
    async def test_listen_info_with_forward_tasks(
        self, router, mock_client, mock_message, mock_task_manager
    ):
        """有监听转发任务时应从 TaskManager 查询并显示。"""
        from module.core.task_manager import Task, TaskType, TaskStatus

        mock_forward_task = Task(
            task_id="fw_task_id_87654321",
            task_type=TaskType.LISTEN_FORWARD,
            chat_id=-1001234567890,
            status=TaskStatus.RUNNING,
            params={
                "source_identifier": "https://t.me/src",
                "target_identifier": "https://t.me/dst",
            },
        )

        # 第一个调用返回空下载列表，第二个调用返回转发列表
        mock_task_manager.list_tasks = AsyncMock(
            side_effect=[
                ([], 0),  # 下载任务
                ([mock_forward_task], 1),  # 转发任务
            ]
        )
        mock_message.text = "/listen_info"
        await router.listen_info(mock_client, mock_message)
        mock_client.send_message.assert_called()
        args, kwargs = mock_client.send_message.call_args
        assert "监听转发" in kwargs["text"]


# ==================== 关键词输入处理测试 ====================


class TestKeywordInput:
    """关键词输入处理测试。"""

    @pytest.mark.asyncio
    async def test_handle_keyword_input_new_keyword(self, router):
        """新关键词应被添加。"""
        mock_msg = MagicMock()
        mock_msg.text = "test_keyword"
        mock_msg.strip = lambda: "test_keyword"
        mock_cq = MagicMock()
        mock_cq.message.edit_text = AsyncMock()

        await router.handle_keyword_input(
            chat_id="channel_123",
            callback_query=mock_cq,
            callback_prompt=lambda: "请输入关键词:",
            _client=MagicMock(),
            message=mock_msg,
        )

        assert router.state_manager.has_added_keyword("test_keyword")

    @pytest.mark.asyncio
    async def test_handle_keyword_input_empty(self, router):
        """空文本不应添加关键词。"""
        mock_msg = MagicMock()
        mock_msg.text = "   "
        mock_msg.strip = lambda: ""
        mock_cq = MagicMock()

        await router.handle_keyword_input(
            chat_id="channel_123",
            callback_query=mock_cq,
            callback_prompt=lambda: "请输入关键词:",
            _client=MagicMock(),
            message=mock_msg,
        )
        # 不应有关键词被添加
        assert router.state_manager.adding_keywords == []


# ==================== 错误消息处理测试 ====================


class TestErrorHandling:
    """错误消息处理测试。"""

    @pytest.mark.asyncio
    async def test_process_error_message(self, router, mock_client, mock_message):
        """process_error_message 应发送帮助消息。"""
        await router.process_error_message(mock_client, mock_message)
        mock_client.send_message.assert_called()
        assert mock_client.send_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_process_error_message_with_handler(
        self, router, mock_client, mock_message
    ):
        """存在 keyword_handler 时应跳过不处理。"""
        mock_handler = MagicMock()
        await router.process_error_message(mock_client, mock_message, mock_handler)
        mock_client.send_message.assert_not_called()


# ==================== 回调数据处理测试 ====================


class TestCallbackData:
    """回调数据处理测试。"""

    @pytest.mark.asyncio
    async def test_callback_data_returns_string(self):
        """callback_data 应返回回调数据字符串。"""
        mock_client = AsyncMock()
        mock_cq = MagicMock()
        mock_cq.answer = AsyncMock()
        mock_cq.data = "test_data"

        result = await CommandRouter.callback_data(mock_client, mock_cq)
        assert result == "test_data"

    @pytest.mark.asyncio
    async def test_callback_data_none(self):
        """callback_data 为空时应返回 None。"""
        mock_client = AsyncMock()
        mock_cq = MagicMock()
        mock_cq.answer = AsyncMock()
        mock_cq.data = None

        result = await CommandRouter.callback_data(mock_client, mock_cq)
        assert result is None

    @pytest.mark.asyncio
    async def test_callback_data_not_string(self):
        """callback_data 非字符串时应返回 None。"""
        mock_client = AsyncMock()
        mock_cq = MagicMock()
        mock_cq.answer = AsyncMock()
        mock_cq.data = b"bytes_data"

        result = await CommandRouter.callback_data(mock_client, mock_cq)
        assert result is None


# ==================== REMOVE_LISTEN 回调测试 ====================


class TestRemoveListenCallback:
    """REMOVE_LISTEN_* 回调处理测试。"""

    @pytest.mark.asyncio
    async def test_remove_listen_download_callback(
        self, router, mock_client, mock_task_executor
    ):
        """rld_{task_id} 回调应调用 cancel_listen_task。"""
        from pyrogram.types.bots_and_keyboards import CallbackQuery

        mock_cq = MagicMock(spec=CallbackQuery)
        mock_cq.answer = AsyncMock()
        mock_cq.data = "rld_test_task_id_12345678"
        mock_cq.message = MagicMock()
        mock_cq.message.edit_text = AsyncMock()

        result = await router.handle_remove_listen_callback(mock_client, mock_cq)
        assert result is True
        mock_task_executor.cancel_listen_task.assert_called_once_with(
            "test_task_id_12345678"
        )
        mock_cq.message.edit_text.assert_called()

    @pytest.mark.asyncio
    async def test_remove_listen_forward_callback(
        self, router, mock_client, mock_task_executor
    ):
        """rlf_{task_id} 回调应调用 cancel_listen_task。"""
        from pyrogram.types.bots_and_keyboards import CallbackQuery

        mock_cq = MagicMock(spec=CallbackQuery)
        mock_cq.answer = AsyncMock()
        mock_cq.data = "rlf_test_task_id_87654321"
        mock_cq.message = MagicMock()
        mock_cq.message.edit_text = AsyncMock()

        result = await router.handle_remove_listen_callback(mock_client, mock_cq)
        assert result is True
        mock_task_executor.cancel_listen_task.assert_called_once_with(
            "test_task_id_87654321"
        )
        mock_cq.message.edit_text.assert_called()

    @pytest.mark.asyncio
    async def test_remove_listen_callback_no_executor(self, router, mock_client):
        """无 TaskExecutor 时回调应优雅降级。"""
        from pyrogram.types.bots_and_keyboards import CallbackQuery

        # 使用没有 task_executor 的 router
        router_no_exec = CommandRouter(
            StateManager(),
            identifier_service=MagicMock(),
            task_manager=MagicMock(),
        )

        mock_cq = MagicMock(spec=CallbackQuery)
        mock_cq.answer = AsyncMock()
        mock_cq.data = "rld_test_task_id"
        mock_cq.message = MagicMock()
        mock_cq.message.edit_text = AsyncMock()

        result = await router_no_exec.handle_remove_listen_callback(
            mock_client, mock_cq
        )
        assert result is True
        mock_cq.message.edit_text.assert_called()

    @pytest.mark.asyncio
    async def test_remove_listen_callback_unknown_format(self, router, mock_client):
        """未知格式回调应返回 False。"""
        from pyrogram.types.bots_and_keyboards import CallbackQuery

        mock_cq = MagicMock(spec=CallbackQuery)
        mock_cq.answer = AsyncMock()
        mock_cq.data = "unknown_callback_data"
        mock_cq.message = MagicMock()
        mock_cq.message.edit_text = AsyncMock()

        result = await router.handle_remove_listen_callback(mock_client, mock_cq)
        assert result is False


# ==================== 下载频道命令测试 ====================


class TestDownloadChatCommand:
    """get_download_chat_link_from_bot 测试。"""

    @pytest.mark.asyncio
    async def test_download_chat_no_args(self, router, mock_client, mock_message):
        """/download_chat 无参数时应提示语法。"""
        mock_message.text = "/download_chat"
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "请提供下载链接" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_wrong_arg_count(
        self, router, mock_client, mock_message
    ):
        """/download_chat 参数数量错误时应提示。"""
        mock_message.text = "/download_chat link1 link2"
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        # 应调用 help + 错误提示
        assert mock_client.send_message.call_count == 2
        args, kwargs = mock_client.send_message.call_args
        assert "命令语法错误" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_not_found(
        self, router, mock_client, mock_message, mock_identifier_service
    ):
        """/download_chat 解析不到频道时应提示找不到频道。"""
        mock_message.text = "/download_chat https://t.me/notfound"
        mock_identifier_service.resolve = AsyncMock(side_effect=UserNotFoundError())
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "找不到频道" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_access_denied(
        self, router, mock_client, mock_message, mock_identifier_service
    ):
        """/download_chat 无权访问时应提示无权访问。"""
        mock_message.text = "/download_chat https://t.me/private"
        mock_identifier_service.resolve = AsyncMock(side_effect=AccessDeniedError())
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "无权访问" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_invalid_identifier(
        self, router, mock_client, mock_message, mock_identifier_service
    ):
        """/download_chat 无效标识符时应提示格式无效。"""
        mock_message.text = "/download_chat bad_link"
        mock_identifier_service.resolve = AsyncMock(
            side_effect=InvalidIdentifierError()
        )
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "格式无效" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_rate_limited(
        self, router, mock_client, mock_message, mock_identifier_service
    ):
        """/download_chat 触发限流时应提示稍后重试。"""
        mock_message.text = "/download_chat https://t.me/busy"
        mock_identifier_service.resolve = AsyncMock(
            side_effect=RateLimitedError(retry_after=30)
        )
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "过于频繁" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_already_exists(
        self, router, mock_client, mock_message
    ):
        """/download_chat 频道已存在时应提示。"""
        mock_message.text = "/download_chat https://t.me/test"
        router.state_manager.create_download_filter("-1001234567890")
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "已在下载中" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_success(self, router, mock_client, mock_message):
        """/download_chat 成功时应创建过滤器并发送状态消息。"""
        mock_message.text = "/download_chat https://t.me/test"
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        # 应创建过滤器并发送消息
        assert router.state_manager.has_download_filter("-1001234567890") is True
        mock_client.send_message.assert_called_once()
        args, kwargs = mock_client.send_message.call_args
        assert "下载频道" in kwargs["text"]
        assert "-1001234567890" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_download_chat_supports_username(
        self, router, mock_client, mock_message, mock_identifier_service
    ):
        """/download_chat 应支持 @username 输入。"""
        mock_message.text = "/download_chat @testchannel"
        await router.get_download_chat_link_from_bot(mock_client, mock_message)
        mock_identifier_service.resolve.assert_awaited_once_with("@testchannel")
        assert router.state_manager.has_download_filter("-1001234567890") is True


# ==================== 关键词模式 Handler 管理测试 ====================


class TestAddKeywordModeHandler:
    """add_keyword_mode_handler 静态方法测试。"""

    @pytest.fixture
    def add_handler_fn(self):
        return MagicMock()

    @pytest.fixture
    def remove_handler_fn(self):
        return MagicMock()

    @pytest.fixture
    def callback_query(self):
        cq = MagicMock()
        cq.message.edit_text = AsyncMock()
        cq.message.reply_text = AsyncMock()
        return cq

    @pytest.fixture
    def callback_prompt(self):
        return MagicMock(return_value="请输入关键词:")

    @pytest.fixture
    def handle_keyword_fn(self):
        return MagicMock()

    def test_add_keyword_mode_handler_enable(
        self,
        add_handler_fn,
        remove_handler_fn,
        callback_query,
        callback_prompt,
        handle_keyword_fn,
    ):
        """enable=True 时应创建并添加 handler。"""
        result = CommandRouter.add_keyword_mode_handler(
            add_handler_fn=add_handler_fn,
            remove_handler_fn=remove_handler_fn,
            root=[12345],
            chat_id="channel_123",
            callback_query=callback_query,
            callback_prompt=callback_prompt,
            handle_keyword_fn=handle_keyword_fn,
            enable=True,
        )
        assert result is not None
        add_handler_fn.assert_called_once()
        # handler 应添加到 group=-1（通过 kwargs 传递）
        _, call_kwargs = add_handler_fn.call_args
        assert call_kwargs.get("group") == -1

    def test_add_keyword_mode_handler_disable(
        self,
        add_handler_fn,
        remove_handler_fn,
        callback_query,
        callback_prompt,
        handle_keyword_fn,
    ):
        """enable=False 时应移除已有 handler。"""
        result = CommandRouter.add_keyword_mode_handler(
            add_handler_fn=add_handler_fn,
            remove_handler_fn=remove_handler_fn,
            root=[12345],
            chat_id="channel_123",
            callback_query=callback_query,
            callback_prompt=callback_prompt,
            handle_keyword_fn=handle_keyword_fn,
            enable=False,
        )
        assert result is None
        remove_handler_fn.assert_called_once_with(None, group=-1)
