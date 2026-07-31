# coding=UTF-8
"""测试 path_tool.py 中的可移植路径工具函数。"""

import os
import sqlite3

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


class TestResolveDataDirectory:
    """测试 resolve_data_directory()：配置原始值 → 绝对路径。"""

    def test_relative_path(self, tmp_path):
        """相对路径 ./some_dir → 基于 project_root 的绝对路径。"""
        from module.utils.path_tool import resolve_data_directory

        project_root = str(tmp_path / "project")
        result = resolve_data_directory("./.trmd", project_root)
        expected = os.path.normpath(os.path.join(project_root, ".trmd"))
        assert result == expected

    def test_absolute_path(self, tmp_path):
        """绝对路径直接返回（规范化后）。"""
        from module.utils.path_tool import resolve_data_directory

        abs_path = str(tmp_path / "absolute_data")
        result = resolve_data_directory(abs_path, str(tmp_path / "irrelevant"))
        assert os.path.isabs(result)
        assert result == os.path.normpath(abs_path)

    def test_none_value(self, tmp_path):
        """None 值回退到默认 <project_root>/.trmd。"""
        from module.utils.path_tool import resolve_data_directory

        project_root = str(tmp_path / "project")
        result = resolve_data_directory(None, project_root)
        expected = os.path.normpath(os.path.join(project_root, ".trmd"))
        assert result == expected

    def test_empty_string(self, tmp_path):
        """空字符串等同于 None，回退到默认路径。"""
        from module.utils.path_tool import resolve_data_directory

        project_root = str(tmp_path / "project")
        result = resolve_data_directory("", project_root)
        expected = os.path.normpath(os.path.join(project_root, ".trmd"))
        assert result == expected

    def test_normpath(self, tmp_path):
        """路径分隔符规范化，去除 ./ 等。"""
        from module.utils.path_tool import resolve_data_directory

        project_root = str(tmp_path / "project")
        result = resolve_data_directory("./data/../.trmd", project_root)
        # 规范化后应该是 project_root/data 的上级再 .trmd = project_root/.trmd
        expected = os.path.normpath(os.path.join(project_root, "data", "..", ".trmd"))
        assert result == expected


class TestMigrateRepositoryDb:
    """测试 migrate_repository_db_if_needed()：旧路径数据库迁移。"""

    def test_migrate_from_root(self, tmp_path):
        """根目录有 repository.db → 移动到 data_dir 下。"""
        from module.utils.path_tool import migrate_repository_db_if_needed

        project_root = str(tmp_path / "project")
        os.makedirs(project_root, exist_ok=True)
        data_dir = os.path.join(project_root, ".trmd")
        os.makedirs(data_dir, exist_ok=True)

        # 在项目根目录创建旧 repository.db
        old_db_path = os.path.join(project_root, "repository.db")
        conn = sqlite3.connect(old_db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

        assert os.path.exists(old_db_path)

        migrate_repository_db_if_needed(project_root, data_dir)

        # 旧文件应被移动到新位置
        assert not os.path.exists(old_db_path)
        new_db_path = os.path.join(data_dir, "repository.db")
        assert os.path.exists(new_db_path)
        # 数据应完整保留
        conn = sqlite3.connect(new_db_path)
        rows = conn.execute("SELECT * FROM test").fetchall()
        conn.close()
        assert rows == [(1,)]

    def test_both_exist(self, tmp_path):
        """两边都存在 → 删除根目录的，保留 data_dir 下的。"""
        from module.utils.path_tool import migrate_repository_db_if_needed

        project_root = str(tmp_path / "project")
        os.makedirs(project_root, exist_ok=True)
        data_dir = os.path.join(project_root, ".trmd")
        os.makedirs(data_dir, exist_ok=True)

        # 在两边都创建 repository.db（用不同内容区分）
        old_db_path = os.path.join(project_root, "repository.db")
        new_db_path = os.path.join(data_dir, "repository.db")

        conn_old = sqlite3.connect(old_db_path)
        conn_old.execute("CREATE TABLE old_data (id INTEGER)")
        conn_old.execute("INSERT INTO old_data VALUES (99)")
        conn_old.commit()
        conn_old.close()

        conn_new = sqlite3.connect(new_db_path)
        conn_new.execute("CREATE TABLE new_data (id INTEGER)")
        conn_new.execute("INSERT INTO new_data VALUES (1)")
        conn_new.commit()
        conn_new.close()

        migrate_repository_db_if_needed(project_root, data_dir)

        # 根目录的应被删除，data_dir 的应保留且数据完整
        assert not os.path.exists(old_db_path)
        assert os.path.exists(new_db_path)
        conn = sqlite3.connect(new_db_path)
        rows = conn.execute("SELECT * FROM new_data").fetchall()
        conn.close()
        assert rows == [(1,)]

    def test_no_migration_needed(self, tmp_path):
        """根目录没有 repository.db → 空操作。"""
        from module.utils.path_tool import migrate_repository_db_if_needed

        project_root = str(tmp_path / "project")
        data_dir = os.path.join(project_root, ".trmd")
        os.makedirs(data_dir, exist_ok=True)

        # 根目录下没有 repository.db
        assert not os.path.exists(os.path.join(project_root, "repository.db"))

        migrate_repository_db_if_needed(project_root, data_dir)

        # 不应有任何文件被创建
        assert not os.path.exists(os.path.join(project_root, "repository.db"))
        assert not os.path.exists(os.path.join(data_dir, "repository.db"))

    def test_new_db_not_exists_dir_created(self, tmp_path):
        """data_dir 不存在时自动创建目录后迁移。"""
        from module.utils.path_tool import migrate_repository_db_if_needed

        project_root = str(tmp_path / "project")
        os.makedirs(project_root, exist_ok=True)
        data_dir = os.path.join(project_root, ".trmd")
        # data_dir 不创建

        # 在项目根目录创建旧 repository.db
        old_db_path = os.path.join(project_root, "repository.db")
        conn = sqlite3.connect(old_db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

        migrate_repository_db_if_needed(project_root, data_dir)

        # 应自动创建 data_dir 并迁移
        assert os.path.isdir(data_dir)
        assert not os.path.exists(old_db_path)
        assert os.path.exists(os.path.join(data_dir, "repository.db"))
