"""
E2E测试配置

定义测试凭证、测试频道、超时配置等。
支持从配置文件和环境变量读取配置，环境变量优先级更高。
"""

import os
from pathlib import Path
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 虚拟环境Python可执行文件路径
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
# 如果虚拟环境不存在，使用系统Python
SYSTEM_PYTHON = "python"
# 优先使用虚拟环境Python
PYTHON_EXECUTABLE = str(VENV_PYTHON) if VENV_PYTHON.exists() else SYSTEM_PYTHON

# 配置文件路径
CONFIG_FILE_PATH = Path(__file__).parent / "e2e_test_config.yaml"

# 默认值
DEFAULT_SERVER_PORT = 8800
DEFAULT_SERVER_START_TIMEOUT = 30
DEFAULT_TIMEOUT = 10000
DEFAULT_NAVIGATION_TIMEOUT = 15000
DEFAULT_API_RESPONSE_TIMEOUT = 15000


def _load_yaml_config() -> dict:
    """加载YAML配置文件"""
    try:
        import yaml

        if CONFIG_FILE_PATH.exists():
            with open(CONFIG_FILE_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                return config
    except ImportError:
        pass
    except Exception:
        pass
    return {}


def _get_config_value(
    key: str, env_key: Optional[str] = None, default: str = ""
) -> str:
    """
    获取配置值（优先级：环境变量 > 配置文件 > 默认值）

    Args:
        key: 配置文件中的key
        env_key: 环境变量名（如果不同）
        default: 默认值

    Returns:
        配置值
    """
    # 优先从环境变量获取
    env_name = env_key or key.upper()
    env_value = os.environ.get(env_name)
    if env_value:
        return env_value

    # 其次从配置文件获取
    yaml_config = _load_yaml_config()
    config_value = yaml_config.get(key)
    if config_value:
        return str(config_value)

    # 最后返回默认值
    return default


# 服务配置
E2E_SERVER_HOST = "localhost"
E2E_SERVER_PORT = int(
    _get_config_value("server_port", "E2E_SERVER_PORT", str(DEFAULT_SERVER_PORT))
)
E2E_SERVER_URL = f"http://{E2E_SERVER_HOST}:{E2E_SERVER_PORT}"

# 超时配置（毫秒）
SERVER_START_TIMEOUT = int(
    _get_config_value(
        "server_start_timeout",
        "E2E_SERVER_START_TIMEOUT",
        str(DEFAULT_SERVER_START_TIMEOUT),
    )
)
DEFAULT_TIMEOUT = int(
    _get_config_value("default_timeout", default=str(DEFAULT_TIMEOUT))
)
NAVIGATION_TIMEOUT = int(
    _get_config_value("navigation_timeout", default=str(DEFAULT_NAVIGATION_TIMEOUT))
)
API_RESPONSE_TIMEOUT = int(
    _get_config_value("api_response_timeout", default=str(DEFAULT_API_RESPONSE_TIMEOUT))
)


# 测试凭证获取函数
def get_test_token() -> str:
    """
    获取测试Token

    优先级：环境变量 TRMD_TEST_TOKEN > 配置文件 test_token > 空字符串

    Returns:
        测试Token（可能为空，E2E fixture会自动生成）

    Note:
        若返回空字符串，E2E fixture会调用 /api/auth/e2e_token 自动生成。
    """
    return _get_config_value("test_token", "TRMD_TEST_TOKEN", "")


def get_expired_token() -> str:
    """
    获取过期Token（用于测试Token过期场景）

    优先级：环境变量 TRMD_EXPIRED_TOKEN > 配置文件 expired_token > 空字符串

    Returns:
        过期Token（可能为空，对应测试会被skip）
    """
    return _get_config_value("expired_token", "TRMD_EXPIRED_TOKEN", "")


def get_test_token_or_raise() -> str:
    """
    获取测试Token（严格模式）

    优先级：环境变量 TRMD_TEST_TOKEN > 配置文件 test_token > 报错

    Returns:
        测试Token

    Raises:
        ValueError: 未配置Token
    """
    token = get_test_token()
    if not token:
        raise ValueError(
            "请配置测试Token：\n"
            "  方式1：设置环境变量 TRMD_TEST_TOKEN\n"
            "  方式2：在 tests/e2e/fixtures/e2e_test_config.yaml 中填写 test_token\n"
            "  方式3：E2E测试启动后会自动生成（无需手动配置）\n"
            "获取方式：向Telegram Bot发送 /web 命令"
        )
    return token


def get_test_api_id() -> str:
    """
    获取Telegram API ID

    优先级：环境变量 TG_API_ID > 配置文件 api_id > 报错

    Returns:
        API ID

    Raises:
        ValueError: 未配置API ID
    """
    api_id = _get_config_value("api_id", "TG_API_ID")
    if not api_id:
        raise ValueError(
            "请配置Telegram API ID：\n"
            "  方式1：设置环境变量 TG_API_ID\n"
            "  方式2：在 tests/e2e/fixtures/e2e_test_config.yaml 中填写 api_id\n"
            "获取方式：https://my.telegram.org/apps"
        )
    return api_id


def get_test_api_hash() -> str:
    """
    获取Telegram API Hash

    优先级：环境变量 TG_API_HASH > 配置文件 api_hash > 报错

    Returns:
        API Hash

    Raises:
        ValueError: 未配置API Hash
    """
    api_hash = _get_config_value("api_hash", "TG_API_HASH")
    if not api_hash:
        raise ValueError(
            "请配置Telegram API Hash：\n"
            "  方式1：设置环境变量 TG_API_HASH\n"
            "  方式2：在 tests/e2e/fixtures/e2e_test_config.yaml 中填写 api_hash\n"
            "获取方式：https://my.telegram.org/apps"
        )
    return api_hash


def get_test_source_channel() -> str:
    """
    获取测试下载源频道

    优先级：环境变量 E2E_TEST_SOURCE_CHANNEL > 配置文件 test_source_channel

    Returns:
        测试源频道（可能为空）
    """
    return _get_config_value("test_source_channel", "E2E_TEST_SOURCE_CHANNEL")


def get_test_target_channel() -> str:
    """
    获取测试转发/上传目标频道

    优先级：环境变量 E2E_TEST_TARGET_CHANNEL > 配置文件 test_target_channel

    Returns:
        测试目标频道（可能为空）
    """
    return _get_config_value("test_target_channel", "E2E_TEST_TARGET_CHANNEL")


def get_session_directory() -> Path:
    """
    获取Session文件目录

    Returns:
        Session目录路径（默认为项目根目录下的sessions/）
    """
    session_dir = _get_config_value("session_directory", "E2E_SESSION_DIR", "sessions")
    return PROJECT_ROOT / session_dir


def is_run_real_tg_tests() -> bool:
    """
    是否运行真实TG任务测试

    Returns:
        bool
    """
    value = _get_config_value("run_real_tg_tests", "E2E_RUN_REAL_TG_TESTS", "false")
    return value.lower() in ("true", "1", "yes")


def get_browser() -> str:
    """
    获取测试浏览器类型

    Returns:
        浏览器类型（chromium/firefox/webkit）
    """
    return _get_config_value("browser", "E2E_BROWSER", "chromium")


def is_headed() -> bool:
    """
    是否显示浏览器窗口

    Returns:
        bool
    """
    value = _get_config_value("headed", "E2E_HEADED", "false")
    return value.lower() in ("true", "1", "yes")


def get_slowmo() -> int:
    """
    获取操作延迟（毫秒）

    Returns:
        延迟时间
    """
    return int(_get_config_value("slowmo", "E2E_SLOWMO", "0"))


def is_prepare_test_data() -> bool:
    """
    是否自动准备测试数据

    Returns:
        bool
    """
    value = _get_config_value("prepare_test_data", "E2E_PREPARE_TEST_DATA", "false")
    return value.lower() in ("true", "1", "yes")


def get_test_download_count() -> int:
    """
    获取下载测试数据条数

    Returns:
        int
    """
    return int(_get_config_value("test_download_count", "E2E_TEST_DOWNLOAD_COUNT", "5"))


def get_test_message_id_range() -> dict:
    """
    获取下载测试消息ID范围

    Returns:
        dict: {min_id: int, max_id: int} 或空字典
    """
    yaml_config = _load_yaml_config()
    id_range = yaml_config.get("test_message_id_range", {})

    # 环境变量覆盖（格式：min_id,max_id）
    env_range = os.environ.get("E2E_TEST_MESSAGE_ID_RANGE", "")
    if env_range and "," in env_range:
        try:
            min_id, max_id = env_range.split(",")
            return {"min_id": int(min_id.strip()), "max_id": int(max_id.strip())}
        except (ValueError, AttributeError):
            pass

    # 从配置文件读取
    if isinstance(id_range, dict) and "min_id" in id_range and "max_id" in id_range:
        return {
            "min_id": int(id_range["min_id"]),
            "max_id": int(id_range["max_id"]),
        }

    return {}


def get_single_file_timeout() -> int:
    """
    获取单个文件下载超时时间（秒）

    Returns:
        int: 单个文件超时秒数
    """
    return int(_get_config_value("test_single_file_timeout", "E2E_SINGLE_FILE_TIMEOUT", "60"))


def get_base_timeout() -> int:
    """
    获取基础超时时间（秒）

    Returns:
        int: 基础超时秒数
    """
    return int(_get_config_value("test_base_timeout", "E2E_BASE_TIMEOUT", "30"))


def calculate_download_timeout() -> int:
    """
    根据消息ID范围动态计算下载超时时间

    Returns:
        int: 总超时秒数
    """
    base_timeout = get_base_timeout()
    single_file_timeout = get_single_file_timeout()

    # 根据消息ID范围计算文件数量
    id_range = get_test_message_id_range()
    if id_range and "min_id" in id_range and "max_id" in id_range:
        file_count = id_range["max_id"] - id_range["min_id"] + 1
    else:
        # 使用 recent 模式，使用配置的下载条数
        file_count = get_test_download_count()

    # 总超时 = 基础超时 + (单个文件超时 × 文件数量)
    total_timeout = base_timeout + (single_file_timeout * file_count)

    return total_timeout


def get_test_media_types() -> list:
    """
    获取下载媒体类型过滤列表

    Returns:
        list
    """
    yaml_config = _load_yaml_config()
    media_types = yaml_config.get("test_media_types", ["photo"])
    if isinstance(media_types, list):
        return media_types
    return ["photo"]


def is_cleanup_test_data() -> bool:
    """
    是否清理测试数据

    Returns:
        bool
    """
    value = _get_config_value("cleanup_test_data", "E2E_CLEANUP_TEST_DATA", "true")
    return value.lower() in ("true", "1", "yes")


def get_test_download_timeout() -> int:
    """
    获取下载任务等待超时（秒）

    Returns:
        int
    """
    return int(
        _get_config_value("test_download_timeout", "E2E_TEST_DOWNLOAD_TIMEOUT", "120")
    )


def get_pagination_task_count() -> int:
    """
    获取分页测试所需任务数量

    Returns:
        int
    """
    return int(
        _get_config_value("pagination_task_count", "E2E_PAGINATION_TASK_COUNT", "25")
    )


# 导出配置变量（兼容旧代码）
TEST_DOWNLOAD_SOURCE = get_test_source_channel()
TEST_FORWARD_TARGET = get_test_target_channel()
