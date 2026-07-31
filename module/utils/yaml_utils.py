# coding=UTF-8
"""YAML 工具模块。

封装 ruamel.yaml，提供项目统一的 YAML 读写接口。
支持注释和格式的往返保留（round-trip），替代 PyYAML 的 yaml.safe_load/yaml.dump。

核心功能：
- get_yaml: 返回预配置的 ruamel.yaml.YAML 实例
- load_yaml: 读取 YAML 文件，保留注释和格式
- dump_yaml: 写回 YAML 文件，保留注释和格式
- yaml_to_plain: 递归将 CommentedMap/CommentedSeq 转为普通 Python 类型
- deep_merge: 递归合并字典，保留 base 的注释元数据
- init_config_from_template: 从 TEMPLATE dict 生成初始 YAML 文件
"""

import logging
from typing import Any, Optional, Union

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

log = logging.getLogger(__name__)


def get_yaml() -> YAML:
    """返回预配置的 ruamel.yaml.YAML 实例。

    配置：
    - preserve_quotes=True: 保留引号风格
    - default_flow_style=False: 块样式输出
    - width=4096: 避免长行折行
    - None 值表示为 ~

    Returns:
        预配置的 YAML 实例
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 4096
    # 配置 None 值表示为 ~（与原 CustomDumper 行为一致）
    yaml.Representer.add_representer(type(None), _represent_none)
    return yaml


def _represent_none(representer, data):
    """将 None 表示为 ~。"""
    return representer.represent_scalar("tag:yaml.org,2002:null", "~")


def load_yaml(filepath: str) -> Optional[CommentedMap]:
    """读取 YAML 文件，保留注释和格式信息。

    Args:
        filepath: YAML 文件路径

    Returns:
        CommentedMap（dict 子类），包含注释元数据；
        如果文件为空则返回 None
    """
    yaml = get_yaml()
    with open(filepath, "r", encoding="UTF-8") as f:
        data = yaml.load(f)
    return data


def dump_yaml(data: Union[CommentedMap, dict], filepath: str) -> None:
    """将数据写回 YAML 文件，保留注释和格式。

    如果 data 是 CommentedMap（从 load_yaml 加载），注释会被保留。
    如果 data 是普通 dict，则写入无注释的 YAML。

    Args:
        data: 要写入的数据（CommentedMap 或普通 dict）
        filepath: 目标文件路径
    """
    yaml = get_yaml()
    with open(filepath, "w", encoding="UTF-8") as f:
        yaml.dump(data, f)


def yaml_to_plain(data: Any) -> Any:
    """递归将 CommentedMap/CommentedSeq 转为普通 Python 类型。

    用于需要纯 Python 类型的场景（如 JSON 序列化、dict 对比等）。

    Args:
        data: 输入数据，可以是 CommentedMap、CommentedSeq 或普通类型

    Returns:
        转换后的普通 Python 类型（dict、list 或原始值）
    """
    if isinstance(data, CommentedMap):
        return {key: yaml_to_plain(value) for key, value in data.items()}
    elif isinstance(data, CommentedSeq):
        return [yaml_to_plain(item) for item in data]
    elif isinstance(data, dict):
        return {key: yaml_to_plain(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [yaml_to_plain(item) for item in data]
    else:
        return data


def deep_merge(base: dict, override: dict) -> dict:
    """递归合并 override 到 base，保留 base 的注释元数据。

    当 base 是 CommentedMap 时，合并操作就地修改 base，
    注释元数据得以保留。返回 base 本身。

    合并规则：
    - override 中存在而 base 中不存在的键：添加
    - override 中存在且 base 中也存在的键：
      - 如果两者都是 dict：递归合并
      - 否则：override 的值替换 base 的值

    Args:
        base: 基础字典（通常是 CommentedMap，包含注释）
        override: 要合并的字典

    Returns:
        合并后的 base（就地修改并返回）
    """
    for key, value in override.items():
        if key in base:
            base_val = base[key]
            if isinstance(base_val, dict) and isinstance(value, dict):
                deep_merge(base_val, value)
            else:
                base[key] = value
        else:
            base[key] = value
    return base


def init_config_from_template(template_dict: dict, filepath: str) -> None:
    """从 TEMPLATE dict 生成初始 YAML 配置文件。

    当配置文件不存在时使用此函数生成。生成的文件不包含注释
    （注释来自 config.example.yaml 或用户手动添加）。

    Args:
        template_dict: 模板字典（通常是 UserConfig.TEMPLATE）
        filepath: 目标文件路径
    """
    # 将普通 dict 转为 CommentedMap 以确保 ruamel.yaml 能正确处理
    yaml = get_yaml()
    with open(filepath, "w", encoding="UTF-8") as f:
        yaml.dump(template_dict, f)
    log.info(f"已生成初始配置文件: {filepath}")
