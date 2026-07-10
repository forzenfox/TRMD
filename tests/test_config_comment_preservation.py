# coding=UTF-8
"""配置注释保留集成测试。

验证 UserConfig 和 ConfigManager 在加载、修改、保存配置时，
config.yaml 中的注释不被丢失。

TDD 红灯阶段：这些测试在 legacy_config.py 改造前会失败。
"""

import os
import tempfile

import pytest

from module.yaml_utils import load_yaml, dump_yaml, deep_merge


# ==================== 辅助工具 ====================

SAMPLE_CONFIG_WITH_COMMENTS = """\
# TRMD 配置文件
# Telegram 资源管理与下载工具

# ======================== 凭证配置 ========================
credential:
  api_hash: test_hash   # Telegram API Hash
  api_id: 12345         # Telegram API ID
  bot_token: ~          # Bot Token

# ======================== 数据目录 ========================
data_directory: ./.trmd

# ======================== 下载类型（全局） ========================
# 允许下载的媒体类型列表
download_type:
- video          # 视频
- photo          # 图片

# ======================== 日志配置 ========================
log:
  console_log_level: INFO    # 控制台日志级别
  file_log_level: DEBUG      # 文件日志级别

# ======================== 偏好设置 ========================
preference:
  export_table:
    count: false    # 是否包含计数列
    link: false     # 是否包含链接列
    upload: false   # 是否包含上传状态列
  forward_type:
    animation: true     # GIF 动图
    audio: true         # 音频
    document: true      # 文档/文件
    photo: true         # 图片
    text: true          # 纯文本消息
    video: true         # 视频
    video_note: true    # 视频消息
    voice: true         # 语音消息
  is_shutdown: false    # 关机标志
  notice: true          # 是否启用通知
  upload:
    delete: false          # 上传完成后是否删除本地文件
    download_upload: true  # 是否自动上传到仓库频道

# ======================== 代理配置 ========================
proxy:
  enable_proxy: false   # 是否启用代理
  hostname: 127.0.0.1   # 代理地址
  password: ~           # 代理密码
  port: 7890            # 代理端口
  scheme: socks5        # 代理协议
  username: ~           # 代理用户名

# ======================== 仓库配置 ========================
repository:
  enabled: true                    # 是否启用仓库
  chat_id: '-1001234567890'        # 仓库频道 ID
  auto_sync_enabled: false         # 是否自动同步
  auto_sync_interval_minutes: 60   # 自动同步间隔

# ======================== 任务配置 ========================
task:
  download_type: ~     # 任务级下载类型覆盖
  is_shutdown: false   # 任务系统关机标志
  max_retries:
    download: 3    # 下载最大重试次数
    upload: 3      # 上传最大重试次数
  max_tasks:
    download: 4    # 下载最大并发数
    upload: 4      # 上传最大并发数
  save_directory: ./downloads       # 下载保存目录
  session_directory: ./sessions     # 会话存储目录
  temp_directory: ./temp            # 临时文件目录
"""


def _write_sample_config(tmp_dir: str) -> str:
    """在临时目录中写入带注释的示例配置文件。"""
    path = os.path.join(tmp_dir, "config.yaml")
    with open(path, "w", encoding="UTF-8") as f:
        f.write(SAMPLE_CONFIG_WITH_COMMENTS)
    return path


# ==================== 注释保留测试 ====================


class TestConfigCommentPreservation:
    """验证配置加载、修改、保存后注释保留。"""

    def test_load_and_save_preserves_comments(self):
        """加载带注释的配置文件后直接保存，注释应保留。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_sample_config(tmp_dir)

            # 加载
            data = load_yaml(path)
            # 直接保存（不修改）
            dump_yaml(data, path)

            # 验证注释保留
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# TRMD 配置文件" in content
            assert "# ======================== 凭证配置" in content
            assert "# Telegram API Hash" in content
            assert "# 允许下载的媒体类型列表" in content
            assert "# 下载最大重试次数" in content

    def test_modify_value_and_save_preserves_comments(self):
        """修改配置值后保存，注释应保留。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_sample_config(tmp_dir)

            # 加载并修改
            data = load_yaml(path)
            data["credential"]["api_id"] = 99999
            data["task"]["max_tasks"]["download"] = 8
            data["proxy"]["enable_proxy"] = True
            dump_yaml(data, path)

            # 验证值已更新
            result = load_yaml(path)
            assert result["credential"]["api_id"] == 99999
            assert result["task"]["max_tasks"]["download"] == 8
            assert result["proxy"]["enable_proxy"] is True

            # 验证注释保留
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# Telegram API Hash" in content
            assert "# 下载最大并发数" in content
            assert "# 是否启用代理" in content

    def test_add_missing_key_and_save_preserves_comments(self):
        """添加缺失的键后保存，已有注释应保留。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_sample_config(tmp_dir)

            data = load_yaml(path)
            # 添加新键（模拟 __check_params 的 add_missing_keys）
            data["new_key"] = "new_value"
            dump_yaml(data, path)

            # 已有注释应保留
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# TRMD 配置文件" in content
            assert "# Telegram API Hash" in content

    def test_remove_extra_key_and_save_preserves_comments(self):
        """删除多余的键后保存，已有注释应保留。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_sample_config(tmp_dir)

            data = load_yaml(path)
            # 删除一个键（模拟 __check_params 的 remove_extra_keys）
            del data["proxy"]
            dump_yaml(data, path)

            # 其他注释应保留
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# TRMD 配置文件" in content
            assert "# Telegram API Hash" in content
            assert "proxy:" not in content

    def test_deep_merge_then_save_preserves_comments(self):
        """deep_merge 合并后保存，注释应保留。

        模拟 ConfigManager.save_config 的合并场景。
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_sample_config(tmp_dir)

            # 加载原始带注释的数据
            base = load_yaml(path)

            # 模拟 API 更新：构造 override dict
            override = {
                "proxy": {
                    "enable_proxy": True,
                    "hostname": "192.168.1.1",
                    "port": 1080,
                }
            }

            # deep_merge 合并
            merged = deep_merge(base, override)

            # 保存
            dump_yaml(merged, path)

            # 验证值已更新
            result = load_yaml(path)
            assert result["proxy"]["enable_proxy"] is True
            assert result["proxy"]["hostname"] == "192.168.1.1"
            assert result["proxy"]["port"] == 1080

            # 验证注释保留
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# TRMD 配置文件" in content
            assert "# Telegram API Hash" in content

    def test_multiple_round_trips_preserve_comments(self):
        """多次加载-修改-保存循环后注释应保留。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_sample_config(tmp_dir)

            for i in range(3):
                data = load_yaml(path)
                data["task"]["max_tasks"]["download"] = 4 + i
                dump_yaml(data, path)

            # 最终验证
            result = load_yaml(path)
            assert result["task"]["max_tasks"]["download"] == 6

            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# TRMD 配置文件" in content
            assert "# 下载最大并发数" in content

    def test_config_example_yaml_no_sensitive_values(self):
        """config.example.yaml 不应包含真实凭证值。"""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.example.yaml",
        )
        if not os.path.exists(example_path):
            pytest.skip("config.example.yaml 尚未创建")

        with open(example_path, "r", encoding="UTF-8") as f:
            content = f.read()

        # 不应包含看起来像真实凭证的值
        data = load_yaml(example_path)
        credential = data.get("credential", {})
        # api_id 不应是纯数字（应该是占位符）
        api_id = credential.get("api_id")
        if api_id is not None:
            assert not (isinstance(api_id, int) and api_id > 10000), \
                "config.example.yaml 不应包含真实的 api_id"
