# coding=UTF-8
"""配置合并迁移测试。

验证 UserConfig/GlobalConfig 双配置合并为单一 config.yaml 的正确性：
- 合并后的 TEMPLATE 包含所有旧键
- 配置可从单文件加载
- 旧 global_config.yaml 的键可从合并配置访问
- Repository 配置方法工作正常
"""

import copy
import logging
import os
import tempfile

import yaml

from module.config import UserConfig, GlobalConfig


# ==================== TEMPLATE 合并完整性测试 ====================

class TestMergedTemplateCompleteness:
    """验证合并后的 UserConfig.TEMPLATE 包含所有旧键。"""

    # 旧 UserConfig.TEMPLATE 的所有顶层键（合并前）
    OLD_USER_CONFIG_TOP_KEYS = {
        'api_id', 'api_hash', 'bot_token', 'session_directory',
        'links', 'save_directory', 'temp_directory',
        'is_shutdown', 'download_type',
    }

    # 旧 UserConfig.TEMPLATE 的嵌套键
    OLD_USER_CONFIG_NESTED = {
        'proxy': {'enable_proxy', 'scheme', 'hostname', 'port', 'username', 'password'},
        'max_tasks': {'download', 'upload'},
        'max_retries': {'download', 'upload'},
    }

    # 旧 GlobalConfig.TEMPLATE 的所有顶层键
    OLD_GLOBAL_CONFIG_TOP_KEYS = {
        'notice', 'file_log_level', 'console_log_level',
    }

    # 旧 GlobalConfig.TEMPLATE 的嵌套键
    OLD_GLOBAL_CONFIG_NESTED = {
        'export_table': {'link', 'count', 'upload'},
        'upload': {'download_upload', 'delete'},
        'forward_type': {
            'video', 'photo', 'audio', 'document',
            'voice', 'text', 'animation', 'video_note',
        },
    }

    def _collect_all_keys(self, template: dict, prefix: str = '') -> set:
        """递归收集模板中所有键的扁平路径集合。"""
        keys = set()
        for key, value in template.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)
            if isinstance(value, dict):
                keys.update(self._collect_all_keys(value, full_key))
        return keys

    def test_merged_template_has_credential_section(self):
        """合并 TEMPLATE 应包含 credential 分组。"""
        assert 'credential' in UserConfig.TEMPLATE

    def test_merged_template_has_proxy_section(self):
        """合并 TEMPLATE 应包含 proxy 分组。"""
        assert 'proxy' in UserConfig.TEMPLATE

    def test_merged_template_has_task_section(self):
        """合并 TEMPLATE 应包含 task 分组。"""
        assert 'task' in UserConfig.TEMPLATE

    def test_merged_template_has_preference_section(self):
        """合并 TEMPLATE 应包含 preference 分组。"""
        assert 'preference' in UserConfig.TEMPLATE

    def test_merged_template_has_log_section(self):
        """合并 TEMPLATE 应包含 log 分组。"""
        assert 'log' in UserConfig.TEMPLATE

    def test_merged_template_has_repository_section(self):
        """合并 TEMPLATE 应包含 repository 分组。"""
        assert 'repository' in UserConfig.TEMPLATE

    def test_credential_section_contains_old_user_keys(self):
        """credential 分组应包含 api_id, api_hash, bot_token。"""
        credential = UserConfig.TEMPLATE.get('credential', {})
        assert 'api_id' in credential
        assert 'api_hash' in credential
        assert 'bot_token' in credential

    def test_proxy_section_preserved(self):
        """proxy 分组应保留原有所有键。"""
        proxy = UserConfig.TEMPLATE.get('proxy', {})
        expected_keys = self.OLD_USER_CONFIG_NESTED['proxy']
        assert expected_keys == set(proxy.keys())

    def test_task_section_contains_old_user_task_keys(self):
        """task 分组应包含 links, save_directory, temp_directory, download_type, is_shutdown, max_tasks, max_retries。"""
        task = UserConfig.TEMPLATE.get('task', {})
        assert 'links' in task
        assert 'save_directory' in task
        assert 'temp_directory' in task
        assert 'download_type' in task
        assert 'is_shutdown' in task
        assert 'max_tasks' in task
        assert 'max_retries' in task

    def test_task_max_tasks_has_download_and_upload(self):
        """task.max_tasks 应包含 download 和 upload。"""
        max_tasks = UserConfig.TEMPLATE.get('task', {}).get('max_tasks', {})
        assert 'download' in max_tasks
        assert 'upload' in max_tasks

    def test_task_max_retries_has_download_and_upload(self):
        """task.max_retries 应包含 download 和 upload。"""
        max_retries = UserConfig.TEMPLATE.get('task', {}).get('max_retries', {})
        assert 'download' in max_retries
        assert 'upload' in max_retries

    def test_preference_section_contains_notice(self):
        """preference 分组应包含 notice。"""
        preference = UserConfig.TEMPLATE.get('preference', {})
        assert 'notice' in preference

    def test_preference_section_contains_is_shutdown(self):
        """preference 分组应包含 is_shutdown。"""
        preference = UserConfig.TEMPLATE.get('preference', {})
        assert 'is_shutdown' in preference

    def test_preference_section_contains_forward_type(self):
        """preference 分组应包含 forward_type。"""
        preference = UserConfig.TEMPLATE.get('preference', {})
        assert 'forward_type' in preference
        forward_type = preference.get('forward_type', {})
        expected_keys = self.OLD_GLOBAL_CONFIG_NESTED['forward_type']
        assert expected_keys == set(forward_type.keys())

    def test_preference_section_contains_upload(self):
        """preference 分组应包含 upload。"""
        preference = UserConfig.TEMPLATE.get('preference', {})
        assert 'upload' in preference
        upload = preference.get('upload', {})
        expected_keys = self.OLD_GLOBAL_CONFIG_NESTED['upload']
        assert expected_keys == set(upload.keys())

    def test_preference_section_contains_export_table(self):
        """preference 分组应包含 export_table。"""
        preference = UserConfig.TEMPLATE.get('preference', {})
        assert 'export_table' in preference
        export_table = preference.get('export_table', {})
        expected_keys = self.OLD_GLOBAL_CONFIG_NESTED['export_table']
        assert expected_keys == set(export_table.keys())

    def test_log_section_contains_file_and_console_levels(self):
        """log 分组应包含 file_log_level 和 console_log_level。"""
        log_section = UserConfig.TEMPLATE.get('log', {})
        assert 'file_log_level' in log_section
        assert 'console_log_level' in log_section

    def test_log_section_default_values(self):
        """log 分组默认值应为 INFO 和 WARNING。"""
        log_section = UserConfig.TEMPLATE.get('log', {})
        assert log_section.get('file_log_level') == logging.getLevelName(logging.INFO)
        assert log_section.get('console_log_level') == logging.getLevelName(logging.WARNING)

    def test_repository_section_has_required_keys(self):
        """repository 分组应包含 enabled, chat_id, auto_sync_enabled, auto_sync_interval_minutes。"""
        repo = UserConfig.TEMPLATE.get('repository', {})
        assert 'enabled' in repo
        assert 'chat_id' in repo
        assert 'auto_sync_enabled' in repo
        assert 'auto_sync_interval_minutes' in repo

    def test_repository_section_default_values(self):
        """repository 分组默认值应正确。"""
        repo = UserConfig.TEMPLATE.get('repository', {})
        assert repo.get('enabled') is True
        assert repo.get('chat_id') == ''
        assert repo.get('auto_sync_enabled') is False
        assert repo.get('auto_sync_interval_minutes') == 60

    def test_all_old_user_config_keys_accounted_for(self):
        """所有旧 UserConfig 顶层键应在合并 TEMPLATE 中找到对应位置。"""
        merged_keys = self._collect_all_keys(UserConfig.TEMPLATE)
        for key in self.OLD_USER_CONFIG_TOP_KEYS:
            # 检查键是否存在于某个分组下
            found = any(k.endswith(f'.{key}') or k == key for k in merged_keys)
            assert found, f"旧 UserConfig 键 '{key}' 在合并 TEMPLATE 中未找到"

    def test_all_old_global_config_keys_accounted_for(self):
        """所有旧 GlobalConfig 顶层键应在合并 TEMPLATE 中找到对应位置。"""
        merged_keys = self._collect_all_keys(UserConfig.TEMPLATE)
        for key in self.OLD_GLOBAL_CONFIG_TOP_KEYS:
            found = any(k.endswith(f'.{key}') or k == key for k in merged_keys)
            assert found, f"旧 GlobalConfig 键 '{key}' 在合并 TEMPLATE 中未找到"


# ==================== 单文件配置加载测试 ====================

class TestSingleFileConfigLoad:
    """验证配置可从单文件加载。"""

    def _write_yaml(self, tmp_dir: str, filename: str, data: dict) -> str:
        """写入 YAML 文件并返回路径。"""
        path = os.path.join(tmp_dir, filename)
        with open(path, 'w', encoding='UTF-8') as f:
            yaml.dump(data, f)
        return path

    def test_load_merged_config_from_single_file(self):
        """应能从单个 YAML 文件加载包含所有分组的配置。"""
        merged_config = copy.deepcopy(UserConfig.TEMPLATE)
        # 填入一些非 None 值
        merged_config['credential']['api_id'] = '12345'
        merged_config['credential']['api_hash'] = 'abc123def456abc123def456abc123de'
        merged_config['credential']['bot_token'] = '123456:ABC-DEF'
        merged_config['task']['save_directory'] = '/tmp/downloads'
        merged_config['task']['download_type'] = ['video', 'photo']
        merged_config['preference']['notice'] = True
        merged_config['log']['file_log_level'] = 'DEBUG'

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = self._write_yaml(tmp_dir, 'config.yaml', merged_config)
            with open(config_path, 'r', encoding='UTF-8') as f:
                loaded = yaml.safe_load(f)
            assert loaded['credential']['api_id'] == '12345'
            assert loaded['preference']['notice'] is True
            assert loaded['log']['file_log_level'] == 'DEBUG'

    def test_old_global_config_keys_accessible_from_merged(self):
        """旧 global_config.yaml 的键应可从合并配置中访问。"""
        # 模拟旧 global_config.yaml 的数据
        old_global_data = copy.deepcopy(GlobalConfig.TEMPLATE)
        old_global_data['notice'] = False
        old_global_data['file_log_level'] = 'DEBUG'
        old_global_data['forward_type']['video'] = False

        # 在合并配置中，这些键应在 preference/log 分组下
        merged_config = copy.deepcopy(UserConfig.TEMPLATE)
        # notice -> preference.notice
        assert 'notice' in merged_config.get('preference', {})
        # file_log_level -> log.file_log_level
        assert 'file_log_level' in merged_config.get('log', {})
        # forward_type -> preference.forward_type
        assert 'forward_type' in merged_config.get('preference', {})

    def test_session_directory_in_task_section(self):
        """session_directory 应在 task 分组中保留。"""
        task = UserConfig.TEMPLATE.get('task', {})
        assert 'session_directory' in task


# ==================== ConfigManager Repository 方法测试 ====================

class TestConfigManagerRepositoryMethods:
    """验证 ConfigManager 的 repository 配置方法。"""

    def test_get_repository_config(self):
        """get_repository_config 应返回 repository 分组字典。"""
        from module.core.config_manager import ConfigManager

        # 创建 mock user_config
        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': True,
                    'chat_id': '-1001234567890',
                    'auto_sync_enabled': False,
                    'auto_sync_interval_minutes': 60,
                }
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        repo_config = cm.get_repository_config()
        assert isinstance(repo_config, dict)
        assert repo_config.get('enabled') is True
        assert repo_config.get('chat_id') == '-1001234567890'

    def test_get_repository_config_returns_empty_when_missing(self):
        """当配置中无 repository 分组时，应返回空字典。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {},
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        repo_config = cm.get_repository_config()
        assert isinstance(repo_config, dict)

    def test_set_repository_chat_id(self):
        """set_repository_chat_id 应设置 repository.chat_id 并保存。"""
        from module.core.config_manager import ConfigManager

        saved_configs = []

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': True,
                    'chat_id': '',
                    'auto_sync_enabled': False,
                    'auto_sync_interval_minutes': 60,
                }
            },
            'save_config': lambda self, c: saved_configs.append(c),
        })()

        cm = ConfigManager(user_config=mock_user_config)
        result = cm.set_repository_chat_id('-1001234567890')
        assert result is True
        assert len(saved_configs) == 1
        assert saved_configs[0]['repository']['chat_id'] == '-1001234567890'

    def test_set_repository_chat_id_creates_repository_if_missing(self):
        """当 repository 分组不存在时，set_repository_chat_id 应创建它。"""
        from module.core.config_manager import ConfigManager

        saved_configs = []

        mock_user_config = type('MockUserConfig', (), {
            'config': {},
            'save_config': lambda self, c: saved_configs.append(c),
        })()

        cm = ConfigManager(user_config=mock_user_config)
        result = cm.set_repository_chat_id('-1009876543210')
        assert result is True
        assert saved_configs[0]['repository']['chat_id'] == '-1009876543210'

    def test_validate_repository_config_valid(self):
        """validate_repository_config 对有效配置应返回 (True, '')。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': True,
                    'chat_id': '-1001234567890',
                    'auto_sync_enabled': False,
                    'auto_sync_interval_minutes': 60,
                }
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        is_valid, msg = cm.validate_repository_config()
        assert is_valid is True
        assert msg == ''

    def test_validate_repository_config_empty_chat_id(self):
        """validate_repository_config 对空 chat_id 应返回验证失败。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': True,
                    'chat_id': '',
                    'auto_sync_enabled': False,
                    'auto_sync_interval_minutes': 60,
                }
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        is_valid, msg = cm.validate_repository_config()
        assert is_valid is False
        assert 'chat_id' in msg.lower()

    def test_validate_repository_config_invalid_chat_id_format(self):
        """validate_repository_config 对无效 chat_id 格式应返回验证失败。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': True,
                    'chat_id': 'not_a_valid_chat_id',
                    'auto_sync_enabled': False,
                    'auto_sync_interval_minutes': 60,
                }
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        is_valid, msg = cm.validate_repository_config()
        assert is_valid is False

    def test_validate_repository_config_disabled_is_valid(self):
        """repository 未启用时，即使 chat_id 为空也应验证通过。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': False,
                    'chat_id': '',
                    'auto_sync_enabled': False,
                    'auto_sync_interval_minutes': 60,
                }
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        is_valid, msg = cm.validate_repository_config()
        assert is_valid is True

    def test_validate_repository_config_invalid_interval(self):
        """validate_repository_config 对无效的 auto_sync_interval_minutes 应返回验证失败。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'repository': {
                    'enabled': True,
                    'chat_id': '-1001234567890',
                    'auto_sync_enabled': True,
                    'auto_sync_interval_minutes': -1,
                }
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        is_valid, msg = cm.validate_repository_config()
        assert is_valid is False


# ==================== ConfigManager 移除 _global_config 测试 ====================

class TestConfigManagerNoGlobalConfig:
    """验证 ConfigManager 不再依赖 _global_config。"""

    def test_config_manager_init_without_global_config(self):
        """ConfigManager 不传 global_config 参数应正常工作。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {'api_id': '123'},
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        assert cm._user_config is not None

    def test_config_manager_load_config_without_global(self):
        """load_config 不依赖 _global_config。"""
        from module.core.config_manager import ConfigManager

        mock_user_config = type('MockUserConfig', (), {
            'config': {
                'credential': {'api_id': '123', 'api_hash': 'abc', 'bot_token': None},
                'preference': {'notice': True},
                'log': {'file_log_level': 'INFO', 'console_log_level': 'WARNING'},
            },
            'save_config': lambda self, c: None,
        })()

        cm = ConfigManager(user_config=mock_user_config)
        config = cm.load_config(mask_sensitive=False)
        assert config.get('preference', {}).get('notice') is True
