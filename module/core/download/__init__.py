# coding=UTF-8
"""下载/上传子系统。"""

from module.core.download.uploader import TelegramUploader
from module.core.download.client import TelegramRestrictedMediaDownloaderClient
from module.core.download.client_manager import ClientManager
from module.core.download.file_manager import FileManager, UploadProgress, FileInfo

# TelegramRestrictedMediaDownloader 延迟导入，避免循环依赖：
# download.__init__ → downloader → module.bot → bot.commands → task.executor → download.file_manager → download.__init__
def __getattr__(name):
    if name == "TelegramRestrictedMediaDownloader":
        from module.core.download.downloader import TelegramRestrictedMediaDownloader
        return TelegramRestrictedMediaDownloader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TelegramRestrictedMediaDownloader",
    "TelegramUploader",
    "TelegramRestrictedMediaDownloaderClient",
    "ClientManager",
    "FileManager",
    "UploadProgress",
    "FileInfo",
]
