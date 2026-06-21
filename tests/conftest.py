# coding=UTF-8
"""pytest 全局配置。

module.parser 在导入时执行 parse_args()（解析 sys.argv），
而 pytest 传入的参数会触发 argparse 退出。通过 conftest.py
在测试收集前清空 sys.argv 来避免此问题。
"""

import sys

# 确保 module.parser.parse_args() 不会消费 pytest 参数
sys.argv = sys.argv[:1]  # 只保留脚本名
