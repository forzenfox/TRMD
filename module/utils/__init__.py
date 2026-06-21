# coding=UTF-8
"""
Utility modules for Telegram Restricted Media Downloader.
This package contains helper functions and classes for path handling,
standard I/O operations, filtering, and general utilities.
"""

from module.utils.path_tool import (
    split_path,
    validate_title,
    truncate_filename,
    gen_backup_config,
    safe_delete,
    safe_scan_directory_file,
    safe_replace,
    move_to_save_directory,
    get_extension,
    get_file_size,
    get_mime_from_extension,
    extract_full_extension,
    is_compressed_file,
    calc_sha256,
    is_file_duplicate,
    compare_file_size,
)

from module.utils.helpers import (
    safe_index,
    get_terminal_width,
    truncate_display_filename,
    safe_message,
    safe_delete_message,
    parse_link,
    extract_info_from_link,
    get_message_by_link,
    get_chat_with_notify,
    get_valid_chat_id,
    is_allow_upload,
    format_chat_link,
    get_my_id,
    add_executable_permission,
    get_subprocess_args,
    gen_random_credential,
    check_environ,
    is_nuitka,
    is_docker,
    Issues,
)

from module.utils.stdio import (
    StatisticalTable,
    PanelTable,
    QrcodeRender,
    MetaData,
    Base64Image,
    ProgressBar,
)

from module.utils.filter import Filter

__all__ = [
    # path_tool exports
    "split_path",
    "validate_title",
    "truncate_filename",
    "gen_backup_config",
    "safe_delete",
    "safe_scan_directory_file",
    "safe_replace",
    "move_to_save_directory",
    "get_extension",
    "get_file_size",
    "get_mime_from_extension",
    "extract_full_extension",
    "is_compressed_file",
    "calc_sha256",
    "is_file_duplicate",
    "compare_file_size",
    # helpers exports
    "safe_index",
    "get_terminal_width",
    "truncate_display_filename",
    "safe_message",
    "safe_delete_message",
    "parse_link",
    "extract_info_from_link",
    "get_message_by_link",
    "get_chat_with_notify",
    "get_valid_chat_id",
    "is_allow_upload",
    "format_chat_link",
    "get_my_id",
    "add_executable_permission",
    "get_subprocess_args",
    "gen_random_credential",
    "check_environ",
    "is_nuitka",
    "is_docker",
    "Issues",
    # stdio exports
    "StatisticalTable",
    "PanelTable",
    "QrcodeRender",
    "MetaData",
    "Base64Image",
    "ProgressBar",
    # filter exports
    "Filter",
]
