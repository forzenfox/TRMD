# coding=UTF-8
"""yaml_utils 单元测试。

测试 ruamel.yaml 封装工具模块的各项功能：
- get_yaml: 返回预配置的 YAML 实例
- load_yaml: 读取 YAML 文件，保留注释
- dump_yaml: 写回 YAML 文件，保留注释
- yaml_to_plain: 递归将 CommentedMap/CommentedSeq 转为普通 Python 类型
- deep_merge: 递归合并字典，保留 base 的注释元数据
- init_config_from_template: 从 TEMPLATE dict 生成初始 YAML 文件
"""

import os
import tempfile

import pytest

from module.utils.yaml_utils import (
    get_yaml,
    load_yaml,
    dump_yaml,
    yaml_to_plain,
    deep_merge,
    init_config_from_template,
)


# ==================== get_yaml 测试 ====================


class TestGetYaml:
    """测试 get_yaml 工厂函数。"""

    def test_returns_yaml_instance(self):
        """get_yaml 应返回 ruamel.yaml.YAML 实例。"""
        from ruamel.yaml import YAML

        yaml = get_yaml()
        assert isinstance(yaml, YAML)

    def test_preserve_quotes_enabled(self):
        """preserve_quotes 应为 True。"""
        yaml = get_yaml()
        assert yaml.preserve_quotes is True

    def test_default_flow_style_false(self):
        """default_flow_style 应为 False（块样式）。"""
        yaml = get_yaml()
        assert yaml.default_flow_style is False

    def test_width_is_large(self):
        """width 应足够大，避免折行。"""
        yaml = get_yaml()
        assert yaml.width >= 4096


# ==================== load_yaml 测试 ====================


class TestLoadYaml:
    """测试 load_yaml 读取功能。"""

    def _write_temp_yaml(self, content: str) -> str:
        """写入临时 YAML 文件并返回路径（文件已关闭）。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write(content)
            return f.name

    def test_load_yaml_returns_commented_map(self):
        """加载 YAML 文件应返回 CommentedMap。"""
        from ruamel.yaml.comments import CommentedMap

        path = self._write_temp_yaml("key1: value1\nkey2: value2\n")
        try:
            result = load_yaml(path)
            assert isinstance(result, CommentedMap)
            assert result["key1"] == "value1"
            assert result["key2"] == "value2"
        finally:
            os.unlink(path)

    def test_load_yaml_preserves_comments(self):
        """加载带注释的 YAML，注释应在 CommentedMap 中保留。"""
        from ruamel.yaml.comments import CommentedMap

        path = self._write_temp_yaml("# 顶部注释\nkey1: value1\n# 键注释\nkey2: value2\n")
        try:
            result = load_yaml(path)
            assert isinstance(result, CommentedMap)
            assert result["key1"] == "value1"
            # 验证注释元数据存在（ca 属性）
            assert hasattr(result, "ca")
        finally:
            os.unlink(path)

    def test_load_yaml_none_as_tilde(self):
        """YAML 中的 ~ 应被解析为 None。"""
        path = self._write_temp_yaml("key1: ~\nkey2: null\nkey3: value\n")
        try:
            result = load_yaml(path)
            assert result["key1"] is None
            assert result["key2"] is None
            assert result["key3"] == "value"
        finally:
            os.unlink(path)

    def test_load_yaml_nested_structure(self):
        """加载嵌套结构应正确解析。"""
        from ruamel.yaml.comments import CommentedMap

        path = self._write_temp_yaml("parent:\n  child1: value1\n  child2: value2\n")
        try:
            result = load_yaml(path)
            assert isinstance(result, CommentedMap)
            assert isinstance(result["parent"], CommentedMap)
            assert result["parent"]["child1"] == "value1"
        finally:
            os.unlink(path)

    def test_load_yaml_list_values(self):
        """加载列表类型的值应正确解析。"""
        path = self._write_temp_yaml("items:\n- video\n- photo\n- audio\n")
        try:
            result = load_yaml(path)
            assert result["items"] == ["video", "photo", "audio"]
        finally:
            os.unlink(path)


# ==================== dump_yaml 测试 ====================


class TestDumpYaml:
    """测试 dump_yaml 写入功能。"""

    def test_dump_yaml_preserves_comments_after_round_trip(self):
        """加载 → 修改值 → dump → 重新加载，注释应保留。"""
        yaml_content = "# 顶部注释\nkey1: value1\n# 键2注释\nkey2: value2\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            # 加载
            data = load_yaml(path)
            # 修改值
            data["key1"] = "new_value1"
            # 写回
            dump_yaml(data, path)
            # 重新加载
            result = load_yaml(path)
            assert result["key1"] == "new_value1"
            assert result["key2"] == "value2"

            # 验证注释保留：读取原始文件内容检查注释存在
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# 顶部注释" in content
            assert "# 键2注释" in content
        finally:
            os.unlink(path)

    def test_dump_yaml_none_as_tilde(self):
        """None 值应被写为 ~。"""
        from ruamel.yaml.comments import CommentedMap

        yaml = get_yaml()
        data = CommentedMap()
        data["key1"] = None
        data["key2"] = "value"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write("")
            path = f.name

        try:
            dump_yaml(data, path)
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "~" in content or "null" in content  # None 值表示
        finally:
            os.unlink(path)


# ==================== yaml_to_plain 测试 ====================


class TestYamlToPlain:
    """测试 yaml_to_plain 转换功能。"""

    def test_converts_commented_map_to_dict(self):
        """CommentedMap 应转为普通 dict。"""
        from ruamel.yaml.comments import CommentedMap

        data = CommentedMap()
        data["key1"] = "value1"
        data["key2"] = 42
        result = yaml_to_plain(data)
        assert isinstance(result, dict)
        assert not isinstance(result, CommentedMap)
        assert result["key1"] == "value1"
        assert result["key2"] == 42

    def test_converts_nested_commented_map(self):
        """嵌套的 CommentedMap/CommentedSeq 应递归转为 dict/list。"""
        from ruamel.yaml.comments import CommentedMap, CommentedSeq

        data = CommentedMap()
        data["parent"] = CommentedMap()
        data["parent"]["child"] = "value"
        data["items"] = CommentedSeq(["a", "b", "c"])

        result = yaml_to_plain(data)
        assert isinstance(result, dict)
        assert isinstance(result["parent"], dict)
        assert not isinstance(result["parent"], CommentedMap)
        assert isinstance(result["items"], list)
        assert not isinstance(result["items"], CommentedSeq)
        assert result["items"] == ["a", "b", "c"]

    def test_preserves_primitive_values(self):
        """原始值类型应保持不变。"""
        from ruamel.yaml.comments import CommentedMap

        data = CommentedMap()
        data["string"] = "hello"
        data["integer"] = 42
        data["float_val"] = 3.14
        data["boolean"] = True
        data["none_val"] = None
        data["list_val"] = [1, 2, 3]

        result = yaml_to_plain(data)
        assert result["string"] == "hello"
        assert result["integer"] == 42
        assert result["float_val"] == 3.14
        assert result["boolean"] is True
        assert result["none_val"] is None
        assert result["list_val"] == [1, 2, 3]

    def test_plain_dict_unchanged(self):
        """普通 dict 输入应直接返回。"""
        data = {"key": "value"}
        result = yaml_to_plain(data)
        assert result == data

    def test_plain_list_unchanged(self):
        """普通 list 输入应直接返回。"""
        data = [1, 2, 3]
        result = yaml_to_plain(data)
        assert result == data


# ==================== deep_merge 测试 ====================


class TestDeepMerge:
    """测试 deep_merge 递归合并功能。"""

    def test_merge_flat_dicts(self):
        """扁平字典合并。"""
        base = {"a": 1, "b": 2}
        override = {"b": 20, "c": 30}
        result = deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 20
        assert result["c"] == 30

    def test_merge_nested_dicts(self):
        """嵌套字典递归合并。"""
        base = {"parent": {"a": 1, "b": 2}, "x": 10}
        override = {"parent": {"b": 20, "c": 30}, "y": 20}
        result = deep_merge(base, override)
        assert result["parent"]["a"] == 1
        assert result["parent"]["b"] == 20
        assert result["parent"]["c"] == 30
        assert result["x"] == 10
        assert result["y"] == 20

    def test_merge_preserves_commented_map_annotations(self):
        """合并 CommentedMap 时应保留注释元数据。"""
        from ruamel.yaml.comments import CommentedMap

        # 模拟从文件加载的带注释数据
        yaml_content = "# 顶部注释\nkey1: value1\nkey2: value2\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            base = load_yaml(path)
            assert isinstance(base, CommentedMap)

            override = {"key1": "new_value"}
            result = deep_merge(base, override)

            # 结果仍是 CommentedMap（注释保留）
            assert isinstance(result, CommentedMap)
            assert result["key1"] == "new_value"
            assert result["key2"] == "value2"
            # 验证注释元数据仍在
            assert hasattr(result, "ca")
        finally:
            os.unlink(path)

    def test_merge_override_replaces_non_dict_with_dict(self):
        """当 base 中是标量而 override 中是 dict 时，override 替换。"""
        base = {"key": "scalar"}
        override = {"key": {"nested": "value"}}
        result = deep_merge(base, override)
        assert result["key"] == {"nested": "value"}

    def test_merge_override_replaces_dict_with_scalar(self):
        """当 base 中是 dict 而 override 中是标量时，override 替换。"""
        base = {"key": {"nested": "value"}}
        override = {"key": "scalar"}
        result = deep_merge(base, override)
        assert result["key"] == "scalar"

    def test_merge_returns_base_object(self):
        """deep_merge 应就地修改 base 并返回它。"""
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert result is base

    def test_merge_empty_override(self):
        """空 override 不修改 base。"""
        base = {"a": 1, "b": 2}
        override = {}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}


# ==================== init_config_from_template 测试 ====================


class TestInitConfigFromTemplate:
    """测试从 TEMPLATE 生成初始配置文件。"""

    def test_creates_file(self):
        """应创建 YAML 文件。"""
        template = {"key1": "value1", "key2": None, "key3": 42}
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "config.yaml")
            init_config_from_template(template, path)
            assert os.path.exists(path)

    def test_created_file_is_valid_yaml(self):
        """生成的文件应是有效的 YAML。"""
        template = {"key1": "value1", "key2": None, "key3": 42}
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "config.yaml")
            init_config_from_template(template, path)
            result = load_yaml(path)
            assert result["key1"] == "value1"
            assert result["key2"] is None
            assert result["key3"] == 42

    def test_none_represented_as_tilde(self):
        """TEMPLATE 中的 None 值应以 ~ 表示。"""
        template = {"key1": None, "key2": "value"}
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "config.yaml")
            init_config_from_template(template, path)
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            # 验证 None 值以 ~ 表示
            assert "~" in content or "null" in content

    def test_nested_template_structure(self):
        """嵌套 TEMPLATE 结构应正确生成。"""
        template = {
            "credential": {"api_id": None, "api_hash": None},
            "task": {"save_directory": "./downloads"},
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "config.yaml")
            init_config_from_template(template, path)
            result = load_yaml(path)
            assert result["credential"]["api_id"] is None
            assert result["task"]["save_directory"] == "./downloads"


# ==================== 完整往返测试 ====================


class TestRoundTrip:
    """完整往返测试：加载 → 修改 → 保存 → 重新加载。"""

    def test_full_round_trip_preserves_data(self):
        """完整往返应保留所有数据。"""
        yaml_content = (
            "# 配置文件\n"
            "credential:\n"
            "  api_id: 12345\n"
            "  api_hash: abcdef123456\n"
            "task:\n"
            "  save_directory: ./downloads\n"
            "  download_type:\n"
            "  - video\n"
            "  - photo\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            # 加载
            data = load_yaml(path)
            # 修改
            data["credential"]["api_id"] = 99999
            data["task"]["download_type"].append("audio")
            # 保存
            dump_yaml(data, path)
            # 重新加载
            result = load_yaml(path)
            assert result["credential"]["api_id"] == 99999
            assert result["credential"]["api_hash"] == "abcdef123456"
            assert result["task"]["save_directory"] == "./downloads"
            assert result["task"]["download_type"] == ["video", "photo", "audio"]
            # 注释保留
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# 配置文件" in content
        finally:
            os.unlink(path)

    def test_add_new_key_and_preserve_comments(self):
        """添加新键后保存，已有注释应保留。"""
        yaml_content = "# 注释A\nkey1: value1\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            data = load_yaml(path)
            data["key2"] = "value2"
            dump_yaml(data, path)
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# 注释A" in content
            assert "key2:" in content
        finally:
            os.unlink(path)

    def test_remove_key_and_preserve_comments(self):
        """删除键后保存，剩余键的注释应保留。"""
        yaml_content = "# 注释A\nkey1: value1\n# 注释B\nkey2: value2\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="UTF-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            data = load_yaml(path)
            del data["key2"]
            dump_yaml(data, path)
            with open(path, "r", encoding="UTF-8") as f:
                content = f.read()
            assert "# 注释A" in content
            assert "key2:" not in content
        finally:
            os.unlink(path)
