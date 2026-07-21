# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
import sys
import threading

from module.utils.helpers import check_environ
from module.core.parser import PARSE_ARGS
from module.core.download.downloader import TelegramRestrictedMediaDownloader


def _run_web_api(port: int = 8000):
    """启动 FastAPI WebUI 服务。"""
    try:
        import uvicorn
        from module.api.app import create_app

        app = create_app()
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
            ws_ping_interval=None,
            ws_ping_timeout=None,
        )
    except ImportError:
        print("错误: 未安装 FastAPI 相关依赖。请运行: pip install fastapi uvicorn")
        sys.exit(1)


def _start_web_api_background(port: int = 8000):
    """在后台线程启动 Web API 服务。"""
    t = threading.Thread(target=_run_web_api, args=(port,), daemon=True)
    t.start()


if __name__ == "__main__":
    check_environ()

    # 确定 WebUI 端口（--port 优先，其次 --web PORT）
    web_port = PARSE_ARGS.port
    if web_port is None:
        web_port = (
            PARSE_ARGS.web
            if (PARSE_ARGS.web is not None and PARSE_ARGS.web > 0)
            else 8000
        )

    # 启动 Web API（后台线程）+ Telegram 客户端（主线程）
    _start_web_api_background(port=web_port)
    # RepositorySync / TaskExecutor 在 downloader.py 中延迟初始化
    # （需等待 Pyrogram Client 启动后才可创建）
    trmd = TelegramRestrictedMediaDownloader()
    trmd.run()
