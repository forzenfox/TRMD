# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/2 0:59
# File:enums.py
import os
import re
import sys
import time

from dataclasses import dataclass
from typing import Union, Optional, Callable, Any

from module import console, log
from module.language import _t


class LinkType:
    SINGLE: str = "single"
    GROUP: str = "group"
    COMMENT: str = "comment"
    TOPIC: str = "topic"


@dataclass
class Link:
    # https://github.com/tangyoha/telegram_media_downloader/blob/master/utils/format.py#L14
    group_id: Union[str, int, None] = None
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    topic_id: Optional[int] = None


class DownloadType:
    VIDEO: str = "video"
    PHOTO: str = "photo"
    DOCUMENT: str = "document"
    AUDIO: str = "audio"
    VOICE: str = "voice"
    ANIMATION: str = "animation"
    VIDEO_NOTE: str = "video_note"

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith("_") and not callable(value):  # 排除特殊方法和属性。
                yield value


class DownloadStatus:
    DOWNLOADING = "downloading"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIP = "skip"
    RETRY = "retry"


class UploadStatus:
    PENDING = "pending"
    UPLOADING = "uploading"
    SUCCESS = "success"
    FAILURE = "failure"
    SENT = "sent"


class MODE:
    SESSION: str = "SESSION"
    ONCE: str = "ONCE"


class CalenderKeyboard:
    START_TIME_BUTTON: str = "start time button"
    END_TIME_BUTTON: str = "end time button"


class SaveDirectoryPrefix:
    CHAT_ID: str = "%CHAT_ID%"
    CHAT_NAME: str = "%CHAT_NAME%"
    MIME_TYPE: str = "%MIME_TYPE%"

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith("_") and not callable(value):  # 排除特殊方法和属性。
                yield value


class WebMeta:
    IP: str = "IP"
    PORT: str = "port"
    USERNAME: str = "username"
    PASSWORD: str = "password"


class ENVIRON:
    TRMD_WEB_PID: str = "TRMD_WEB_PID"
    TRMD_WEB_PORT: str = "TRMD_WEB_PORT"
    PSMUX_SESSION_NAME: str = "PSMUX_SESSION_NAME"  # Windows专属。


class KeyWord:
    LINK: str = "link"
    LINK_TYPE: str = "link type"
    SIZE: str = "size"
    STATUS: str = "status"
    FILE: str = "file"
    ERROR_SIZE: str = "error size"
    ACTUAL_SIZE: str = "actual size"
    ALREADY_EXIST: str = "already exist"
    CHANNEL: str = "channel"
    MESSAGE_ID: str = "message id"
    TYPE: str = "type"
    RE_DOWNLOAD: str = "re-download"
    RE_UPLOAD: str = "re-upload"
    RETRY_TIMES: str = "retry times"
    CURRENT_DOWNLOAD_TASK: str = "current download task"
    CURRENT_UPLOAD_TASK: str = "current upload task"
    REASON: str = "reason"
    RESUME: str = "resume"
    DOWNLOAD_TASK: str = "download task"
    UPLOAD_TASK: str = "upload task"
    DOWNLOAD_AND_UPLOAD_TASK: str = "download and upload task"
    FORWARD_SUCCESS: str = "forward success"
    FORWARD_FAILURE: str = "forward failure"
    FORWARD_SKIP: str = "skip forward"
    UPLOAD_FILE_PART: str = "upload file part"


class Extension:
    PHOTO = {
        "image/avif": "avif",
        "image/bmp": "bmp",
        "image/gif": "gif",
        "image/ief": "ief",
        "image/jpg": "jpg",
        "image/jpeg": "jpeg",
        "image/heic": "heic",
        "image/heif": "heif",
        "image/png": "png",
        "image/svg+xml": "svg",
        "image/tiff": "tif",
        "image/vnd.microsoft.icon": "ico",
        "image/x-cmu-raster": "ras",
        "image/x-portable-anymap": "pnm",
        "image/x-portable-bitmap": "pbm",
        "image/x-portable-graymap": "pgm",
        "image/x-portable-pixmap": "ppm",
        "image/x-rgb": "rgb",
        "image/x-xbitmap": "xbm",
        "image/x-xpixmap": "xpm",
        "image/x-xwindowdump": "xwd",
    }
    VIDEO = {
        "video/mp4": "mp4",
        "video/mpeg": "mpg",
        "video/quicktime": "qt",
        "video/webm": "webm",
        "video/x-msvideo": "avi",
        "video/x-sgi-movie": "movie",
        "video/x-matroska": "mkv",
    }
    REVERSE_PHOTO = {
        "avif": "image/avif",
        "bmp": "image/bmp",
        "gif": "image/gif",
        "ief": "image/ief",
        "jpg": "image/jpg",
        "jpeg": "image/jpeg",
        "heic": "image/heic",
        "heif": "image/heif",
        "png": "image/png",
        "svg": "image/svg+xml",
        "tif": "image/tiff",
        "ico": "image/vnd.microsoft.icon",
        "ras": "image/x-cmu-raster",
        "pnm": "image/x-portable-anymap",
        "pbm": "image/x-portable-bitmap",
        "pgm": "image/x-portable-graymap",
        "ppm": "image/x-portable-pixmap",
        "rgb": "image/x-rgb",
        "xbm": "image/x-xbitmap",
        "xpm": "image/x-xpixmap",
        "xwd": "image/x-xwindowdump",
    }
    REVERSE_VIDEO = {
        "mp4": "video/mp4",
        "mpg": "video/mpeg",
        "qt": "video/quicktime",
        "webm": "video/webm",
        "avi": "video/x-msvideo",
        "movie": "video/x-sgi-movie",
        "mkv": "video/x-matroska",
    }
    ALL_REVERSE = {
        "avif": "image/avif",
        "bmp": "image/bmp",
        "gif": "image/gif",
        "ief": "image/ief",
        "jpg": "image/jpg",
        "jpeg": "image/jpeg",
        "heic": "image/heic",
        "heif": "image/heif",
        "png": "image/png",
        "svg": "image/svg+xml",
        "tif": "image/tiff",
        "ico": "image/vnd.microsoft.icon",
        "ras": "image/x-cmu-raster",
        "pnm": "image/x-portable-anymap",
        "pbm": "image/x-portable-bitmap",
        "pgm": "image/x-portable-graymap",
        "ppm": "image/x-portable-pixmap",
        "rgb": "image/x-rgb",
        "xbm": "image/x-xbitmap",
        "xpm": "image/x-xpixmap",
        "xwd": "image/x-xwindowdump",
        "video/mp4": "mp4",
        "video/mpeg": "mpg",
        "video/quicktime": "qt",
        "video/webm": "webm",
        "video/x-msvideo": "avi",
        "video/x-sgi-movie": "movie",
        "video/x-matroska": "mkv",
    }


class GradientColor:
    # 生成渐变色:https://photokit.com/colors/color-gradient/?lang=zh
    BLUE2PURPLE_14 = [
        "#0ebeff",
        "#21b4f9",
        "#33abf3",
        "#46a1ed",
        "#5898e8",
        "#6b8ee2",
        "#7d85dc",
        "#907bd6",
        "#a272d0",
        "#b568ca",
        "#c75fc5",
        "#da55bf",
        "#ec4cb9",
        "#ff42b3",
    ]
    GREEN2PINK_11 = [
        "#00ff40",
        "#14f54c",
        "#29eb58",
        "#3de064",
        "#52d670",
        "#66cc7c",
        "#7ac288",
        "#8fb894",
        "#a3ada0",
        "#b8a3ac",
        "#cc99b8",
    ]
    GREEN2BLUE_10 = [
        "#84fab0",
        "#85f6b8",
        "#86f1bf",
        "#88edc7",
        "#89e9ce",
        "#8ae4d6",
        "#8be0dd",
        "#8ddce5",
        "#8ed7ec",
        "#8fd3f4",
    ]
    YELLOW2GREEN_10 = [
        "#d4fc79",
        "#cdfa7d",
        "#c6f782",
        "#bff586",
        "#b8f28b",
        "#b2f08f",
        "#abed94",
        "#a4eb98",
        "#9de89d",
        "#96e6a1",
    ]
    ORANGE2YELLOW_15 = [
        "#f08a5d",
        "#f1915e",
        "#f1985f",
        "#f29f60",
        "#f3a660",
        "#f3ad61",
        "#f4b462",
        "#f5bc63",
        "#f5c364",
        "#f6ca65",
        "#f6d166",
        "#f7d866",
        "#f8df67",
        "#f8e668",
        "#f9ed69",
    ]
    NEW_LIFE = [
        "#43e97b",
        "#42eb85",
        "#41ed8f",
        "#3fee9a",
        "#3ef0a4",
        "#3df2ae",
        "#3cf4b8",
        "#3af5c3",
        "#39f7cd",
        "#38f9d7",
    ]
    RED_GRADIENT_15 = [
        "#ff0000",
        "#ff0011",
        "#ff0021",
        "#ff0032",
        "#ff0043",
        "#ff0053",
        "#ff0064",
        "#ff0075",
        "#ff0085",
        "#ff0096",
        "#ff1a9e",
        "#ff33a6",
        "#ff4db0",
        "#ff66b8",
        "#ff80c2",
    ]

    @staticmethod
    def __extend_gradient_colors(colors: list, target_length: int) -> list:
        extended_colors = colors[:]
        while len(extended_colors) < target_length:
            # 添加原列表（除最后一个元素外）的逆序
            extended_colors.extend(colors[-2::-1])
            # 如果仍然不够长，继续添加正序部分
            if len(extended_colors) < target_length:
                extended_colors.extend(colors[:-1])
        return extended_colors[:target_length]

    @staticmethod
    def gen_gradient_text(text: str, gradient_color: list) -> str:
        """当渐变色列表小于文字长度时,翻转并扩展当前列表。"""
        text_lst: list = [i for i in text]
        text_lst_len: int = len(text_lst)
        gradient_color_len: int = len(gradient_color)
        if text_lst_len > gradient_color_len:
            # 扩展颜色列表以适应文本长度
            gradient_color = GradientColor.__extend_gradient_colors(
                gradient_color, text_lst_len
            )
        result: str = ""
        for i in range(text_lst_len):
            result += f"[{gradient_color[i]}]{text_lst[i]}[/{gradient_color[i]}]"
        return result

    @staticmethod
    def __hex_to_rgb(hex_color: str) -> tuple:
        """将十六进制颜色值转换为RGB元组。"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def __rgb_to_hex(r: int, g: int, b: int) -> str:
        """将RGB元组转换为十六进制颜色值。"""
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def generate_gradient(start_color: str, end_color: str, steps: int) -> list:
        """根据起始和结束颜色生成颜色渐变列表。"""
        steps = 2 if steps <= 1 else steps
        # 转换起始和结束颜色为RGB
        start_rgb = GradientColor.__hex_to_rgb(start_color)
        end_rgb = GradientColor.__hex_to_rgb(end_color)
        # 生成渐变色列表
        gradient_color: list = []
        for i in range(steps):
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * i / (steps - 1))
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * i / (steps - 1))
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * i / (steps - 1))
            gradient_color.append(GradientColor.__rgb_to_hex(r, g, b))

        return gradient_color


class Banner:
    A = r"""
       ______           __  __                     _ __          
      / ____/__  ____  / /_/ /__  _________  _____(_) /____      
     / / __/ _ \/ __ \/ __/ / _ \/ ___/ __ \/ ___/ / __/ _ \     
    / /_/ /  __/ / / / /_/ /  __(__  ) /_/ / /  / / /_/  __/     
    \____/\___/_/ /_/\__/_/\___/____/ .___/_/  /_/\__/\___/      
                                   /_/                           
        """
    B = r"""
    ╔═╗┌─┐┌┐┌┌┬┐┬  ┌─┐┌─┐┌─┐┬─┐┬┌┬┐┌─┐  
    ║ ╦├┤ │││ │ │  ├┤ └─┐├─┘├┬┘│ │ ├┤   
    ╚═╝└─┘┘└┘ ┴ ┴─┘└─┘└─┘┴  ┴└─┴ ┴ └─┘  
        """
    C = r"""
     ██████╗ ███████╗███╗   ██╗████████╗██╗     ███████╗███████╗██████╗ ██████╗ ██╗████████╗███████╗    
    ██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║     ██╔════╝██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝██╔════╝    
    ██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     █████╗  ███████╗██████╔╝██████╔╝██║   ██║   █████╗      
    ██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██╔══╝  ╚════██║██╔═══╝ ██╔══██╗██║   ██║   ██╔══╝      
    ╚██████╔╝███████╗██║ ╚████║   ██║   ███████╗███████╗███████║██║     ██║  ██║██║   ██║   ███████╗    
     ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝           
            """
    D = r'''                                                                          
                                            ,,                                       ,,                    
      .g8"""bgd                      mm   `7MM                                       db   mm               
    .dP'     `M                      MM     MM                                            MM               
    dM'       `   .gP"Ya `7MMpMMMb.mmMMmm   MM  .gP"Ya  ,pP"Ybd `7MMpdMAo.`7Mb,od8 `7MM mmMMmm .gP"Ya      
    MM           ,M'   Yb  MM    MM  MM     MM ,M'   Yb 8I   `"   MM   `Wb  MM' "'   MM   MM  ,M'   Yb     
    MM.    `7MMF'8M""""""  MM    MM  MM     MM 8M"""""" `YMMMa.   MM    M8  MM       MM   MM  8M""""""     
    `Mb.     MM  YM.    ,  MM    MM  MM     MM YM.    , L.   I8   MM   ,AP  MM       MM   MM  YM.    ,     
      `"bmmmdPY   `Mbmmd'.JMML  JMML.`Mbmo.JMML.`Mbmmd' M9mmmP'   MMbmmd' .JMML.   .JMML. `Mbmo`Mbmmd'     
                                                                  MM                                       
                                                                .JMML.                                     
        '''
    TRMD = r"""
    ████████╗██████╗ ███╗   ███╗██████╗ 
    ╚══██╔══╝██╔══██╗████╗ ████║██╔══██╗
       ██║   ██████╔╝██╔████╔██║██║  ██║
       ██║   ██╔══██╗██║╚██╔╝██║██║  ██║
       ██║   ██║  ██║██║ ╚═╝ ██║██████╔╝
       ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝
    """


class BotCommandText:
    HELP: tuple = ("help", "展示可用命令。")
    DOWNLOAD: tuple = (
        "download",
        "分配新的下载任务(多种使用方式见使用说明)。\n`/download https://t.me/x/x 起始ID 结束ID`",
    )
    TABLE: tuple = ("table", "在终端输出当前下载情况的统计信息。")
    FORWARD: tuple = (
        "forward",
        "从频道A转发至频道B 起始ID 结束ID。\n`/forward https://t.me/A https://t.me/B 1 100`",
    )
    EXIT: tuple = ("exit", "退出软件。")
    LISTEN_DOWNLOAD: tuple = (
        "listen_download",
        "实时监听该链接的最新消息(视频和图片)进行下载。\n`/listen_download https://t.me/A https://t.me/B https://t.me/n`",
    )
    LISTEN_FORWARD: tuple = (
        "listen_forward",
        "实时监听该链接的最新消息(任意消息)进行转发。\n`/listen_forward 监听频道 转发频道`",
    )
    LISTEN_INFO: tuple = ("listen_info", "查看当前已经创建的监听信息。")
    UPLOAD: tuple = ("upload", "上传本地的文件到指定频道。`/upload 本地文件 目标频道`")
    UPLOAD_R: tuple = (
        "upload_r",
        "递归上传文件夹(包含子文件夹)到指定频道。`/upload_r 本地文件夹 目标频道`",
    )
    DOWNLOAD_CHAT: tuple = (
        "download_chat",
        "下载指定频道并支持通过内联键盘自定义内容过滤。`/download_chat 频道链接`",
    )

    @staticmethod
    def with_description(text: tuple) -> str:
        return f"/{text[0]} - {text[1]}"


class BotCallbackText:
    NULL: str = "null"
    LINK_TABLE: str = "link_table"
    COUNT_TABLE: str = "count_table"
    UPLOAD_TABLE: str = "upload_table"
    BACK_HELP: str = "back_help"
    BACK_TABLE: str = "back_table"
    NOTICE: str = "notice"
    DOWNLOAD: str = "download"
    DOWNLOAD_UPLOAD: str = "download_upload"
    REMOVE_LISTEN_DOWNLOAD: str = "rld"
    REMOVE_LISTEN_FORWARD: str = "rlf"
    LOOKUP_LISTEN_INFO: str = "lookup_listen_info"
    EXPORT_LINK_TABLE: str = "export_link_table"
    EXPORT_COUNT_TABLE: str = "export_count_table"
    EXPORT_UPLOAD_TABLE: str = "export_upload_table"
    TOGGLE_LINK_TABLE: str = "toggle_link_table"
    TOGGLE_COUNT_TABLE: str = "toggle_count_table"
    TOGGLE_UPLOAD_TABLE: str = "toggle_upload_table"
    TOGGLE_FORWARD_VIDEO: str = "toggle_forward_video"
    TOGGLE_FORWARD_PHOTO: str = "toggle_forward_photo"
    TOGGLE_FORWARD_AUDIO: str = "toggle_forward_audio"
    TOGGLE_FORWARD_VOICE: str = "toggle_forward_voice"
    TOGGLE_FORWARD_ANIMATION: str = "toggle_forward_animation"
    TOGGLE_FORWARD_DOCUMENT: str = "toggle_forward_document"
    TOGGLE_FORWARD_TEXT: str = "toggle_forward_text"
    TOGGLE_FORWARD_VIDEO_NOTE: str = "toggle_forward_video_note"
    TOGGLE_DOWNLOAD_VIDEO: str = "toggle_download_video"
    TOGGLE_DOWNLOAD_PHOTO: str = "toggle_download_photo"
    TOGGLE_DOWNLOAD_AUDIO: str = "toggle_download_audio"
    TOGGLE_DOWNLOAD_VOICE: str = "toggle_download_voice"
    TOGGLE_DOWNLOAD_ANIMATION: str = "toggle_download_animation"
    TOGGLE_DOWNLOAD_DOCUMENT: str = "toggle_download_document"
    TOGGLE_DOWNLOAD_VIDEO_NOTE: str = "toggle_download_video_note"
    EXPORT_TABLE: str = "export_table"
    SHUTDOWN: str = "shutdown"
    SETTING: str = "setting"
    UPLOAD_SETTING: str = "upload_setting"
    DOWNLOAD_SETTING: str = "download_setting"
    FORWARD_SETTING: str = "forward_setting"
    UPLOAD_DOWNLOAD: str = "upload_download"
    UPLOAD_DOWNLOAD_DELETE: str = "upload_download_delete"
    DOWNLOAD_CHAT_ID: str = "download_chat_id"
    DOWNLOAD_CHAT_ID_CANCEL: str = "download_chat_id_cancel"
    DOWNLOAD_CHAT_FILTER: str = "download_chat_filter"
    DOWNLOAD_CHAT_DATE_FILTER: str = "download_chat_date_filter"
    DOWNLOAD_CHAT_DTYPE_FILTER: str = "download_chat_dtype_filter"
    DOWNLOAD_CHAT_KEYWORD_FILTER: str = "download_chat_keyword_filter"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO: str = "toggle_download_chat_video"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO: str = "toggle_download_chat_photo"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO: str = "toggle_download_chat_audio"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE: str = "toggle_download_chat_voice"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION: str = "toggle_download_chat_animation"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT: str = "toggle_download_chat_document"
    TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE: str = "toggle_download_chat_video_note"
    TOGGLE_DOWNLOAD_CHAT_COMMENT: str = "toggle_download_chat_comment"
    CALENDAR_CONFIRM: str = "calendar_confirm"
    FILTER_START_DATE: str = "filter_start_date"
    FILTER_END_DATE: str = "filter_end_date"
    DROP_KEYWORD: str = "drop_keyword"
    IGNORE_KEYWORD: str = "ignore_keyword"
    CONFIRM_KEYWORD: str = "confirm_keyword"
    CANCEL_KEYWORD_INPUT: str = "cancel_keyword_input"

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith("__") and not callable(value):  # 排除特殊方法和属性。
                yield value


class BotMessage:
    RIGHT: str = "✅以下链接已创建下载任务:\n"
    EXIST: str = "⚠️以下链接已存在已被移除:\n"
    INVALID: str = "🚫以下链接不合法已被移除:\n"


class BotButton:
    GITHUB: str = "📦GitHub"
    SUBSCRIBE_CHANNEL: str = "📌订阅频道"
    VIDEO_TUTORIAL: str = "🎬视频教程"
    OPEN_NOTICE: str = "📢启用通知"
    CLOSE_NOTICE: str = "🔕禁用通知"
    LINK_TABLE: str = "🔗链接统计表"
    COUNT_TABLE: str = "➕计数统计表"
    UPLOAD_TABLE: str = "📤上传统计表"
    HELP_PAGE: str = "🛎️帮助页面"
    CLICK_VIEW: str = "🖱点击查看"
    CLICK_DOWNLOAD: str = "🖱点击下载"
    DOWNLOAD: str = "⬇️下载"
    DOWNLOAD_UPLOAD: str = "↕️下载后上传"
    TASK_ASSIGN: str = "🌟任务已分配"
    RETRIEVE_MESSAGE: str = "🔎检索消息中"
    RETRIEVE_COMMENT: str = "🔎检索评论区中"
    ASSIGNING_TASK: str = "🚛分配任务中"
    TASK_CANCEL: str = "🗑️任务已取消"
    EXECUTE_TASK: str = "▶️执行任务"
    CANCEL_TASK: str = "⏹️取消任务"
    OK: str = "✅确定"
    CANCEL: str = "❌取消"
    DROP: str = "🗑️移除"
    IGNORE: str = "👁️‍🗨️忽略"
    RETURN: str = "🔙返回"
    CONFIRM_AND_RETURN: str = "↩️确定并返回"
    LOOKUP_LISTEN_INFO: str = "🔍查看监听信息"
    EXPORT_TABLE: str = "📊导出表格"
    RESELECT: str = "🔄重新选择"
    SETTING: str = "⚙️设置"
    OPEN_LINK_TABLE: str = "🔓启用导出链接表格"
    CLOSE_LINK_TABLE: str = "🔒禁用导出链接表格"
    OPEN_COUNT_TABLE: str = "🔓启用导出计数表格"
    CLOSE_COUNT_TABLE: str = "🔒禁用导出计数表格"
    OPEN_UPLOAD_TABLE: str = "🔓启用导出上传表格"
    CLOSE_UPLOAD_TABLE: str = "🔒禁用导出上传表格"
    OPEN_EXIT_SHUTDOWN: str = "✅启用退出后关机"
    CLOSE_EXIT_SHUTDOWN: str = "❌禁用退出后关机"
    ALREADY_REMOVE: str = "✅已移除"
    UPLOAD_SETTING: str = "📤上传设置"
    DOWNLOAD_SETTING: str = "📥下载设置"
    FORWARD_SETTING: str = "↗️转发设置"
    OPEN_UPLOAD_DOWNLOAD: str = "🔓启用下载后上传"
    CLOSE_UPLOAD_DOWNLOAD: str = "🔒禁用下载后上传"
    OPEN_UPLOAD_DOWNLOAD_DELETE: str = "🔓启用下载后上传并删除"
    CLOSE_UPLOAD_DOWNLOAD_DELETE: str = "🔒禁用下载后上传并删除"
    VIDEO_ON: str = "🎬视频 ✅"
    PHOTO_ON: str = "🖼️图片 ✅"
    AUDIO_ON: str = "🎵音频 ✅"
    VOICE_ON: str = "🎤语音 ✅"
    ANIMATION_ON: str = "🎨GIF ✅"
    DOCUMENT_ON: str = "📄文档 ✅"
    TEXT_ON: str = "💬文本消息 ✅"
    VIDEO_NOTE_ON: str = "📹视频笔记 ✅"
    VIDEO_OFF: str = "🎬视频 ❌"
    PHOTO_OFF: str = "🖼️图片 ❌"
    AUDIO_OFF: str = "🎵音频 ❌"
    VOICE_OFF: str = "🎤语音 ❌"
    ANIMATION_OFF: str = "🎨GIF ❌"
    DOCUMENT_OFF: str = "📄文档 ❌"
    TEXT_OFF: str = "💬文本消息 ❌"
    VIDEO_NOTE_OFF: str = "📹视频笔记 ❌"
    DATE_RANGE_SETTING: str = "📅设置日期范围"
    SELECT_START_DATE: str = "⏮️选择起始日期"
    SELECT_END_DATE: str = "⏭️选择结束日期"
    INPUT_KEYWORD: str = "⌨️请向我发送关键词"
    DOWNLOAD_DTYPE_SETTING: str = "📝设置下载类型"
    KEYWORD_FILTER_SETTING: str = "🔑设置匹配关键词"
    CONFIRM_KEYWORD: str = "✅确认关键词"
    INCLUDE_COMMENT: str = "✅包含评论区"
    IGNORE_COMMENT: str = "❌包含评论区"
