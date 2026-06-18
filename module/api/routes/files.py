# coding=UTF-8
"""文件管理路由。

提供文件列表浏览功能。
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query

from module.api.dependencies import require_token, get_file_manager, get_config_manager
from module.api.responses import json_response
from module.api.models.file import FileInfo, FileListOut

router = APIRouter(prefix="/files", tags=["文件"])


@router.get("")
async def list_files(
    request: Request,
    token: str = Depends(require_token),
    path: Optional[str] = Query(None, description="目录路径，默认为下载根目录"),
    recursive: bool = Query(False, description="是否递归"),
):
    """获取文件列表。

    :param request: FastAPI 请求对象
    :param token: 认证 Token
    :param path: 目录路径
    :param recursive: 是否递归
    :return: 文件列表
    """
    # 获取下载根目录
    config_manager = get_config_manager(request)
    if path:
        target_path = os.path.abspath(path)
    else:
        # 默认使用下载目录
        try:
            target_path = os.path.abspath(config_manager.save_directory or "downloads")
        except AttributeError:
            target_path = os.path.abspath("downloads")

    if not os.path.exists(target_path):
        # 如果目录不存在，返回空列表
        return json_response(data={"path": target_path, "items": []})

    if not os.path.isdir(target_path):
        return json_response(data={"path": target_path, "items": []})

    # 扫描目录
    items = []
    try:
        with os.scandir(target_path) as entries:
            for entry in entries:
                try:
                    stat = entry.stat()
                    if entry.is_dir():
                        items.append(FileInfo(
                            name=entry.name,
                            path=entry.path,
                            type="directory",
                            size=0,
                            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        ))
                    else:
                        items.append(FileInfo(
                            name=entry.name,
                            path=entry.path,
                            type="file",
                            size=stat.st_size,
                            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        ))
                except (PermissionError, OSError):
                    continue
    except PermissionError:
        return json_response(data={"path": target_path, "items": []})

    # 按名称排序
    items.sort(key=lambda x: (x.type == "file", x.name.lower()))

    return json_response(data={"path": target_path, "items": [i.model_dump() for i in items]})
