# -*- coding: utf-8 -*-
"""测试文件准备工具。

提供创建各种测试文件的辅助函数。
"""

import os
import tempfile
from pathlib import Path
from typing import Optional


def create_small_file(
    size_kb: int = 1,
    filename: str = "small.txt",
    directory: Optional[str] = None,
) -> str:
    """创建小测试文件。

    Args:
        size_kb: 文件大小（KB）
        filename: 文件名
        directory: 目录路径，默认为临时目录

    Returns:
        文件路径
    """
    if directory is None:
        directory = tempfile.gettempdir()

    file_path = Path(directory) / filename
    content = "x" * (size_kb * 1024)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(file_path)


def create_medium_file(
    size_mb: int = 1,
    filename: str = "medium.txt",
    directory: Optional[str] = None,
) -> str:
    """创建中等大小测试文件。

    Args:
        size_mb: 文件大小（MB）
        filename: 文件名
        directory: 目录路径，默认为临时目录

    Returns:
        文件路径
    """
    if directory is None:
        directory = tempfile.gettempdir()

    file_path = Path(directory) / filename
    content = "x" * (size_mb * 1024 * 1024)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(file_path)


def create_test_image(
    width: int = 100,
    height: int = 100,
    filename: str = "test.jpg",
    directory: Optional[str] = None,
) -> str:
    """创建测试图片文件。

    Args:
        width: 图片宽度
        height: 图片高度
        filename: 文件名
        directory: 目录路径，默认为临时目录

    Returns:
        文件路径
    """
    if directory is None:
        directory = tempfile.gettempdir()

    file_path = Path(directory) / filename

    # 创建简单的 JPEG 文件头
    # 这是一个最小的有效 JPEG 文件
    jpeg_header = bytes(
        [
            0xFF,
            0xD8,
            0xFF,
            0xE0,
            0x00,
            0x10,
            0x4A,
            0x46,
            0x49,
            0x46,
            0x00,
            0x01,
            0x01,
            0x00,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,
            0xFF,
            0xDB,
            0x00,
            0x43,
            0x00,
        ]
    )

    with open(file_path, "wb") as f:
        f.write(jpeg_header)
        # 添加一些填充数据
        f.write(b"\x00" * 1024)
        # JPEG 结束标记
        f.write(bytes([0xFF, 0xD9]))

    return str(file_path)


def create_test_video(
    filename: str = "test.mp4",
    directory: Optional[str] = None,
) -> str:
    """创建测试视频文件（最小有效 MP4）。

    Args:
        filename: 文件名
        directory: 目录路径，默认为临时目录

    Returns:
        文件路径
    """
    if directory is None:
        directory = tempfile.gettempdir()

    file_path = Path(directory) / filename

    # 创建最小的 MP4 文件结构
    # ftyp box
    ftyp = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    # mdat box (空)
    mdat = b"\x00\x00\x00\x08mdat"
    # moov box (简化)
    moov = b"\x00\x00\x00\x08moov"

    with open(file_path, "wb") as f:
        f.write(ftyp + mdat + moov)

    return str(file_path)


def cleanup_test_files(directory: Optional[str] = None, pattern: str = "test_*"):
    """清理测试文件。

    Args:
        directory: 目录路径，默认为临时目录
        pattern: 文件名匹配模式
    """
    if directory is None:
        directory = tempfile.gettempdir()

    dir_path = Path(directory)
    for file in dir_path.glob(pattern):
        try:
            file.unlink()
        except Exception:
            pass


def get_test_file_path(filename: str, directory: Optional[str] = None) -> str:
    """获取测试文件路径。

    Args:
        filename: 文件名
        directory: 目录路径，默认为临时目录

    Returns:
        文件路径
    """
    if directory is None:
        directory = tempfile.gettempdir()

    return str(Path(directory) / filename)
