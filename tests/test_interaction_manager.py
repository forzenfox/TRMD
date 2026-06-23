# coding=UTF-8
"""InteractionManager 单元测试。

测试交互状态管理器的核心功能：
- 流程注册与状态追踪
- 超时处理
- 步骤收集与验证
- 状态保存/恢复
"""

import time
from pathlib import Path

import pytest

from module.interaction_manager import (
    InteractionManager,
    InteractionState,
    BatchStep,
    StepResult,
)


# ==================== Fixtures ====================


@pytest.fixture
def manager():
    """提供基础 InteractionManager 实例（内存模式）。"""
    return InteractionManager(timeout_seconds=60)


@pytest.fixture
def manager_with_save(tmp_path):
    """提供带持久化路径的 InteractionManager 实例。"""
    save_file = tmp_path / "interaction_state.json"
    return InteractionManager(timeout_seconds=60, state_file=str(save_file))


# ==================== 交互状态数据模型测试 ====================


class TestInteractionState:
    """InteractionState 数据模型测试。"""

    def test_create_state(self):
        """应能创建 InteractionState 实例。"""
        state = InteractionState(
            user_id=123,
            command="/batch",
            current_step=BatchStep.SOURCE_CHANNEL,
            collected_data={"source": "https://t.me/test"},
        )
        assert state.user_id == 123
        assert state.command == "/batch"
        assert state.current_step == BatchStep.SOURCE_CHANNEL
        assert state.collected_data == {"source": "https://t.me/test"}

    def test_state_created_at(self):
        """创建时应自动设置 created_at 时间戳。"""
        state = InteractionState(user_id=123, command="/batch")
        assert state.created_at is not None
        assert isinstance(state.created_at, float)

    def test_state_last_updated(self):
        """last_updated 应初始化为 created_at。"""
        state = InteractionState(user_id=123, command="/batch")
        assert state.last_updated == state.created_at

    def test_state_to_dict(self):
        """to_dict() 应返回可序列化的字典。"""
        state = InteractionState(
            user_id=456,
            command="/batch",
            current_step=BatchStep.TARGET_CHANNEL,
            collected_data={"source": "https://t.me/a"},
        )
        d = state.to_dict()
        assert d["user_id"] == 456
        assert d["command"] == "/batch"
        assert d["current_step"] == BatchStep.TARGET_CHANNEL
        assert d["collected_data"] == {"source": "https://t.me/a"}

    def test_state_from_dict(self):
        """from_dict() 应从字典恢复状态。"""
        d = {
            "user_id": 789,
            "command": "/batch",
            "current_step": BatchStep.MESSAGE_RANGE,
            "collected_data": {"start_id": "1", "end_id": "100"},
            "created_at": 1000.0,
            "last_updated": 1000.0,
        }
        state = InteractionState.from_dict(d)
        assert state.user_id == 789
        assert state.command == "/batch"
        assert state.current_step == BatchStep.MESSAGE_RANGE
        assert state.collected_data == {"start_id": "1", "end_id": "100"}
        assert state.created_at == 1000.0

    def test_update_timestamp(self):
        """touch() 应更新 last_updated 时间戳。"""
        state = InteractionState(user_id=123, command="/batch")
        old_time = state.last_updated
        time.sleep(0.01)
        state.touch()
        assert state.last_updated > old_time


# ==================== BatchStep 枚举测试 ====================


class TestBatchStep:
    """BatchStep 枚举测试。"""

    def test_step_order(self):
        """步骤应按正确顺序定义。"""
        steps = list(BatchStep)
        assert steps[0] == BatchStep.SOURCE_CHANNEL
        assert steps[-1] == BatchStep.COMPLETE

    def test_next_step(self):
        """next_step() 应返回下一步骤。"""
        assert BatchStep.next_step(BatchStep.SOURCE_CHANNEL) == BatchStep.TARGET_CHANNEL
        assert BatchStep.next_step(BatchStep.TARGET_CHANNEL) == BatchStep.MESSAGE_RANGE
        assert (
            BatchStep.next_step(BatchStep.MESSAGE_RANGE) == BatchStep.FILTER_CONDITION
        )
        assert BatchStep.next_step(BatchStep.FILTER_CONDITION) == BatchStep.COMPLETE

    def test_next_step_from_complete(self):
        """COMPLETE 步骤的下一步仍为 COMPLETE。"""
        assert BatchStep.next_step(BatchStep.COMPLETE) == BatchStep.COMPLETE

    def test_get_prompt(self):
        """get_prompt() 应返回对应的中文提示文本。"""
        assert "源频道" in BatchStep.get_prompt(BatchStep.SOURCE_CHANNEL)
        assert "目标频道" in BatchStep.get_prompt(BatchStep.TARGET_CHANNEL)
        assert "起始" in BatchStep.get_prompt(BatchStep.MESSAGE_RANGE)
        assert "过滤" in BatchStep.get_prompt(BatchStep.FILTER_CONDITION)

    def test_is_valid_input(self):
        """is_valid_input() 应验证输入格式。"""
        # 源频道 - 需要是 t.me 链接
        assert (
            BatchStep.is_valid_input(BatchStep.SOURCE_CHANNEL, "https://t.me/test")
            is True
        )
        assert BatchStep.is_valid_input(BatchStep.SOURCE_CHANNEL, "invalid") is False
        # 消息范围 - 需要两个数字
        assert BatchStep.is_valid_input(BatchStep.MESSAGE_RANGE, "1 100") is True
        assert BatchStep.is_valid_input(BatchStep.MESSAGE_RANGE, "abc") is False
        # 过滤条件 - 可以为空（跳过）
        assert BatchStep.is_valid_input(BatchStep.FILTER_CONDITION, "") is True
        assert BatchStep.is_valid_input(BatchStep.FILTER_CONDITION, "keyword") is True


# ==================== InteractionManager 核心测试 ====================


class TestInteractionManager:
    """InteractionManager 核心功能测试。"""

    def test_create_manager(self, manager):
        """应能创建 InteractionManager 实例。"""
        assert manager is not None
        assert manager.timeout_seconds == 60

    def test_get_active_flow_none(self, manager):
        """无活跃流程时应返回 None。"""
        assert manager.get_active_flow(123) is None

    def test_start_flow(self, manager):
        """start_flow() 应创建新的交互流程。"""
        state = manager.start_flow(user_id=123, command="/batch")
        assert state is not None
        assert state.user_id == 123
        assert state.command == "/batch"
        assert manager.get_active_flow(123) is state

    def test_start_flow_overwrites_existing(self, manager):
        """同一用户启动新流程应覆盖旧流程。"""
        manager.start_flow(user_id=123, command="/batch")
        new_state = manager.start_flow(user_id=123, command="/web")
        assert new_state.command == "/web"
        assert manager.get_active_flow(123) is new_state

    def test_update_step(self, manager):
        """update_step() 应更新当前步骤和收集的数据。"""
        state = manager.start_flow(user_id=123, command="/batch")
        updated = manager.update_step(user_id=123, data="https://t.me/source")
        assert updated is not None
        assert updated.collected_data.get("source_channel") == "https://t.me/source"

    def test_update_step_no_active_flow(self, manager):
        """无活跃流程时 update_step() 应返回 None。"""
        assert manager.update_step(user_id=123, data="test") is None

    def test_cancel_flow(self, manager):
        """cancel_flow() 应移除活跃流程。"""
        manager.start_flow(user_id=123, command="/batch")
        result = manager.cancel_flow(user_id=123)
        assert result is True
        assert manager.get_active_flow(123) is None

    def test_cancel_flow_no_flow(self, manager):
        """无活跃流程时 cancel_flow() 应返回 False。"""
        assert manager.cancel_flow(user_id=123) is False

    def test_has_active_flow(self, manager):
        """has_active_flow() 应正确反映流程状态。"""
        assert manager.has_active_flow(123) is False
        manager.start_flow(user_id=123, command="/batch")
        assert manager.has_active_flow(123) is True

    def test_collect_step_data(self, manager):
        """collect() 应收集步骤数据并自动推进。"""
        manager.start_flow(user_id=123, command="/batch")
        result = manager.collect(user_id=123, input_text="https://t.me/source")
        assert result is not None
        assert result.success is True
        assert result.next_step is not None

    def test_collect_invalid_input(self, manager):
        """collect() 对无效输入应返回失败。"""
        manager.start_flow(user_id=123, command="/batch")
        result = manager.collect(user_id=123, input_text="invalid_not_a_link")
        # 源频道步骤需要 t.me 链接
        assert result.success is False

    def test_collect_complete_steps(self, manager):
        """collect() 完成所有步骤后应返回 COMPLETE 状态。"""
        manager.start_flow(user_id=123, command="/batch")
        # 步骤1: 源频道
        r1 = manager.collect(user_id=123, input_text="https://t.me/source")
        assert r1.success is True
        # 步骤2: 目标频道
        r2 = manager.collect(user_id=123, input_text="https://t.me/target")
        assert r2.success is True
        # 步骤3: 消息范围
        r3 = manager.collect(user_id=123, input_text="1 100")
        assert r3.success is True
        # 步骤4: 过滤条件（可空）
        r4 = manager.collect(user_id=123, input_text="")
        assert r4.success is True
        # 步骤5: 完成
        assert r4.current_step == BatchStep.COMPLETE

    def test_get_collected_data(self, manager):
        """get_collected_data() 应返回收集的完整数据。"""
        manager.start_flow(user_id=123, command="/batch")
        manager.collect(user_id=123, input_text="https://t.me/source")
        manager.collect(user_id=123, input_text="https://t.me/target")
        manager.collect(user_id=123, input_text="1 100")
        manager.collect(user_id=123, input_text="video")
        data = manager.get_collected_data(user_id=123)
        assert data is not None
        assert data.get("source_channel") == "https://t.me/source"
        assert data.get("target_channel") == "https://t.me/target"

    def test_get_collected_data_no_flow(self, manager):
        """无活跃流程时 get_collected_data() 应返回 None。"""
        assert manager.get_collected_data(user_id=123) is None

    def test_get_step_prompt(self, manager):
        """get_step_prompt() 应返回当前步骤的提示。"""
        manager.start_flow(user_id=123, command="/batch")
        prompt = manager.get_step_prompt(user_id=123)
        assert prompt is not None
        assert "源频道" in prompt

    def test_get_step_prompt_no_flow(self, manager):
        """无活跃流程时 get_step_prompt() 应返回 None。"""
        assert manager.get_step_prompt(user_id=123) is None

    def test_get_all_active_flows(self, manager):
        """get_all_active_flows() 应返回所有活跃流程。"""
        manager.start_flow(user_id=1, command="/batch")
        manager.start_flow(user_id=2, command="/batch")
        flows = manager.get_all_active_flows()
        assert len(flows) == 2

    def test_clear_all_flows(self, manager):
        """clear_all_flows() 应清除所有流程。"""
        manager.start_flow(user_id=1, command="/batch")
        manager.start_flow(user_id=2, command="/batch")
        manager.clear_all_flows()
        assert len(manager.get_all_active_flows()) == 0


# ==================== 超时处理测试 ====================


class TestTimeoutHandling:
    """超时处理相关测试。"""

    def test_timeout_expires(self, manager):
        """超时后流程应自动失效。"""
        # 使用极短超时
        short_manager = InteractionManager(timeout_seconds=1)
        short_manager.start_flow(user_id=123, command="/batch")
        assert short_manager.has_active_flow(123) is True
        # 模拟超时
        time.sleep(1.1)
        assert short_manager.has_active_flow(123) is False

    def test_timeout_extends_on_update(self, manager):
        """每次更新步骤时应重置超时计时。"""
        short_manager = InteractionManager(timeout_seconds=2)
        short_manager.start_flow(user_id=123, command="/batch")
        time.sleep(1)
        # 更新步骤应重置超时
        short_manager.collect(user_id=123, input_text="https://t.me/source")
        time.sleep(1)
        # 仍应活跃（上次更新后只过了约 1 秒）
        assert short_manager.has_active_flow(123) is True

    def test_timeout_cleanup(self, manager):
        """cleanup_expired_flows() 应清除过期流程。"""
        short_manager = InteractionManager(timeout_seconds=1)
        short_manager.start_flow(user_id=1, command="/batch")
        short_manager.start_flow(user_id=2, command="/batch")
        time.sleep(1.1)
        count = short_manager.cleanup_expired_flows()
        assert count == 2
        assert len(short_manager.get_all_active_flows()) == 0


# ==================== 持久化测试 ====================


class TestStatePersistence:
    """状态持久化测试。"""

    def test_save_state(self, manager_with_save):
        """save_state() 应将状态写入文件。"""
        manager_with_save.start_flow(user_id=123, command="/batch")
        manager_with_save.save_state()
        save_file = Path(manager_with_save._state_file)
        assert save_file.exists()

    def test_load_state(self, manager_with_save):
        """load_state() 应从文件恢复状态。"""
        manager_with_save.start_flow(user_id=123, command="/batch")
        manager_with_save.collect(user_id=123, input_text="https://t.me/source")
        manager_with_save.save_state()

        # 新建实例并加载
        save_file = manager_with_save._state_file
        new_manager = InteractionManager(timeout_seconds=60, state_file=save_file)
        new_manager.load_state()
        state = new_manager.get_active_flow(123)
        assert state is not None
        assert state.command == "/batch"

    def test_load_nonexistent_file(self, manager_with_save):
        """加载不存在的文件不应抛出异常。"""
        manager_with_save._state_file = "/nonexistent/path/state.json"
        # 不应抛异常
        manager_with_save.load_state()

    def test_auto_save_on_collect(self, manager_with_save):
        """collect() 后状态文件应被更新。"""
        manager_with_save.start_flow(user_id=123, command="/batch")
        manager_with_save.save_state()
        old_mtime = Path(manager_with_save._state_file).stat().st_mtime
        time.sleep(0.1)
        manager_with_save.collect(user_id=123, input_text="https://t.me/source")
        new_mtime = Path(manager_with_save._state_file).stat().st_mtime
        assert new_mtime >= old_mtime


# ==================== StepResult 测试 ====================


class TestStepResult:
    """StepResult 数据模型测试。"""

    def test_success_result(self):
        """应能创建成功的结果。"""
        result = StepResult(
            success=True,
            current_step=BatchStep.TARGET_CHANNEL,
            next_step=BatchStep.MESSAGE_RANGE,
            message="步骤已完成",
        )
        assert result.success is True
        assert result.current_step == BatchStep.TARGET_CHANNEL
        assert result.next_step == BatchStep.MESSAGE_RANGE

    def test_failure_result(self):
        """应能创建失败的结果。"""
        result = StepResult(
            success=False,
            current_step=BatchStep.SOURCE_CHANNEL,
            message="输入格式无效",
        )
        assert result.success is False
        assert result.next_step is None

    def test_complete_result(self):
        """完成状态的结果。"""
        data = {"source": "https://t.me/a", "target": "https://t.me/b"}
        result = StepResult(
            success=True,
            current_step=BatchStep.COMPLETE,
            collected_data=data,
            message="所有步骤已完成",
        )
        assert result.collected_data == data
