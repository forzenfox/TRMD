# coding=UTF-8
"""频道与消息相关 Pydantic 数据模型。"""

import re
from typing import Optional, Literal
from pydantic import BaseModel, field_validator, model_validator


class ChatOut(BaseModel):
    """频道响应数据。"""

    id: str
    title: str
    type: str
    username: Optional[str] = None


class ChatResolveOut(BaseModel):
    """IdentifierService 解析后的对话信息响应数据。"""

    chat_id: int
    chat_type: str
    chat_name: str
    username: Optional[str] = None
    message_count: int = -1
    media_count: int = -1
    has_access: bool = True
    is_private: bool = False


class MessageRangeRequest(BaseModel):
    """消息范围分析请求体。

    支持五种消息范围模式：
    - id_range: 消息 ID 范围（需要 min_id 和 max_id）
    - date_range: 日期范围（需要 start_date 和 end_date，格式 YYYY-MM-DD）
    - multiple_ids: 多个消息 ID 或链接（需要 message_list）
    - all: 全部消息（不需要其他参数）
    - recent: 最近 N 条消息（需要 recent_count）
    """

    range_mode: Literal["id_range", "date_range", "multiple_ids", "all", "recent"]
    min_id: Optional[int] = None
    max_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    message_list: Optional[list[str]] = None
    download_type: Optional[list[str]] = None
    recent_count: Optional[int] = None

    @field_validator("range_mode")
    @classmethod
    def validate_range_mode(cls, v: str) -> str:
        valid_modes = {"id_range", "date_range", "multiple_ids", "all", "recent"}
        if v not in valid_modes:
            raise ValueError(f"range_mode 必须是以下之一: {', '.join(valid_modes)}")
        return v

    @model_validator(mode="after")
    def check_recent_count(self):
        """recent 模式必须提供 recent_count，其他模式不允许携带。"""
        if self.range_mode == "recent":
            if self.recent_count is None or self.recent_count <= 0:
                raise ValueError("range_mode='recent' 时 recent_count 必须大于 0")
        elif self.recent_count is not None:
            raise ValueError("range_mode 不是 recent 时，recent_count 必须为 None")
        return self

    def validate_for_mode(self) -> tuple[bool, list[str]]:
        """根据 range_mode 验证字段组合。

        Returns:
            (是否有效, 错误列表)
        """
        errors: list[str] = []

        if self.range_mode == "id_range":
            if self.min_id is None:
                errors.append("id_range 模式需要提供 min_id")
            if self.max_id is None:
                errors.append("id_range 模式需要提供 max_id")
            if self.min_id is not None and self.max_id is not None:
                if self.min_id > self.max_id:
                    errors.append("min_id 不能大于 max_id")

        elif self.range_mode == "date_range":
            if not self.start_date:
                errors.append("date_range 模式需要提供 start_date")
            if not self.end_date:
                errors.append("date_range 模式需要提供 end_date")
            # 验证日期格式
            date_pattern = r"^\d{4}-\d{2}-\d{2}$"
            if self.start_date and not re.match(date_pattern, self.start_date):
                errors.append("start_date 格式应为 YYYY-MM-DD")
            if self.end_date and not re.match(date_pattern, self.end_date):
                errors.append("end_date 格式应为 YYYY-MM-DD")

        elif self.range_mode == "multiple_ids":
            if not self.message_list or len(self.message_list) == 0:
                errors.append("multiple_ids 模式需要提供 message_list")

        elif self.range_mode == "recent":
            if self.recent_count is None or self.recent_count <= 0:
                errors.append("recent 模式需要提供 recent_count 且大于 0")

        # all 模式不需要额外验证

        return (len(errors) == 0, errors)

    def parse_message_ids(self) -> list[int]:
        """将消息范围解析为消息 ID 列表。

        仅适用于 id_range 和 multiple_ids 模式。
        对于 date_range、all 和 recent 模式，返回空列表（需要 Telegram API 查询）。

        Returns:
            消息 ID 列表
        """
        if (
            self.range_mode == "id_range"
            and self.min_id is not None
            and self.max_id is not None
        ):
            return list(range(self.min_id, self.max_id + 1))

        elif self.range_mode == "multiple_ids" and self.message_list:
            ids = []
            for item in self.message_list:
                item = item.strip()
                if not item:
                    continue
                # 尝试从链接中提取消息 ID
                # 支持格式: https://t.me/channel/123 或 t.me/channel/123 或 纯数字
                match = re.search(r"/(\d+)$", item)
                if match:
                    ids.append(int(match.group(1)))
                elif item.isdigit():
                    ids.append(int(item))
            return ids

        return []


class MessageEstimateRequest(BaseModel):
    """消息估算请求体（包含 chat_id）。"""

    chat_id: str  # 用户原始输入（URL/@username/数字ID）
    range_mode: Literal["id_range", "date_range", "multiple_ids", "all", "recent"] = (
        "all"
    )
    min_id: Optional[int] = None
    max_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    message_list: Optional[list[str]] = None
    type_filters: Optional[list[str]] = None
    recent_count: Optional[int] = None

    @model_validator(mode="after")
    def check_recent_count(self):
        """recent 模式必须提供 recent_count，其他模式不允许携带。"""
        if self.range_mode == "recent":
            if self.recent_count is None or self.recent_count <= 0:
                raise ValueError("range_mode='recent' 时 recent_count 必须大于 0")
        elif self.recent_count is not None:
            raise ValueError("range_mode 不是 recent 时，recent_count 必须为 None")
        return self


class MessageAnalyzeRequest(MessageEstimateRequest):
    """消息精确分析请求体（复用估算请求字段）。"""

    pass


class MessageEstimateOut(BaseModel):
    """消息估算响应数据。"""

    message_count: int
    total_size_bytes: int
    total_size_human: str
    estimated_duration_seconds: int
    sampled: bool
    sample_count: int = 0
    sample_valid_count: int = 0
    avg_size_bytes: float = 0.0
    range_mode: str = "id_range"
