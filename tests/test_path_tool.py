# coding=UTF-8
"""测试 path_tool.py 中的可移植路径工具函数。"""

import os

from module.utils.path_tool import to_portable_path, from_portable_path


class TestToPortablePath:
    """测试 to_portable_path：绝对路径 → 可移植相对路径（/ 分隔符）。"""

    def test_basic_relative_conversion(self, tmp_path):
        """基本转换：绝对路径转为相对于 save_root 的路径。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "photo", "image.jpg")

        result = to_portable_path(file_path, save_root)
        assert result == "photo/image.jpg"

    def test_forward_slash_separator(self, tmp_path):
        """确保输出使用 / 分隔符（即使在 Windows 上）。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "channel", "video.mp4")

        result = to_portable_path(file_path, save_root)
        assert "\\" not in result
        assert "/" in result

    def test_file_at_root(self, tmp_path):
        """文件直接在 save_root 下（无子目录）。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "image.jpg")

        result = to_portable_path(file_path, save_root)
        assert result == "image.jpg"

    def test_relative_save_root(self, tmp_path):
        """save_root 为相对路径时也能正确处理。"""
        os.chdir(str(tmp_path))
        save_root = "./downloads"
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "photo", "test.jpg")

        result = to_portable_path(file_path, save_root)
        assert result == "photo/test.jpg"

    def test_deeply_nested_path(self, tmp_path):
        """深层嵌套路径。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "a", "b", "c", "file.mp4")

        result = to_portable_path(file_path, save_root)
        assert result == "a/b/c/file.mp4"

    def test_path_with_spaces(self, tmp_path):
        """路径包含空格。"""
        save_root = str(tmp_path / "my downloads")
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "photo folder", "my image.jpg")

        result = to_portable_path(file_path, save_root)
        assert result == "photo folder/my image.jpg"

    def test_path_with_unicode(self, tmp_path):
        """路径包含 Unicode 字符（如中文频道名）。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        file_path = os.path.join(save_root, "频道名", "图片.jpg")

        result = to_portable_path(file_path, save_root)
        assert result == "频道名/图片.jpg"


class TestFromPortablePath:
    """测试 from_portable_path：可移植相对路径 → 绝对路径。"""

    def test_basic_resolution(self, tmp_path):
        """基本解析：相对路径还原为绝对路径。"""
        save_root = str(tmp_path / "downloads")

        result = from_portable_path("photo/image.jpg", save_root)
        expected = os.path.normpath(os.path.join(save_root, "photo", "image.jpg"))
        assert result == expected

    def test_forward_slash_converted_to_platform_sep(self, tmp_path):
        """/ 分隔符被转换为平台分隔符。"""
        save_root = str(tmp_path / "downloads")

        result = from_portable_path("a/b/c/file.mp4", save_root)
        # 结果应该是一个有效的本地路径
        assert os.path.isabs(result)

    def test_file_at_root(self, tmp_path):
        """无子目录的文件。"""
        save_root = str(tmp_path / "downloads")

        result = from_portable_path("image.jpg", save_root)
        expected = os.path.normpath(os.path.join(save_root, "image.jpg"))
        assert result == expected

    def test_relative_save_root(self, tmp_path):
        """save_root 为相对路径时也能正确处理。"""
        os.chdir(str(tmp_path))
        save_root = "./downloads"

        result = from_portable_path("photo/test.jpg", save_root)
        assert os.path.isabs(result)
        assert result.endswith(
            os.path.join("downloads", "photo", "test.jpg").lstrip(os.sep)
        )

    def test_deeply_nested_path(self, tmp_path):
        """深层嵌套路径。"""
        save_root = str(tmp_path / "downloads")

        result = from_portable_path("a/b/c/file.mp4", save_root)
        assert "a" in result and "b" in result and "c" in result


class TestRoundTrip:
    """测试 to_portable_path 和 from_portable_path 的往返转换。"""

    def test_round_trip(self, tmp_path):
        """绝对路径 → 可移植路径 → 绝对路径，结果应与原始路径一致。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        original = os.path.abspath(os.path.join(save_root, "photo", "image.jpg"))

        portable = to_portable_path(original, save_root)
        restored = from_portable_path(portable, save_root)

        assert os.path.normpath(restored) == os.path.normpath(original)

    def test_round_trip_with_spaces(self, tmp_path):
        """含空格路径的往返转换。"""
        save_root = str(tmp_path / "my downloads")
        os.makedirs(save_root, exist_ok=True)
        original = os.path.abspath(
            os.path.join(save_root, "photo folder", "my image.jpg")
        )

        portable = to_portable_path(original, save_root)
        restored = from_portable_path(portable, save_root)

        assert os.path.normpath(restored) == os.path.normpath(original)

    def test_round_trip_with_unicode(self, tmp_path):
        """含 Unicode 的往返转换。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        original = os.path.abspath(os.path.join(save_root, "频道名", "图片.jpg"))

        portable = to_portable_path(original, save_root)
        restored = from_portable_path(portable, save_root)

        assert os.path.normpath(restored) == os.path.normpath(original)

    def test_round_trip_file_at_root(self, tmp_path):
        """文件直接在根目录的往返转换。"""
        save_root = str(tmp_path / "downloads")
        os.makedirs(save_root, exist_ok=True)
        original = os.path.abspath(os.path.join(save_root, "file.mp4"))

        portable = to_portable_path(original, save_root)
        restored = from_portable_path(portable, save_root)

        assert os.path.normpath(restored) == os.path.normpath(original)

    def test_round_trip_different_save_root_prefix(self, tmp_path):
        """不同 save_root 前缀下，可移植路径可正确还原。"""
        # 模拟开发环境 (Windows)
        dev_root = str(tmp_path / "workspace" / "downloads")
        os.makedirs(dev_root, exist_ok=True)
        original_dev = os.path.abspath(os.path.join(dev_root, "photo", "img.jpg"))

        portable = to_portable_path(original_dev, dev_root)

        # 模拟生产环境 (Docker)，不同前缀
        prod_root = str(tmp_path / "app" / "downloads")

        restored_prod = from_portable_path(portable, prod_root)
        expected_prod = os.path.normpath(os.path.join(prod_root, "photo", "img.jpg"))

        assert os.path.normpath(restored_prod) == expected_prod
