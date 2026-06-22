#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出 OpenAPI Schema 为 JSON 文件。

使用方法:
    python scripts/export_openapi.py

输出文件:
    docs/openapi.json
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from module.api.app import create_app


def export_openapi(output_path: str = "docs/openapi.json"):
    """导出 OpenAPI Schema。

    Args:
        output_path: 输出文件路径，默认为 docs/openapi.json
    """
    app = create_app()
    schema = app.openapi()

    # 确保输出目录存在
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 写入 JSON 文件
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"OpenAPI Schema 已导出到: {output_file}")
    print(f"API 端点数量: {len(schema.get('paths', {}))}")

    # 打印端点列表
    print("\n端点列表:")
    for path, methods in schema.get("paths", {}).items():
        for method in methods.keys():
            print(f"  {method.upper()} {path}")

    return schema


if __name__ == "__main__":
    export_openapi()
