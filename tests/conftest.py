# coding=UTF-8
"""pytest 全局配置。

module.parser 在导入时执行 parse_args()（解析 sys.argv），
而 pytest 传入的参数会触发 argparse 退出。通过 conftest.py
在测试收集前清空 sys.argv 来避免此问题。
"""

import sys
import tempfile
from pathlib import Path
import pytest

# 确保 module.parser.parse_args() 不会消费 pytest 参数
sys.argv = sys.argv[:1]  # 只保留脚本名


@pytest.fixture
def temp_dir():
    """提供临时目录用于测试文件操作。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_data_dir():
    """提供测试数据目录。"""
    return Path(__file__).parent / "data"


@pytest.fixture
def task_factory():
    """提供任务数据工厂。"""
    from tests.fixtures.data_factories import TaskFactory
    return TaskFactory()


@pytest.fixture
def token_factory():
    """提供 Token 数据工厂。"""
    from tests.fixtures.data_factories import TokenFactory
    return TokenFactory()


@pytest.fixture
def config_factory():
    """提供配置数据工厂。"""
    from tests.fixtures.data_factories import ConfigFactory
    return ConfigFactory()


@pytest.fixture
def file_factory():
    """提供文件准备工具。"""
    from tests.fixtures import prepare_test_files
    return prepare_test_files
