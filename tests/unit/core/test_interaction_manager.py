# coding=UTF-8
"""InteractionManager 扩展测试 — 批次8 Bot 层桥接

测试覆盖：
- BatchStep 新枚举（TASK_TYPE, RANGE_MODE, RANGE_INPUT, FILTER_TYPES）
- next_step 条件分支（FORWARD 需要 TARGET_CHANNEL）
- get_prompt 差异化（RANGE_INPUT 根据 range_mode 显示不同提示）
- is_valid_input 差异化（RANGE_INPUT 根据 range_mode 验证不同格式）
- set_step_data 方法（内联键盘回调直接设置数据）
- advance_step 方法（内联键盘回调后推进步骤）
- collect 方法兼容新步骤
"""

from module.core.interaction_manager import (
    BatchStep,
    InteractionManager,
    InteractionState,
)


# ==================== BatchStep 枚举测试 ====================


class TestBatchStepEnum:
    """BatchStep 枚举值测试。"""

    def test_task_type_exists(self):
        assert BatchStep.TASK_TYPE == "task_type"

    def test_range_mode_exists(self):
        assert BatchStep.RANGE_MODE == "range_mode"

    def test_range_input_exists(self):
        assert BatchStep.RANGE_INPUT == "range_input"

    def test_filter_types_exists(self):
        assert BatchStep.FILTER_TYPES == "filter_types"

    def test_source_channel_exists(self):
        assert BatchStep.SOURCE_CHANNEL == "source_channel"

    def test_target_channel_exists(self):
        assert BatchStep.TARGET_CHANNEL == "target_channel"

    def test_complete_exists(self):
        assert BatchStep.COMPLETE == "complete"

    def test_old_message_range_removed(self):
        """旧的 MESSAGE_RANGE 和 FILTER_CONDITION 枚举不应再存在。"""
        assert not hasattr(BatchStep, "MESSAGE_RANGE")
        assert not hasattr(BatchStep, "FILTER_CONDITION")


# ==================== next_step 条件分支测试 ====================


class TestBatchStepNextStep:
    """BatchStep.next_step 条件分支测试。"""

    def test_task_type_to_source_channel(self):
        result = BatchStep.next_step(BatchStep.TASK_TYPE)
        assert result == BatchStep.SOURCE_CHANNEL

    def test_source_channel_download_to_range_mode(self):
        """DOWNLOAD 任务：SOURCE_CHANNEL 后直接到 RANGE_MODE。"""
        result = BatchStep.next_step(
            BatchStep.SOURCE_CHANNEL, {"task_type": "download"}
        )
        assert result == BatchStep.RANGE_MODE

    def test_source_channel_forward_to_target_channel(self):
        """FORWARD 任务：SOURCE_CHANNEL 后到 TARGET_CHANNEL。"""
        result = BatchStep.next_step(BatchStep.SOURCE_CHANNEL, {"task_type": "forward"})
        assert result == BatchStep.TARGET_CHANNEL

    def test_source_channel_no_data_to_range_mode(self):
        """无 collected_data 时默认为 download，跳到 RANGE_MODE。"""
        result = BatchStep.next_step(BatchStep.SOURCE_CHANNEL)
        assert result == BatchStep.RANGE_MODE

    def test_source_channel_empty_data_to_range_mode(self):
        result = BatchStep.next_step(BatchStep.SOURCE_CHANNEL, {})
        assert result == BatchStep.RANGE_MODE

    def test_target_channel_to_range_mode(self):
        result = BatchStep.next_step(BatchStep.TARGET_CHANNEL)
        assert result == BatchStep.RANGE_MODE

    def test_range_mode_to_range_input(self):
        result = BatchStep.next_step(BatchStep.RANGE_MODE)
        assert result == BatchStep.RANGE_INPUT

    def test_range_input_to_filter_types(self):
        result = BatchStep.next_step(BatchStep.RANGE_INPUT)
        assert result == BatchStep.FILTER_TYPES

    def test_filter_types_to_complete(self):
        result = BatchStep.next_step(BatchStep.FILTER_TYPES)
        assert result == BatchStep.COMPLETE

    def test_complete_stays_complete(self):
        result = BatchStep.next_step(BatchStep.COMPLETE)
        assert result == BatchStep.COMPLETE


# ==================== get_prompt 差异化测试 ====================


class TestBatchStepGetPrompt:
    """BatchStep.get_prompt 差异化测试。"""

    def test_task_type_prompt(self):
        prompt = BatchStep.get_prompt(BatchStep.TASK_TYPE)
        assert "任务类型" in prompt or "选择" in prompt

    def test_source_channel_prompt(self):
        prompt = BatchStep.get_prompt(BatchStep.SOURCE_CHANNEL)
        assert "源频道" in prompt

    def test_target_channel_prompt(self):
        prompt = BatchStep.get_prompt(BatchStep.TARGET_CHANNEL)
        assert "目标频道" in prompt

    def test_range_mode_prompt(self):
        prompt = BatchStep.get_prompt(BatchStep.RANGE_MODE)
        assert "范围" in prompt or "模式" in prompt

    def test_range_input_id_range(self):
        """id_range 模式的提示文本。"""
        prompt = BatchStep.get_prompt(BatchStep.RANGE_INPUT, {"range_mode": "id_range"})
        assert "ID" in prompt

    def test_range_input_date_range(self):
        """date_range 模式的提示文本。"""
        prompt = BatchStep.get_prompt(
            BatchStep.RANGE_INPUT, {"range_mode": "date_range"}
        )
        assert "日期" in prompt

    def test_range_input_multiple_ids(self):
        """multiple_ids 模式的提示文本。"""
        prompt = BatchStep.get_prompt(
            BatchStep.RANGE_INPUT, {"range_mode": "multiple_ids"}
        )
        assert "列表" in prompt or "ID" in prompt

    def test_range_input_all(self):
        """all 模式的提示文本。"""
        prompt = BatchStep.get_prompt(BatchStep.RANGE_INPUT, {"range_mode": "all"})
        assert "全部" in prompt or "所有" in prompt

    def test_range_input_default_is_id_range(self):
        """无 collected_data 时默认显示 id_range 提示。"""
        prompt = BatchStep.get_prompt(BatchStep.RANGE_INPUT)
        assert "ID" in prompt

    def test_filter_types_prompt(self):
        prompt = BatchStep.get_prompt(BatchStep.FILTER_TYPES)
        assert "类型" in prompt or "过滤" in prompt

    def test_complete_prompt(self):
        prompt = BatchStep.get_prompt(BatchStep.COMPLETE)
        assert "完成" in prompt or "✅" in prompt


# ==================== is_valid_input 差异化测试 ====================


class TestBatchStepIsValidInput:
    """BatchStep.is_valid_input 差异化测试。"""

    # --- SOURCE_CHANNEL ---
    def test_source_channel_valid(self):
        assert BatchStep.is_valid_input(
            BatchStep.SOURCE_CHANNEL, "https://t.me/channel"
        )

    def test_source_channel_invalid(self):
        assert not BatchStep.is_valid_input(BatchStep.SOURCE_CHANNEL, "not a url")

    # --- TARGET_CHANNEL ---
    def test_target_channel_valid(self):
        assert BatchStep.is_valid_input(BatchStep.TARGET_CHANNEL, "https://t.me/target")

    def test_target_channel_invalid(self):
        assert not BatchStep.is_valid_input(BatchStep.TARGET_CHANNEL, "random text")

    # --- RANGE_INPUT id_range ---
    def test_range_input_id_range_valid(self):
        assert BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "1 100", {"range_mode": "id_range"}
        )

    def test_range_input_id_range_invalid_order(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "100 1", {"range_mode": "id_range"}
        )

    def test_range_input_id_range_invalid_single(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "100", {"range_mode": "id_range"}
        )

    def test_range_input_id_range_invalid_text(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "abc def", {"range_mode": "id_range"}
        )

    def test_range_input_id_range_zero_start(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "0 100", {"range_mode": "id_range"}
        )

    # --- RANGE_INPUT date_range ---
    def test_range_input_date_range_valid(self):
        assert BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT,
            "2026-01-01 2026-06-01",
            {"range_mode": "date_range"},
        )

    def test_range_input_date_range_invalid_format(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT,
            "01-01-2026 06-01-2026",
            {"range_mode": "date_range"},
        )

    def test_range_input_date_range_single_date(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT,
            "2026-01-01",
            {"range_mode": "date_range"},
        )

    def test_range_input_date_range_invalid_text(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT,
            "abc def",
            {"range_mode": "date_range"},
        )

    # --- RANGE_INPUT multiple_ids ---
    def test_range_input_multiple_ids_valid(self):
        assert BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "100, 200, 300", {"range_mode": "multiple_ids"}
        )

    def test_range_input_multiple_ids_links(self):
        assert BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT,
            "https://t.me/ch/100",
            {"range_mode": "multiple_ids"},
        )

    def test_range_input_multiple_ids_empty(self):
        assert not BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "  ", {"range_mode": "multiple_ids"}
        )

    # --- RANGE_INPUT all ---
    def test_range_input_all_any_input(self):
        """all 模式下任何输入都有效（实际不需要输入）。"""
        assert BatchStep.is_valid_input(
            BatchStep.RANGE_INPUT, "anything", {"range_mode": "all"}
        )

    # --- RANGE_INPUT default ---
    def test_range_input_default_is_id_range(self):
        """无 collected_data 时默认按 id_range 验证。"""
        assert BatchStep.is_valid_input(BatchStep.RANGE_INPUT, "1 100")
        assert not BatchStep.is_valid_input(BatchStep.RANGE_INPUT, "abc")

    # --- TASK_TYPE（内联键盘步骤，不接受文本输入）---
    def test_task_type_rejects_text(self):
        assert not BatchStep.is_valid_input(BatchStep.TASK_TYPE, "download")

    # --- RANGE_MODE（内联键盘步骤，不接受文本输入）---
    def test_range_mode_rejects_text(self):
        assert not BatchStep.is_valid_input(BatchStep.RANGE_MODE, "id_range")

    # --- FILTER_TYPES（内联键盘步骤，不接受文本输入）---
    def test_filter_types_rejects_text(self):
        assert not BatchStep.is_valid_input(BatchStep.FILTER_TYPES, "video")


# ==================== InteractionManager set_step_data 测试 ====================


class TestInteractionManagerSetStepData:
    """InteractionManager.set_step_data 方法测试。"""

    def test_set_step_data_success(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        result = im.set_step_data(1, "task_type", "download")
        assert result is True
        data = im.get_collected_data(1)
        assert data["task_type"] == "download"

    def test_set_step_data_no_flow(self):
        im = InteractionManager()
        result = im.set_step_data(999, "task_type", "download")
        assert result is False

    def test_set_step_data_overwrite(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        im.set_step_data(1, "task_type", "download")
        im.set_step_data(1, "task_type", "forward")
        data = im.get_collected_data(1)
        assert data["task_type"] == "forward"

    def test_set_step_data_filter_types_list(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        im.set_step_data(1, "filter_types", ["video", "photo"])
        data = im.get_collected_data(1)
        assert data["filter_types"] == ["video", "photo"]


# ==================== InteractionManager advance_step 测试 ====================


class TestInteractionManagerAdvanceStep:
    """InteractionManager.advance_step 方法测试。"""

    def test_advance_from_task_type(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        im.set_step_data(1, "task_type", "download")
        result = im.advance_step(1)
        assert result is not None
        assert result.current_step == BatchStep.SOURCE_CHANNEL

    def test_advance_from_source_channel_download(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        # 手动设置到 SOURCE_CHANNEL 步骤
        state = im.get_active_flow(1)
        state.current_step = BatchStep.SOURCE_CHANNEL
        im.set_step_data(1, "task_type", "download")
        result = im.advance_step(1)
        assert result is not None
        assert result.current_step == BatchStep.RANGE_MODE

    def test_advance_from_source_channel_forward(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        state = im.get_active_flow(1)
        state.current_step = BatchStep.SOURCE_CHANNEL
        im.set_step_data(1, "task_type", "forward")
        result = im.advance_step(1)
        assert result is not None
        assert result.current_step == BatchStep.TARGET_CHANNEL

    def test_advance_no_flow(self):
        im = InteractionManager()
        result = im.advance_step(999)
        assert result is None


# ==================== InteractionManager collect 兼容测试 ====================


class TestInteractionManagerCollect:
    """InteractionManager.collect 方法兼容新步骤的测试。"""

    def test_collect_source_channel(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        # 手动推进到 SOURCE_CHANNEL
        state = im.get_active_flow(1)
        state.current_step = BatchStep.SOURCE_CHANNEL
        im.set_step_data(1, "task_type", "download")

        result = im.collect(1, "https://t.me/channel")
        assert result is not None
        assert result.success is True

    def test_collect_range_input_id_range(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        state = im.get_active_flow(1)
        state.current_step = BatchStep.RANGE_INPUT
        im.set_step_data(1, "range_mode", "id_range")

        result = im.collect(1, "1 100")
        assert result is not None
        assert result.success is True
        assert "1 100" == im.get_collected_data(1).get("range_input")

    def test_collect_range_input_date_range(self):
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        state = im.get_active_flow(1)
        state.current_step = BatchStep.RANGE_INPUT
        im.set_step_data(1, "range_mode", "date_range")

        result = im.collect(1, "2026-01-01 2026-06-01")
        assert result is not None
        assert result.success is True

    def test_collect_keyboard_step_rejected(self):
        """内联键盘步骤（TASK_TYPE/RANGE_MODE/FILTER_TYPES）应拒绝文本输入。"""
        im = InteractionManager()
        im.start_flow(user_id=1, command="/batch")
        # 默认步骤是 TASK_TYPE
        im.get_active_flow(1)
        # TASK_TYPE 不应有 _BATCH_FIELD_MAP 映射
        result = im.collect(1, "download")
        # collect 中 is_valid_input 应拒绝 TASK_TYPE 步骤的文本输入
        assert result is not None
        assert result.success is False


# ==================== InteractionState 默认步骤测试 ====================


class TestInteractionStateDefaultStep:
    """InteractionState 默认步骤应改为 TASK_TYPE。"""

    def test_default_step_is_task_type(self):
        state = InteractionState(user_id=1, command="/batch")
        assert state.current_step == BatchStep.TASK_TYPE

    def test_from_dict_with_task_type(self):
        data = {
            "user_id": 1,
            "command": "/batch",
            "current_step": "task_type",
            "collected_data": {},
        }
        state = InteractionState.from_dict(data)
        assert state.current_step == BatchStep.TASK_TYPE

    def test_from_dict_backward_compatible_source_channel(self):
        """旧序列化数据中 current_step=source_channel 应能反序列化。"""
        data = {
            "user_id": 1,
            "command": "/batch",
            "current_step": "source_channel",
            "collected_data": {},
        }
        state = InteractionState.from_dict(data)
        assert state.current_step == BatchStep.SOURCE_CHANNEL
