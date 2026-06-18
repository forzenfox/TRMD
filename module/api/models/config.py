# coding=UTF-8
"""配置相关 Pydantic 数据模型。"""

from typing import Optional

from pydantic import BaseModel, Field


class ResourceLimits(BaseModel):
    """资源限制配置。"""

    max_concurrent_tasks: int = 1
    max_download_concurrency: int = 3
    max_upload_concurrency: int = 1
    max_forward_concurrency: int = 1
    min_disk_space_gb: int = 2
    memory_limit_mb: int = 512
    task_size_warning_gb: int = 5
    task_size_max_gb: int = 10


class ProxyConfig(BaseModel):
    """代理配置。"""

    enable_proxy: bool = False
    scheme: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None


class ConfigOut(BaseModel):
    """配置响应数据。"""

    api_id: Optional[str] = None
    api_hash: Optional[str] = None
    bot_token: Optional[str] = None
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    download_type: list[str] = Field(default_factory=lambda: ["video", "photo"])
    max_retry_count: int = 3


class ConfigUpdate(BaseModel):
    """配置更新请求体。"""

    resource_limits: Optional[ResourceLimits] = None
    proxy: Optional[ProxyConfig] = None
    download_type: Optional[list[str]] = None
    max_retry_count: Optional[int] = None
