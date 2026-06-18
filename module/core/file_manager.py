# coding=UTF-8
# FileManager 模块：核心文件管理层，为 Bot 与 WebUI 提供统一的本地文件操作能力。
import os
import hashlib
import mimetypes
import logging
from dataclasses import dataclass, field
from typing import Literal, Callable, Awaitable

from module import log
from module.path_tool import safe_delete

# ============================================================
# 常量定义
# ============================================================


class FileManagerConstants:
    """FileManager 模块常量。"""
    MAX_MEDIA_GROUP_SIZE: int = 10
    DEFAULT_MEMORY_LIMIT_MB: int = 512
    DEFAULT_DELETE_AFTER_UPLOAD: bool = False
    FORWARD_DELETE_AFTER_UPLOAD: bool = True

    SUPPORTED_ALBUM_TYPES: set = {'photo', 'video', 'audio'}
    UNSUPPORTED_ALBUM_TYPES: set = {'document', 'sticker', 'animation'}


# ============================================================
# 数据模型
# ============================================================


@dataclass
class FileInfo:
    """描述一个本地文件或目录的元数据。"""
    path: str                              # 绝对路径
    name: str                              # 文件/目录名
    is_directory: bool                     # 是否为目录
    size: int                              # 文件大小（字节），目录为 0
    mime_type: str | None                  # MIME 类型，目录为 None
    extension: str | None                  # 扩展名（小写，不含点），目录为 None
    modified_time: float                   # 最后修改时间戳
    sha256: str | None = None              # 文件 SHA256（上传前按需计算）
    is_selected: bool = False              # 是否被用户/WebUI 选中
    telegram_type: Literal[
        'photo', 'video', 'audio', 'voice',
        'document', 'animation', 'sticker', 'unsupported'
    ] | None = None                        # 按 Telegram 语义分类


@dataclass
class UploadResult:
    """描述一次上传任务的最终结果。"""
    success: bool                          # 是否成功
    file_path: str | None = None           # 本地文件路径
    message: object | None = None          # Pyrogram 返回的 Message 对象（成功时）
    error_code: str | None = None          # 错误码（失败时）
    error_msg: str | None = None           # 可读错误信息
    deleted: bool = False                  # 本地文件是否已清理


@dataclass
class MediaGroupConfig:
    """媒体组上传配置。"""
    max_group_size: int = 10               # 每组最大文件数，默认且最大为 10
    sort_by: str = 'name'                  # 排序字段：name / time / size / none
    sort_order: str = 'asc'                # 排序方向：asc / desc
    send_as_album: bool = True             # 是否尝试以媒体组发送
    fallback_to_single: bool = True        # 媒体组失败时是否降级为单文件发送


@dataclass
class UploadProgress:
    """上传进度回调数据结构。"""
    task_id: str                           # 任务/文件唯一标识
    file_path: str                         # 当前文件路径
    current: int                           # 当前已上传字节
    total: int                             # 文件总字节
    percentage: float                      # 上传百分比
    status: str                            # pending / uploading / success / failed


# ============================================================
# 异常体系
# ============================================================


class FileManagerError(Exception):
    """FileManager 基础异常类。"""
    def __init__(self, code: str, message: str, file_path: str | None = None):
        self.code = code
        self.message = message
        self.file_path = file_path
        super().__init__(message)


class FileNotFound(FileManagerError):
    """文件不存在异常。"""
    pass


class UploadSizeLimit(FileManagerError):
    """上传大小超限异常。"""
    pass


class MediaGroupInvalid(FileManagerError):
    """媒体组无效异常。"""
    pass


# ============================================================
# 核心类
# ============================================================


class FileManager:
    """核心文件管理器，提供文件浏览、选择、上传、清理等操作。"""

    # Windows 系统关键目录黑名单。
    _SYSTEM_PATH_BLACKLIST = (
        'C:\\Windows',
        'C:\\Program Files',
        'C:\\Program Files (x86)',
    )

    def __init__(
        self,
        config: dict,
        client: object,
        progress_callback: Callable[[UploadProgress], Awaitable[None]] | None = None,
    ):
        """
        初始化 FileManager。

        Args:
            config: 配置字典，至少包含 resource_limits.memory_limit_mb、
                    upload.max_group_size、upload.delete_after_upload 等键。
            client: 已授权的 Pyrogram Client 实例。
            progress_callback: 可选的全局上传进度回调。
        """
        self._config = config
        self._client = client
        self._progress_callback = progress_callback

        # 读取配置。
        resource_limits = config.get('resource_limits', {})
        self._memory_limit_mb = resource_limits.get('memory_limit_mb', FileManagerConstants.DEFAULT_MEMORY_LIMIT_MB)

        upload_config = config.get('upload', {})
        self._max_group_size = min(
            upload_config.get('max_group_size', FileManagerConstants.MAX_MEDIA_GROUP_SIZE),
            FileManagerConstants.MAX_MEDIA_GROUP_SIZE,
        )
        self._delete_after_upload = upload_config.get(
            'delete_after_upload', FileManagerConstants.DEFAULT_DELETE_AFTER_UPLOAD
        )

    # ---------- 文件浏览与选择 ----------

    async def list_files(
        self,
        path: str,
        recursive: bool = False,
        include_hidden: bool = False,
    ) -> list[FileInfo]:
        """列出指定路径下的文件与目录。"""
        abs_path = os.path.abspath(os.path.normpath(path))

        # 路径校验。
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f'路径不存在: {abs_path}')
        if not os.path.isdir(abs_path):
            raise NotADirectoryError(f'路径不是目录: {abs_path}')

        # 系统关键目录黑名单检查。
        self._check_system_path(abs_path)

        result: list[FileInfo] = []
        self._scan_directory(abs_path, recursive, include_hidden, result)
        return result

    def _scan_directory(
        self,
        directory: str,
        recursive: bool,
        include_hidden: bool,
        result: list[FileInfo],
    ) -> None:
        """递归扫描目录。"""
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    # 隐藏文件过滤。
                    if not include_hidden and self._is_hidden(entry.name):
                        continue

                    if entry.is_dir():
                        info = self._build_dir_info(entry.path, entry.name, entry.stat().st_mtime)
                        result.append(info)
                        if recursive:
                            self._scan_directory(entry.path, recursive, include_hidden, result)
                    elif entry.is_file():
                        info = self._build_file_info(entry.path, entry.name, entry.stat())
                        result.append(info)
        except PermissionError as e:
            log.warning(f'权限不足，无法扫描目录 "{directory}": {e}')

    async def get_file_info(self, path: str) -> FileInfo:
        """获取单个文件或目录的详细信息。"""
        abs_path = os.path.abspath(os.path.normpath(path))

        if not os.path.exists(abs_path):
            raise FileNotFoundError(f'路径不存在: {abs_path}')

        stat = os.stat(abs_path)

        if os.path.isdir(abs_path):
            return self._build_dir_info(abs_path, os.path.basename(abs_path), stat.st_mtime)
        else:
            return self._build_file_info(abs_path, os.path.basename(abs_path), stat)

    async def select_files(
        self,
        paths: list[str],
        allowed_extensions: list[str] | None = None,
    ) -> list[FileInfo]:
        """将一组路径转换为 FileInfo 列表，过滤不存在/不可读的文件。"""
        # 去重并保持顺序。
        seen = set()
        unique_paths = []
        for p in paths:
            abs_p = os.path.abspath(os.path.normpath(p))
            if abs_p not in seen:
                seen.add(abs_p)
                unique_paths.append(abs_p)

        result: list[FileInfo] = []
        for abs_path in unique_paths:
            if not os.path.exists(abs_path):
                log.warning(f'路径不存在，已跳过: {abs_path}')
                continue

            try:
                if os.path.isdir(abs_path):
                    # 目录递归收集其下所有非隐藏文件。
                    dir_files: list[FileInfo] = []
                    self._scan_directory(abs_path, recursive=False, include_hidden=False, result=dir_files)
                    # 只取文件，不取子目录。
                    files_only = [f for f in dir_files if not f.is_directory]
                    result.extend(files_only)
                else:
                    info = self._build_file_info(
                        abs_path, os.path.basename(abs_path), os.stat(abs_path)
                    )
                    result.append(info)
            except PermissionError as e:
                log.warning(f'权限不足，已跳过: {abs_path}, 原因: {e}')
                continue

        # 按扩展名过滤。
        if allowed_extensions:
            allowed_lower = {ext.lower() for ext in allowed_extensions}
            result = [f for f in result if f.extension and f'.{f.extension}'.lower() in allowed_lower]

        return result

    async def get_directory_size(self, path: str) -> int:
        """递归计算目录总大小（字节）。"""
        abs_path = os.path.abspath(os.path.normpath(path))
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return 0

        total_size = 0
        for dirpath, dirnames, filenames in os.walk(abs_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, PermissionError):
                    pass
        return total_size

    # ---------- 媒体组拆分 ----------

    async def split_media_group(
        self,
        file_infos: list[FileInfo],
        config: MediaGroupConfig | None = None,
    ) -> list[list[FileInfo]]:
        """将文件列表按类型拆分：媒体组（album_compatible）每 10 个一组，不支持的类型走单文件。

        返回格式为 list[dict]，每个 dict 包含：
            - 'is_album': bool - 是否为媒体组
            - 'files': list[FileInfo] - 文件列表
        """
        if not file_infos:
            return []

        if config is None:
            config = MediaGroupConfig()

        # 确保 max_group_size 不超过上限。
        max_size = min(config.max_group_size, FileManagerConstants.MAX_MEDIA_GROUP_SIZE)

        album_compatible, single_only = await self._classify_files(file_infos)

        groups: list[dict] = []

        # 媒体组文件按 max_size 切块。
        if config.send_as_album and album_compatible:
            for i in range(0, len(album_compatible), max_size):
                chunk = album_compatible[i:i + max_size]
                groups.append({'is_album': True, 'files': chunk})
        else:
            # 如果不以媒体组发送，全部走单文件。
            single_only.extend(album_compatible)

        # 不支持的文件走单文件。
        for f in single_only:
            groups.append({'is_album': False, 'files': [f]})

        return groups

    async def _classify_files(
        self,
        file_infos: list[FileInfo],
    ) -> tuple[list[FileInfo], list[FileInfo]]:
        """将文件列表分类为 album_compatible 和 single_only。"""
        album_compatible: list[FileInfo] = []
        single_only: list[FileInfo] = []

        for fi in file_infos:
            if fi.telegram_type in FileManagerConstants.SUPPORTED_ALBUM_TYPES:
                album_compatible.append(fi)
            else:
                single_only.append(fi)

        return album_compatible, single_only

    # ---------- 清理接口 ----------

    async def delete_local_file(self, file_path: str) -> bool:
        """安全删除本地文件或空目录，返回是否成功。"""
        abs_path = os.path.abspath(os.path.normpath(file_path))

        # 安全检查：不删除系统关键目录。
        self._check_system_path(abs_path)

        return safe_delete(abs_path)

    async def cleanup_after_upload(
        self,
        results: list[UploadResult],
        delete_after_upload: bool = True,
    ) -> list[UploadResult]:
        """根据策略批量清理已上传文件的本地副本。"""
        if not delete_after_upload:
            return results

        for res in results:
            if not res.success:
                continue
            if res.file_path and os.path.exists(res.file_path):
                res.deleted = await self.delete_local_file(res.file_path)
                if not res.deleted:
                    log.warning(f'上传后清理失败: {res.file_path}')
        return results

    # ---------- 上传进度回调 ----------

    async def _progress_wrapper(
        self,
        task_id: str,
        file_path: str,
        current: int,
        total: int,
        callback: Callable[[UploadProgress], Awaitable[None]] | None,
    ):
        """进度回调包装器。"""
        progress = UploadProgress(
            task_id=task_id,
            file_path=file_path,
            current=current,
            total=total,
            percentage=round(current / total * 100, 2) if total else 0,
            status='uploading',
        )

        if callback:
            await callback(progress)
        elif self._progress_callback:
            await self._progress_callback(progress)

    # ---------- 内部工具方法 ----------

    def _check_system_path(self, path: str) -> None:
        """检查路径是否在系统关键目录黑名单中。"""
        abs_path = os.path.abspath(os.path.normpath(path))
        normalized = abs_path.lower()
        for blacklist_path in self._SYSTEM_PATH_BLACKLIST:
            if normalized.startswith(blacklist_path.lower()):
                raise PermissionError(f'禁止操作系统关键目录: {abs_path}')

    @staticmethod
    def _is_hidden(name: str) -> bool:
        """判断文件或目录是否为隐藏。
        Windows 下通过 ctypes 检查文件属性，Linux/macOS 下检查是否以 '.' 开头。
        """
        if os.name == 'nt':
            # Windows: 使用 ctypes 检查 FILE_ATTRIBUTE_HIDDEN (0x2) 和 FILE_ATTRIBUTE_SYSTEM (0x4)。
            import ctypes
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(name)
                if attrs == -1:
                    return name.startswith('.')
                return bool(attrs & 0x6)  # HIDDEN | SYSTEM
            except Exception:
                return name.startswith('.')
        else:
            # Linux/macOS: 以 '.' 开头的文件视为隐藏。
            return name.startswith('.')

    def _build_file_info(self, path: str, name: str, stat_result: os.stat_result) -> FileInfo:
        """构建文件的 FileInfo。"""
        ext = os.path.splitext(name)[1].lstrip('.').lower() if '.' in name else None
        mime_type = self._guess_mime_type(name)
        telegram_type = self._classify_telegram_type(name, mime_type)

        return FileInfo(
            path=path,
            name=name,
            is_directory=False,
            size=stat_result.st_size,
            mime_type=mime_type,
            extension=ext,
            modified_time=stat_result.st_mtime,
            telegram_type=telegram_type,
        )

    @staticmethod
    def _build_dir_info(path: str, name: str, modified_time: float) -> FileInfo:
        """构建目录的 FileInfo。"""
        return FileInfo(
            path=path,
            name=name,
            is_directory=True,
            size=0,
            mime_type=None,
            extension=None,
            modified_time=modified_time,
        )

    @staticmethod
    def _guess_mime_type(name: str) -> str | None:
        """根据文件名猜测 MIME 类型。"""
        mime_type, _ = mimetypes.guess_type(name)
        return mime_type

    @staticmethod
    def _classify_telegram_type(name: str, mime_type: str | None) -> str | None:
        """根据文件名和 MIME 类型推导 Telegram 类型。"""
        ext = os.path.splitext(name)[1].lower() if '.' in name else ''

        # 图片类型。
        if mime_type and mime_type.startswith('image/'):
            if ext == '.gif':
                return 'animation'
            return 'photo'

        # 视频类型。
        if mime_type and mime_type.startswith('video/'):
            return 'video'

        # 音频类型。
        if mime_type and mime_type.startswith('audio/'):
            return 'audio'

        # 基于扩展名二次判断。
        photo_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.avif', '.heic', '.heif'}
        video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        audio_exts = {'.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus', '.wav'}
        animation_exts = {'.gif'}
        sticker_exts = {'.tgs', '.webm'}  # 动态贴纸。

        if ext in animation_exts:
            return 'animation'
        if ext in photo_exts:
            return 'photo'
        if ext in video_exts:
            return 'video'
        if ext in audio_exts:
            return 'audio'
        if ext in sticker_exts:
            return 'sticker'

        # 其他均视为 document。
        return 'document'
