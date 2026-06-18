# coding=UTF-8
"""交互状态管理器。

负责管理用户输入流程（如 /batch 的多步输入收集）、超时处理、
状态保存/恢复。详见 M2 阶段 Bot 简化模块设计。
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class BatchStep(str, Enum):
    """批量操作收集步骤枚举。"""

    SOURCE_CHANNEL = "source_channel"       # 源频道链接
    TARGET_CHANNEL = "target_channel"       # 目标频道链接
    MESSAGE_RANGE = "message_range"         # 消息范围
    FILTER_CONDITION = "filter_condition"   # 过滤条件
    COMPLETE = "complete"                   # 收集完成

    @classmethod
    def next_step(cls, current: "BatchStep") -> "BatchStep":
        """返回当前步骤的下一步骤。"""
        order = [
            cls.SOURCE_CHANNEL,
            cls.TARGET_CHANNEL,
            cls.MESSAGE_RANGE,
            cls.FILTER_CONDITION,
            cls.COMPLETE,
        ]
        idx = order.index(current)
        if idx >= len(order) - 1:
            return cls.COMPLETE
        return order[idx + 1]

    @classmethod
    def get_prompt(cls, step: "BatchStep") -> str:
        """返回当前步骤的用户提示文本。"""
        prompts = {
            cls.SOURCE_CHANNEL: "📥 请输入源频道链接（如 https://t.me/channel_name）",
            cls.TARGET_CHANNEL: "📤 请输入目标频道链接（如 https://t.me/channel_name）",
            cls.MESSAGE_RANGE: "🔢 请输入消息范围（格式：起始ID 结束ID，如 1 100）",
            cls.FILTER_CONDITION: "🔍 请输入过滤关键词（可选，直接回车跳过）",
            cls.COMPLETE: "✅ 所有信息已收集完成",
        }
        return prompts.get(step, "❓ 未知步骤")

    @classmethod
    def is_valid_input(cls, step: "BatchStep", input_text: str) -> bool:
        """验证当前步骤的输入是否有效。"""
        text = input_text.strip()

        if step == cls.SOURCE_CHANNEL:
            return text.startswith("https://t.me/")

        elif step == cls.TARGET_CHANNEL:
            return text.startswith("https://t.me/")

        elif step == cls.MESSAGE_RANGE:
            parts = text.split()
            if len(parts) != 2:
                return False
            try:
                start = int(parts[0])
                end = int(parts[1])
                return start > 0 and end >= start
            except ValueError:
                return False

        elif step == cls.FILTER_CONDITION:
            # 过滤条件可以为空
            return True

        return False


@dataclass
class StepResult:
    """步骤处理结果。"""

    success: bool                           # 是否成功
    current_step: BatchStep                 # 当前步骤
    next_step: Optional[BatchStep] = None   # 下一步骤
    message: str = ""                       # 提示消息
    collected_data: dict = field(default_factory=dict)  # 已收集的数据


@dataclass
class InteractionState:
    """单个用户交互流程的运行时状态。"""

    user_id: int                            # 用户 ID
    command: str                            # 触发的命令（如 /batch）
    current_step: BatchStep = BatchStep.SOURCE_CHANNEL  # 当前步骤
    collected_data: dict = field(default_factory=dict)  # 已收集的数据
    created_at: float = 0.0                 # 创建时间戳
    last_updated: float = 0.0               # 最后更新时间戳

    def __post_init__(self):
        """初始化时间戳。"""
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.last_updated == 0.0:
            self.last_updated = now

    def touch(self):
        """更新最后活动时间戳。"""
        self.last_updated = time.time()

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "user_id": self.user_id,
            "command": self.command,
            "current_step": self.current_step.value if isinstance(self.current_step, BatchStep) else self.current_step,
            "collected_data": self.collected_data,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InteractionState":
        """从字典反序列化。"""
        step_value = data.get("current_step", BatchStep.SOURCE_CHANNEL)
        # 兼容字符串和枚举值
        if isinstance(step_value, str):
            try:
                step = BatchStep(step_value)
            except ValueError:
                step = BatchStep.SOURCE_CHANNEL
        else:
            step = step_value

        return cls(
            user_id=data["user_id"],
            command=data["command"],
            current_step=step,
            collected_data=data.get("collected_data", {}),
            created_at=data.get("created_at", 0.0),
            last_updated=data.get("last_updated", 0.0),
        )


# ==================== InteractionManager ====================

class InteractionManager:
    """用户交互流程状态管理器。

    管理多步输入收集、超时处理、状态持久化。
    """

    # 数据字段映射（命令 -> 步骤 -> 收集字段名）
    _BATCH_FIELD_MAP = {
        BatchStep.SOURCE_CHANNEL: "source_channel",
        BatchStep.TARGET_CHANNEL: "target_channel",
        BatchStep.MESSAGE_RANGE: "message_range",
        BatchStep.FILTER_CONDITION: "filter_condition",
    }

    def __init__(
        self,
        timeout_seconds: int = 300,
        state_file: Optional[str] = None,
    ) -> None:
        """
        :param timeout_seconds: 无操作超时时间（秒），默认 5 分钟。
        :param state_file: 状态持久化文件路径；若为 None 则仅内存模式。
        """
        self.timeout_seconds = timeout_seconds
        self._state_file = state_file
        # user_id -> InteractionState
        self._active_flows: dict[int, InteractionState] = {}

    # ---- 活跃流程管理 ----

    def start_flow(self, user_id: int, command: str) -> InteractionState:
        """启动新的交互流程，覆盖已有的流程。

        :param user_id: 用户 ID
        :param command: 触发的命令（如 "/batch"）
        :return: 新的 InteractionState
        """
        # 移除旧流程
        self._active_flows.pop(user_id, None)

        state = InteractionState(user_id=user_id, command=command)
        self._active_flows[user_id] = state
        logger.info("交互流程已启动: user_id=%s, command=%s", user_id, command)
        return state

    def get_active_flow(self, user_id: int) -> Optional[InteractionState]:
        """获取用户的活跃流程，返回前检查是否超时。

        :param user_id: 用户 ID
        :return: InteractionState 或 None
        """
        state = self._active_flows.get(user_id)
        if state is None:
            return None

        # 检查超时
        if self._is_expired(state):
            self.cancel_flow(user_id)
            logger.info("交互流程已超时: user_id=%s", user_id)
            return None

        return state

    def has_active_flow(self, user_id: int) -> bool:
        """检查用户是否有活跃的交互流程。

        :param user_id: 用户 ID
        :return: 是否有活跃流程
        """
        return self.get_active_flow(user_id) is not None

    def cancel_flow(self, user_id: int) -> bool:
        """取消用户的交互流程。

        :param user_id: 用户 ID
        :return: 是否成功取消
        """
        if user_id in self._active_flows:
            del self._active_flows[user_id]
            logger.info("交互流程已取消: user_id=%s", user_id)
            return True
        return False

    def clear_all_flows(self) -> int:
        """清除所有活跃流程。

        :return: 清除的数量
        """
        count = len(self._active_flows)
        self._active_flows.clear()
        logger.info("已清除所有交互流程: count=%d", count)
        return count

    def get_all_active_flows(self) -> dict[int, InteractionState]:
        """获取所有活跃流程（已过滤过期）。

        :return: user_id -> InteractionState 字典
        """
        # 清理过期流程
        self.cleanup_expired_flows()
        return dict(self._active_flows)

    # ---- 步骤收集 ----

    def update_step(
        self,
        user_id: int,
        data: str,
    ) -> Optional[InteractionState]:
        """更新当前步骤并收集数据。

        :param user_id: 用户 ID
        :param data: 用户输入的数据
        :return: 更新后的状态，若无活跃流程则返回 None
        """
        state = self.get_active_flow(user_id)
        if state is None:
            return None

        current_step = state.current_step
        field_name = self._BATCH_FIELD_MAP.get(current_step)

        if field_name:
            state.collected_data[field_name] = data

        # 推进到下一步
        state.current_step = BatchStep.next_step(current_step)
        state.touch()
        logger.info(
            "步骤已更新: user_id=%s, step=%s",
            user_id,
            state.current_step.value,
        )
        return state

    def collect(
        self,
        user_id: int,
        input_text: str,
    ) -> Optional[StepResult]:
        """收集用户输入并自动推进流程。

        :param user_id: 用户 ID
        :param input_text: 用户输入的文本
        :return: StepResult 或 None（无活跃流程时）
        """
        state = self.get_active_flow(user_id)
        if state is None:
            return None

        current_step = state.current_step

        # 验证输入
        if not BatchStep.is_valid_input(current_step, input_text):
            return StepResult(
                success=False,
                current_step=current_step,
                message=f"❌ 输入格式无效，请重新输入\n{BatchStep.get_prompt(current_step)}",
            )

        # 收集数据
        field_name = self._BATCH_FIELD_MAP.get(current_step)
        if field_name:
            state.collected_data[field_name] = input_text.strip()

        # 推进步骤
        next_step = BatchStep.next_step(current_step)
        state.current_step = next_step
        state.touch()

        # 构建结果
        result_msg = ""
        if next_step == BatchStep.COMPLETE:
            result_msg = "✅ 所有信息已收集完成！"
            result_data = dict(state.collected_data)
        else:
            result_msg = f"✅ 已接收，{BatchStep.get_prompt(next_step)}"
            result_data = {}

        # 自动保存（如果有持久化路径）
        if self._state_file:
            self.save_state()

        return StepResult(
            success=True,
            current_step=next_step,
            next_step=BatchStep.next_step(next_step) if next_step != BatchStep.COMPLETE else None,
            message=result_msg,
            collected_data=result_data if next_step == BatchStep.COMPLETE else {},
        )

    def get_collected_data(self, user_id: int) -> Optional[dict]:
        """获取用户已收集的全部数据。

        :param user_id: 用户 ID
        :return: collected_data 字典或 None
        """
        state = self.get_active_flow(user_id)
        if state is None:
            return None
        return dict(state.collected_data)

    def get_step_prompt(self, user_id: int) -> Optional[str]:
        """获取当前步骤的提示文本。

        :param user_id: 用户 ID
        :return: 提示文本或 None
        """
        state = self.get_active_flow(user_id)
        if state is None:
            return None
        return BatchStep.get_prompt(state.current_step)

    # ---- 超时处理 ----

    def _is_expired(self, state: InteractionState) -> bool:
        """检查状态是否已超时。

        :param state: 交互状态
        :return: 是否超时
        """
        elapsed = time.time() - state.last_updated
        return elapsed > self.timeout_seconds

    def cleanup_expired_flows(self) -> int:
        """清理所有过期的交互流程。

        :return: 清理的数量
        """
        expired_ids = [
            uid for uid, state in self._active_flows.items()
            if self._is_expired(state)
        ]
        for uid in expired_ids:
            del self._active_flows[uid]

        if expired_ids:
            logger.info("已清理过期交互流程: count=%d", len(expired_ids))
        return len(expired_ids)

    # ---- 状态持久化 ----

    def save_state(self) -> bool:
        """将当前状态保存到文件。

        :return: 是否保存成功
        """
        if not self._state_file:
            return False

        try:
            data = {
                uid: state.to_dict()
                for uid, state in self._active_flows.items()
            }
            save_path = Path(self._state_file)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="UTF-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("交互状态已保存: file=%s", self._state_file)
            return True
        except Exception as e:
            logger.error("交互状态保存失败: %s", e)
            return False

    def load_state(self) -> bool:
        """从文件加载状态。

        :return: 是否加载成功
        """
        if not self._state_file:
            return False

        try:
            save_path = Path(self._state_file)
            if not save_path.exists():
                return False

            with open(save_path, "r", encoding="UTF-8") as f:
                data = json.load(f)

            self._active_flows.clear()
            for uid_str, state_dict in data.items():
                uid = int(uid_str)
                state = InteractionState.from_dict(state_dict)
                # 仅加载未过期的流程
                if not self._is_expired(state):
                    self._active_flows[uid] = state

            logger.info("交互状态已加载: file=%s, count=%d", self._state_file, len(self._active_flows))
            return True
        except Exception as e:
            logger.error("交互状态加载失败: %s", e)
            return False
