# coding=UTF-8
"""配置管理路由。

提供配置读取与更新功能。
"""

from fastapi import APIRouter, Depends, Request

from module.api.dependencies import require_token, get_config_manager
from module.api.responses import json_response
from module.api.models.config import ConfigOut, ConfigUpdate, ResourceLimits, ProxyConfig

router = APIRouter(prefix="/config", tags=["配置"])


@router.get("")
async def get_config(
    request: Request,
    token: str = Depends(require_token),
):
    """获取当前配置。"""
    config_manager = get_config_manager(request)

    try:
        # 从配置管理器读取配置
        config = getattr(config_manager, "config", {})

        resource_limits = ResourceLimits(
            max_concurrent_tasks=config.get("max_tasks", {}).get("download", 3),
            max_download_concurrency=config.get("max_tasks", {}).get("download", 3),
            max_upload_concurrency=config.get("max_tasks", {}).get("upload", 3),
        )

        proxy_data = config.get("proxy", {})
        proxy_config = ProxyConfig(
            enable_proxy=proxy_data.get("enable_proxy", False),
            scheme=proxy_data.get("scheme"),
            hostname=proxy_data.get("hostname"),
            port=proxy_data.get("port"),
            username=proxy_data.get("username"),
            password=proxy_data.get("password"),
        )

        result = ConfigOut(
            api_id=config.get("api_id"),
            api_hash=config.get("api_hash"),
            bot_token=config.get("bot_token"),
            resource_limits=resource_limits,
            proxy=proxy_config,
            download_type=config.get("download_type", ["video", "photo"]),
            max_retry_count=config.get("max_retries", {}).get("download", 3),
        )

        return json_response(data=result.model_dump())
    except Exception as e:
        return json_response(
            data=None,
            message=f"读取配置失败: {str(e)}",
            status_code=500,
        )


@router.put("")
async def update_config(
    request: Request,
    body: ConfigUpdate,
    token: str = Depends(require_token),
):
    """更新配置。"""
    config_manager = get_config_manager(request)

    try:
        # 校验资源限制
        if body.resource_limits:
            rl = body.resource_limits
            if rl.task_size_max_gb <= rl.task_size_warning_gb:
                return json_response(
                    data=None,
                    message="task_size_max_gb 必须大于 task_size_warning_gb",
                    status_code=400,
                )

        # 更新配置
        config = getattr(config_manager, "config", {})

        if body.download_type is not None:
            config["download_type"] = body.download_type

        if body.max_retry_count is not None:
            if "max_retries" not in config:
                config["max_retries"] = {}
            config["max_retries"]["download"] = body.max_retry_count

        if body.resource_limits:
            if "max_tasks" not in config:
                config["max_tasks"] = {}
            config["max_tasks"]["download"] = body.resource_limits.max_download_concurrency
            config["max_tasks"]["upload"] = body.resource_limits.max_upload_concurrency

        if body.proxy:
            if "proxy" not in config:
                config["proxy"] = {}
            proxy = body.proxy
            config["proxy"]["enable_proxy"] = proxy.enable_proxy
            if proxy.scheme:
                config["proxy"]["scheme"] = proxy.scheme
            if proxy.hostname:
                config["proxy"]["hostname"] = proxy.hostname
            if proxy.port:
                config["proxy"]["port"] = proxy.port
            if proxy.username:
                config["proxy"]["username"] = proxy.username
            if proxy.password:
                config["proxy"]["password"] = proxy.password

        # 保存配置
        if hasattr(config_manager, "save_config"):
            config_manager.save_config(config)

        return json_response(data={"message": "配置已更新"})
    except Exception as e:
        return json_response(
            data=None,
            message=f"更新配置失败: {str(e)}",
            status_code=500,
        )
