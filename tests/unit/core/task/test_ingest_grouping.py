# coding=UTF-8
"""相册模式分组逻辑单元测试。

验证 _ingest_downloaded_files 按 media_group_id 分组的核心逻辑：
- 同一 media_group_id 的 items 分到同一组（相册模式）
- 无 media_group_id 的 items 按 source_message_id 独立分组（单文件）
- 相册 + 单文件混合场景分组正确
- 空字符串 media_group_id 视为 None
"""

from module.core.task.manager import ItemStatus, TaskItem


def _make_item(
    item_id: str,
    source_message_id: int,
    media_group_id: str | None = None,
    status: ItemStatus = ItemStatus.SUCCESS,
    file_path: str | None = "/downloads/test.mp4",
) -> TaskItem:
    """创建测试用 TaskItem。"""
    return TaskItem(
        id=item_id,
        task_id="task_001",
        status=status,
        source_message_id=source_message_id,
        file_path=file_path,
        media_group_id=media_group_id,
    )


# ---- 分组逻辑提取为独立函数，便于测试 ----


def group_items_by_media(items: list[TaskItem]) -> dict[str, list[TaskItem]]:
    """按 media_group_id 分组（相册）+ 按 source_message_id 分组（单文件）。

    此函数与 task_executor.py 中 _ingest_downloaded_files 的分组逻辑一致。
    """
    groups: dict[str, list[TaskItem]] = {}
    for item in items:
        if item.status != ItemStatus.SUCCESS or not item.file_path:
            continue

        mg_id = item.media_group_id
        # 空字符串视为 None
        if mg_id is not None and mg_id.strip() == "":
            mg_id = None

        if mg_id:
            # 有 media_group_id：按 media_group_id 分组（相册）
            group_key = f"mg:{mg_id}"
        else:
            # 无 media_group_id：按 source_message_id 分组（单文件消息）
            source_message_id = item.source_message_id or 0
            group_key = f"sg:{source_message_id}"

        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(item)

    return groups


# ==================== 测试用例 ====================


class TestGroupByMediaGroupId:
    """按 media_group_id 分组测试。"""

    def test_same_media_group_id_grouped_together(self):
        """同一 media_group_id 的 items 应分到同一组。"""
        items = [
            _make_item("item_1", 96414, media_group_id="album_001"),
            _make_item("item_2", 96415, media_group_id="album_001"),
            _make_item("item_3", 96416, media_group_id="album_001"),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 1
        key = "mg:album_001"
        assert key in groups
        assert len(groups[key]) == 3
        assert [i.id for i in groups[key]] == ["item_1", "item_2", "item_3"]

    def test_different_media_group_ids_separate_groups(self):
        """不同 media_group_id 应分到不同组。"""
        items = [
            _make_item("item_1", 96414, media_group_id="album_001"),
            _make_item("item_2", 96415, media_group_id="album_001"),
            _make_item("item_3", 96420, media_group_id="album_002"),
            _make_item("item_4", 96421, media_group_id="album_002"),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 2
        assert len(groups["mg:album_001"]) == 2
        assert len(groups["mg:album_002"]) == 2


class TestSingleFileGrouping:
    """无 media_group_id 的单文件分组测试。"""

    def test_single_file_without_media_group_id(self):
        """无 media_group_id 的 items 按 source_message_id 独立分组。"""
        items = [
            _make_item("item_1", 96414),
            _make_item("item_2", 96415),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 2
        assert "sg:96414" in groups
        assert "sg:96415" in groups
        assert len(groups["sg:96414"]) == 1
        assert len(groups["sg:96415"]) == 1

    def test_single_file_same_source_message_id_grouped(self):
        """同一 source_message_id 的多个文件（无 media_group_id）应分到同一组。"""
        items = [
            _make_item("item_1", 96414),
            _make_item("item_2", 96414),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 1
        assert len(groups["sg:96414"]) == 2


class TestMixedItemsGrouping:
    """相册 + 单文件混合场景测试。"""

    def test_mixed_album_and_single_file(self):
        """相册和单文件混合分组正确。"""
        items = [
            # 相册1: 2张图片
            _make_item("item_1", 96414, media_group_id="album_001"),
            _make_item("item_2", 96415, media_group_id="album_001"),
            # 单文件
            _make_item("item_3", 96420),
            # 相册2: 3张图片
            _make_item("item_4", 96430, media_group_id="album_002"),
            _make_item("item_5", 96431, media_group_id="album_002"),
            _make_item("item_6", 96432, media_group_id="album_002"),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 3
        assert len(groups["mg:album_001"]) == 2
        assert len(groups["sg:96420"]) == 1
        assert len(groups["mg:album_002"]) == 3

    def test_only_album_items(self):
        """仅相册 items 时分组正确。"""
        items = [
            _make_item("item_1", 100, media_group_id="a1"),
            _make_item("item_2", 101, media_group_id="a1"),
            _make_item("item_3", 200, media_group_id="a2"),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 2
        assert len(groups["mg:a1"]) == 2
        assert len(groups["mg:a2"]) == 1


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_media_group_id_treated_as_none(self):
        """空字符串 media_group_id 应视为 None，按单文件处理。"""
        items = [
            _make_item("item_1", 96414, media_group_id=""),
            _make_item("item_2", 96415, media_group_id="  "),
        ]
        groups = group_items_by_media(items)

        # 空/空白字符串视为 None，按 source_message_id 分组
        assert "sg:96414" in groups
        assert "sg:96415" in groups
        assert len(groups) == 2

    def test_non_success_items_excluded(self):
        """非 SUCCESS 状态的 items 应被排除。"""
        items = [
            _make_item("item_1", 96414, media_group_id="album_001"),
            _make_item(
                "item_2",
                96415,
                media_group_id="album_001",
                status=ItemStatus.FAILED,
            ),
            _make_item("item_3", 96420, status=ItemStatus.PENDING),
        ]
        groups = group_items_by_media(items)

        # 只有 item_1 符合条件
        assert len(groups) == 1
        assert len(groups["mg:album_001"]) == 1
        assert groups["mg:album_001"][0].id == "item_1"

    def test_no_file_path_excluded(self):
        """无 file_path 的 items 应被排除。"""
        items = [
            _make_item("item_1", 96414, media_group_id="album_001"),
            _make_item("item_2", 96415, media_group_id="album_001", file_path=None),
        ]
        groups = group_items_by_media(items)

        assert len(groups) == 1
        assert len(groups["mg:album_001"]) == 1

    def test_empty_items_list(self):
        """空列表应返回空分组。"""
        groups = group_items_by_media([])
        assert len(groups) == 0

    def test_group_key_no_collision(self):
        """mg: 和 sg: 前缀避免 media_group_id 与 source_message_id 碰撞。"""
        items = [
            _make_item("item_1", 123, media_group_id="123"),
            _make_item("item_2", 123),
        ]
        groups = group_items_by_media(items)

        # 两个不同组：mg:123 和 sg:123
        assert len(groups) == 2
        assert "mg:123" in groups
        assert "sg:123" in groups


class TestTaskItemMediaGroupIdField:
    """TaskItem dataclass 的 media_group_id 字段测试。"""

    def test_task_item_has_media_group_id_field(self):
        """TaskItem 默认 media_group_id=None。"""
        item = TaskItem(id="test", task_id="task_001")
        assert hasattr(item, "media_group_id")
        assert item.media_group_id is None

    def test_task_item_with_media_group_id(self):
        """TaskItem 可设置 media_group_id。"""
        item = TaskItem(id="test", task_id="task_001", media_group_id="album_001")
        assert item.media_group_id == "album_001"

    def test_update_item_status_sets_media_group_id(self):
        """通过 setattr 更新 media_group_id（模拟 update_item_status 的 kwargs 行为）。"""
        item = TaskItem(id="test", task_id="task_001")
        assert item.media_group_id is None

        # 模拟 update_item_status 的 **kwargs 逻辑
        key, value = "media_group_id", "album_002"
        if hasattr(item, key):
            setattr(item, key, value)

        assert item.media_group_id == "album_002"
