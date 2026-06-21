# coding=UTF-8
"""统一异常类与异常处理器。

定义业务异常类型，并注册全局异常处理器以统一返回格式。
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ==================== 业务异常 ====================


class TRMDAPIException(Exception):
    """Web API 业务异常基类。"""

    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TaskNotFoundError(TRMDAPIException):
    """任务未找到。"""

    def __init__(self, task_id: str = ""):
        super().__init__(
            code=404,
            message=f"任务不存在: {task_id}" if task_id else "任务不存在",
            status_code=404,
        )


class TaskSizeExceeded(TRMDAPIException):
    """任务大小超过上限。"""

    def __init__(self, size_human: str = ""):
        msg = f"任务大小超过 10GB 上限{f' ({size_human})' if size_human else ''}"
        super().__init__(code=1001, message=msg, status_code=400)


class TaskSizeWarning(TRMDAPIException):
    """任务大小超过告警阈值。"""

    def __init__(self, size_human: str = ""):
        msg = f"任务大小{f' {size_human}' if size_human else ''}超过 5GB，请确认"
        super().__init__(code=1002, message=msg, status_code=400)


class InsufficientDiskSpace(TRMDAPIException):
    """磁盘空间不足。"""

    def __init__(self):
        super().__init__(code=1003, message="磁盘空间不足", status_code=400)


class TaskConflictError(TRMDAPIException):
    """任务状态冲突。"""

    def __init__(self, message: str = "任务状态冲突"):
        super().__init__(code=409, message=message, status_code=409)


class ChatNotFoundError(TRMDAPIException):
    """频道未找到。"""

    def __init__(self, chat_id: str = ""):
        super().__init__(
            code=404,
            message=f"频道不存在: {chat_id}" if chat_id else "频道不存在",
            status_code=404,
        )


# ==================== 异常处理器 ====================


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。

    :param app: FastAPI 应用实例
    """

    @app.exception_handler(TRMDAPIException)
    async def trmd_exception_handler(
        request: Request, exc: TRMDAPIException
    ) -> JSONResponse:
        """处理业务异常。"""
        logger.warning("业务异常 [%d]: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    # 处理核心模块 TaskNotFoundError
    from module.core.task_manager import TaskNotFoundError as CoreTaskNotFoundError

    @app.exception_handler(CoreTaskNotFoundError)
    async def core_task_not_found_handler(
        request: Request, exc: CoreTaskNotFoundError
    ) -> JSONResponse:
        """处理核心模块任务未找到异常。"""
        return JSONResponse(
            status_code=404,
            content={"code": 404, "message": str(exc), "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理请求参数校验失败。"""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": 422,
                "message": "请求参数校验失败",
                "data": {"detail": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """处理未知内部错误，不暴露 Traceback。"""
        logger.exception("内部错误: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": 500,
                "message": "服务器内部错误",
                "data": None,
            },
        )
