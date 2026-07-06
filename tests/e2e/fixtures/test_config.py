"""
E2E测试配置

定义测试凭证、测试频道、超时配置等。
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 服务配置
E2E_SERVER_HOST = "localhost"
E2E_SERVER_PORT = 8800
E2E_SERVER_URL = f"http://{E2E_SERVER_HOST}:{E2E_SERVER_PORT}"

# 超时配置（毫秒）
DEFAULT_TIMEOUT = 10000
NAVIGATION_TIMEOUT = 15000
API_RESPONSE_TIMEOUT = 15000
SERVER_START_TIMEOUT = 30  # 秒

# 测试凭证（从环境变量读取）
def get_test_token() -> str:
    """获取测试Token"""
    token = os.environ.get("TRMD_TEST_TOKEN")
    if not token:
        raise ValueError("请设置环境变量 TRMD_TEST_TOKEN")
    return token

def get_test_api_id() -> str:
    """获取Telegram API ID"""
    api_id = os.environ.get("TG_API_ID")
    if not api_id:
        raise ValueError("请设置环境变量 TG_API_ID")
    return api_id

def get_test_api_hash() -> str:
    """获取Telegram API Hash"""
    api_hash = os.environ.get("TG_API_HASH")
    if not api_hash:
        raise ValueError("请设置环境变量 TG_API_HASH")
    return api_hash

# 测试频道配置
TEST_DOWNLOAD_SOURCE = os.environ.get("E2E_TEST_SOURCE_CHANNEL", "")
TEST_FORWARD_TARGET = os.environ.get("E2E_TEST_TARGET_CHANNEL", "")