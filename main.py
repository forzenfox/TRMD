# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
import os
import sys

from module.enums import ENVIRON, MODE
from module.utils.helpers import check_environ
from module.web import Web
from module.parser import PARSE_ARGS
from module.downloader import TelegramRestrictedMediaDownloader


def _run_web_api(port: int = 8000):
    """启动 FastAPI WebUI 服务。"""
    try:
        import uvicorn
        from module.api.app import create_app

        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=port)
    except ImportError:
        print("错误: 未安装 FastAPI 相关依赖。请运行: pip install fastapi uvicorn")
        sys.exit(1)


if __name__ == '__main__':
    check_environ()

    # 确定 WebUI 端口（--port 优先，其次 --web PORT）
    web_port = PARSE_ARGS.port
    if web_port is None:
        web_port = PARSE_ARGS.web if (PARSE_ARGS.web is not None and PARSE_ARGS.web > 0) else 8000

    # 仅启动 WebUI（不启动 Telegram 客户端）
    if PARSE_ARGS.web_only:
        _run_web_api(port=web_port)

    # 通过 --web 参数启动 FastAPI WebUI
    elif PARSE_ARGS.web is not None:
        _run_web_api(port=web_port)

    elif os.environ.get(ENVIRON.TRMD_WEB_PORT) and os.environ.get(ENVIRON.TRMD_WEB_PID) is None:
        # 原有 ttyd+tmux Web 模式
        web = Web(__file__)
        if PARSE_ARGS.mode == MODE.SESSION:
            web.run_session()
        else:
            web.run_once()
    else:
        # 核心下载器模式
        trmd = TelegramRestrictedMediaDownloader()
        trmd.run()
