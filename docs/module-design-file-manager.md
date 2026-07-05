# FileManager 模块设计文档

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **文档版本**: v1.2
> **创建日期**: 2026-06-18
> **更新日期**: 2026-07-03
> **状态**: 已更新设计（待实现 v1.2 扩展）
> **关联文档**: [interaction-enhancement-design.md](./interaction-enhancement-design.md)、[private-chat-download-by-username-prd.md](./private-chat-download-by-username-prd.md)

---

## 变更记录

| 版本 | 日期 | 变更内容 | 状态 |
|------|------|----------|------|
| v1.2 | 2026-07-03 | 新增下载任务仓库备份集成（DOWNLOAD / LISTEN_DOWNLOAD）；强化 `source_chat_id` / `source_message_id` 来源追踪语义；补充私聊消息无公开 `source_link` 的说明 | 已更新设计（待实现） |
| v1.1 | 2026-06-21 | 初始实现：文件浏览、上传、媒体组拆分、仓库模式回调 | 已实现 |

---

## 1. 设计目标与职责边界

### 1.1 设计目标

FileManager 是 Bot 与 WebUI 共享的**核心文件管理层**，目标是为上层提供统一、安全、可观测的本地文件操作能力：

| 目标 | 说明 |
|------|------|
| **统一抽象** | 将文件浏览、选择、信息获取、上传、清理等操作收敛到单一模块，避免 Bot 与 WebUI 重复实现。 |
| **向后兼容** | 不破坏现有 `/upload`、`/upload_r` 命令及 `TelegramUploader` 的工作流程；新能力以扩展接口形式提供。 |
| **资源保护** | 单文件内存缓存上限 512MB，流式处理大文件；转发任务默认上传后删除本地文件。 |
| **Telegram 限制适配** | 媒体组上传自动遵守「最多 10 个文件、不支持 document/贴纸/GIF」的限制。 |
| **下载任务仓库备份** | 为 `DOWNLOAD` / `LISTEN_DOWNLOAD` 任务提供可选的自动仓库备份能力。 |
| **可测试性** | 所有 IO 与 Telegram 交互均可注入 Mock，便于 TDD 与单元测试。 |

### 1.2 职责边界

```
┌──────────────────────────────────────────────────────────────────────┐
│                           调用方层                                    │
│  ┌───────────────┐        ┌─────────────────────┐                   │
│  │ Telegram Bot  │        │ WebUI API / WebSocket │                   │
│  │ (轻量命令入口)│        │   (可视化文件管理)    │                   │
│  └───────┬───────┘        └──────────┬──────────┘                   │
└──────────┼───────────────────────────┼───────────────────────────────┘
           │                           │
           ▼                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         FileManager（本模块）                         │
│  - 文件浏览 / 选择 / 信息获取                                         │
│  - 单文件上传                                                         │
│  - 媒体组拆分与上传                                                   │
│  - 上传进度回调                                                       │
│  - 本地文件清理                                                       │
│  - 仓库模式回调（上传成功后通知 RepositoryManager）                    │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    TelegramClient / Pyrogram                          │
│  - send_media_group / send_video / send_photo / send_document         │
│  - save_file / UploadMedia                                            │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│               RepositoryManager（仓库模式，外部模块）                   │
│  - on_upload_success(): 上传成功后提取媒体信息，写入仓库数据库          │
│  - check_dedup(): 三级去重（来源 → file_unique_id → 内容哈希）        │
│  - distribute_to_target(): copy_message → file_id_send → 重新下载     │
│  - compute_content_hash(): SHA256 内容哈希计算                        │
└──────────────────────────────────────────────────────────────────────┘
```

**FileManager 不做的事：**

- 不直接处理 Telegram 登录与会话管理（由 `client.py` 负责）。
- 不参与任务队列调度（由 `TaskManager` 负责）。
- 不处理频道链接解析、消息范围选择（由现有 parser / downloader 负责）。
- 不持久化任务状态（由 `TaskManager` + SQLite 负责）。
- 不直接操作仓库数据库（由 `RepositoryManager` + `RepositoryDB` 负责）。
- 不执行仓库分发逻辑（copy_message / file_id_send 等由 `RepositoryManager` 编排）。

---

## 2. 数据模型

### 2.1 FileInfo

描述一个本地文件或目录的元数据，用于文件浏览、选择与上传预览。

```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class FileInfo:
    path: str                              # 绝对路径
    name: str                              # 文件/目录名
    is_directory: bool                     # 是否为目录
    size: int                              # 文件大小（字节），目录为 0 或递归大小
    mime_type: str | None                  # MIME 类型，目录为 None
    extension: str | None                  # 扩展名（小写，不含点），目录为 None
    modified_time: float                   # 最后修改时间戳
    sha256: str | None = None              # 文件 SHA256（上传前按需计算）
    is_selected: bool = False              # 是否被用户/WebUI 选中
    telegram_type: Literal[
        'photo', 'video', 'audio', 'voice',
        'document', 'animation', 'sticker', 'unsupported'
    ] | None = None                        # 按 Telegram 语义分类，用于媒体组拆分
```

**字段说明：**

- `telegram_type` 由 `mime_type` + 扩展名推导，作为媒体组拆分的核心判断依据。
- `sha256` 在上传前懒加载，用于断点续传与去重。
- `size` 对目录默认返回 `0`；如上层需要递归统计，应调用 `FileManager.get_directory_size()`。

### 2.2 UploadResult

描述一次上传任务的最终结果，单文件与媒体组均使用。

```python
from dataclasses import dataclass
from typing import Any


@dataclass
class UploadResult:
    success: bool                          # 是否成功
    file_path: str | None                  # 本地文件路径
    message: Any | None                    # Pyrogram 返回的 Message 对象（成功时）
    error_code: str | None                 # 错误码（失败时）
    error_msg: str | None                  # 可读错误信息
    deleted: bool = False                  # 本地文件是否已清理
    file_unique_id: str | None = None      # 文件唯一标识（从 Pyrogram Message 提取，用于仓库去重）
```

### 2.3 MediaGroupConfig

媒体组上传配置，由上层（WebUI 或 Bot）传入。

```python
from dataclasses import dataclass


@dataclass
class MediaGroupConfig:
    max_group_size: int = 10               # 每组最大文件数，默认且最大为 10
    sort_by: str = 'name'                  # 排序字段：name / time / size / none
    sort_order: str = 'asc'                # 排序方向：asc / desc
    send_as_album: bool = True             # 是否尝试以媒体组发送
    fallback_to_single: bool = True        # 媒体组失败时是否降级为单文件发送
```

**约束：**

- `max_group_size` 必须 ≤ 10，超过时强制截断为 10 并记录警告。
- 当 `send_as_album=False` 时，所有文件均走单文件上传路径。

### 2.4 UploadProgress

上传进度回调数据结构。

```python
from dataclasses import dataclass


@dataclass
class UploadProgress:
    task_id: str                           # 任务/文件唯一标识
    file_path: str                         # 当前文件路径
    current: int                           # 当前已上传字节
    total: int                             # 文件总字节
    percentage: float                      # 上传百分比
    status: str                            # pending / uploading / success / failed
```

---

## 3. 接口契约

### 3.1 FileManager 公共方法

```python
from typing import Callable, Awaitable, Any
from dataclasses import dataclass


class FileManager:
    def __init__(
        self,
        config: dict,
        client: pyrogram.Client,
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
        self.repository_manager = None      # 外部注入的 RepositoryManager 实例（仓库模式）

    @staticmethod
    def _extract_file_unique_id(message: Any) -> str | None:
        """从 Pyrogram Message 对象中提取 file_unique_id。

        按优先级依次检查 video / photo / document / audio / animation / voice / sticker，
        返回第一个非空的 file_unique_id，均无则返回 None。
        """

    # ---------- 文件浏览与选择 ----------

    async def list_files(
        self,
        path: str,
        recursive: bool = False,
        include_hidden: bool = False,
    ) -> list[FileInfo]:
        """列出指定路径下的文件与目录。"""

    async def get_file_info(self, path: str) -> FileInfo:
        """获取单个文件或目录的详细信息。"""

    async def select_files(
        self,
        paths: list[str],
        allowed_extensions: list[str] | None = None,
    ) -> list[FileInfo]:
        """将一组路径转换为 FileInfo 列表，过滤不存在/不可读的文件。"""

    async def get_directory_size(self, path: str) -> int:
        """递归计算目录总大小（字节）。"""

    # ---------- 上传接口 ----------

    async def upload_single(
        self,
        chat_id: int | str,
        file_path: str,
        caption: str | None = None,
        progress_callback: Callable[[UploadProgress], Awaitable[None]] | None = None,
        delete_after_upload: bool | None = None,
        source_chat_id: int | str | None = None,
        source_message_id: int | None = None,
    ) -> UploadResult:
        """上传单个本地文件到指定聊天。

        Args:
            source_chat_id: 来源对话 ID（仓库模式下用于记录来源）。
                            频道与私聊来源均需提供；私聊消息无公开 source_link，
                            因此 source_chat_id + source_message_id 是仓库映射的主要来源标识。
            source_message_id: 来源消息 ID（仓库模式下用于记录来源）。
                               与 source_chat_id 共同构成来源追踪键，私聊场景下尤为重要。
        """

    async def upload_media_group(
        self,
        chat_id: int | str,
        file_paths: list[str],
        config: MediaGroupConfig | None = None,
        caption: str | None = None,
        progress_callback: Callable[[UploadProgress], Awaitable[None]] | None = None,
        delete_after_upload: bool | None = None,
        source_chat_id: int | str | None = None,
        source_message_id: int | None = None,
    ) -> list[UploadResult]:
        """将多个本地文件以媒体组形式上传，自动拆分与降级。

        Args:
            source_chat_id: 来源对话 ID（仓库模式下用于记录来源）。
                            频道与私聊来源均需提供；私聊消息无公开 source_link，
                            因此 source_chat_id + source_message_id 是仓库映射的主要来源标识。
            source_message_id: 来源消息 ID（仓库模式下用于记录来源）。
                               与 source_chat_id 共同构成来源追踪键，私聊场景下尤为重要。
        """

    # ---------- 清理接口 ----------

    async def delete_local_file(self, file_path: str) -> bool:
        """安全删除本地文件或空目录，返回是否成功。"""

    async def cleanup_after_upload(
        self,
        results: list[UploadResult],
        delete_after_upload: bool = True,
    ) -> list[UploadResult]:
        """根据策略批量清理已上传文件的本地副本。"""
```

### 3.2 构造参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config` | `dict` | 是 | 包含资源限制、上传策略等配置。 |
| `client` | `pyrogram.Client` | 是 | 已启动的 Telegram 客户端。 |
| `progress_callback` | `Callable | None` | 否 | 全局进度回调，可被单次上传的同名参数覆盖。 |
| `repository_manager` | `RepositoryManager | None` | 否 | 外部注入的仓库管理器实例，启用仓库模式后由上层设置。 |

### 3.3 返回值约定

- `list_files` / `select_files` 返回按 `sort_by` 排序后的 `FileInfo` 列表。
- `upload_single` 返回单个 `UploadResult`。
- `upload_media_group` 返回与输入 `file_paths` 一一对应的 `UploadResult` 列表，顺序与输入顺序一致。

---

## 4. 文件浏览与选择详细设计

### 4.1 文件浏览

**输入：**

- `path`: 目标目录绝对路径。
- `recursive`: 是否递归列出子目录内容。
- `include_hidden`: 是否包含隐藏文件（Windows 下含系统属性文件，Linux/macOS 下以 `.` 开头）。

**处理流程：**

```
1. 规范化路径（os.path.abspath / os.path.normpath）。
2. 校验路径存在且为目录，否则抛出 FileNotFoundError / NotADirectoryError。
3. 使用 os.scandir 遍历，避免一次性加载大量文件。
4. 对每个条目构造 FileInfo：
   - 目录：size=0，mime_type=None，extension=None。
   - 文件：通过 mimetypes / Extension 表推导 mime_type 与 telegram_type。
5. 过滤隐藏文件（按 include_hidden 决定）。
6. 递归时返回「目录本身 + 子目录内容」的扁平列表，或返回树形结构（由 API 层决定）。
```

**目录大小计算：**

- 非递归浏览时，`FileInfo.size` 对目录返回 `0`。
- 上层需要大小时，调用 `get_directory_size()` 进行递归统计；该操作可能较慢，建议 WebUI 中异步显示「计算中」。

### 4.2 文件选择

**输入：** 一组路径（可混合文件与目录）。

**处理流程：**

```
1. 去重并保持顺序。
2. 对每个路径：
   - 不存在或不可读 → 记录 warning，跳过。
   - 目录 → 递归收集其下所有非隐藏文件（默认不进入子目录，可通过参数控制）。
   - 文件 → 直接加入候选列表。
3. 按 allowed_extensions 过滤（如只保留图片/视频）。
4. 返回 FileInfo 列表。
```

### 4.3 安全性

- 禁止浏览系统关键目录（如 `C:\Windows`、`/sys`、`/proc`），通过白名单或路径前缀校验实现。
- 所有路径在进入 OS 操作前进行规范化，防止路径穿越。
- 对权限不足的文件记录 warning 并跳过，不中断流程。

---

## 5. 媒体组上传详细设计

### 5.1 Telegram 限制

| 限制 | 说明 |
|------|------|
| 最大文件数 | 单个媒体组最多 10 个文件 |
| 支持类型 | 图片（photo）、视频（video）、音频（audio） |
| 不支持类型 | 文档（document）、贴纸（sticker）、GIF（animation） |
| 单文件大小 | 普通用户 2GB，会员用户 4GB |

### 5.2 拆分策略

当输入文件超过 10 个或包含非媒体组支持类型时，按以下规则分组：

```
输入文件列表
    │
    ▼
按 telegram_type 分类
    ├── unsupported（document / sticker / animation）
    │      └── 走单文件上传路径
    └── supported（photo / video / audio）
           │
           ▼
    按顺序每 max_group_size(≤10) 个一组
           │
           ▼
    每组调用 Pyrogram send_media_group
```

**详细规则：**

1. **类型过滤：** 先调用 `_classify_files()` 将文件划分为 `album_compatible` 与 `single_only`。
2. **顺序保持：** `album_compatible` 文件按 `MediaGroupConfig.sort_by` 排序后，按原始输入顺序或排序后顺序分块；`single_only` 文件保持输入顺序单独上传。
3. **容量切块：** `album_compatible` 每达到 10 个文件即切为一组，剩余不足 10 个的尾组也作为一个媒体组。
4. **混合场景：** 当用户选择的文件同时包含兼容与不兼容类型时，最终结果为「多个媒体组」+「多个单文件」的混合序列。

### 5.3 媒体组发送流程

```python
async def upload_media_group(self, chat_id, file_paths, config, ...):
    file_infos = await self.select_files(file_paths)
    groups = self._split_into_groups(file_infos, config)

    results: list[UploadResult] = []
    for group in groups:
        if group.is_album and len(group.files) > 1:
            try:
                messages = await self._send_media_group(chat_id, group, progress_callback)
                results.extend([UploadResult(success=True, ...)] * len(group.files))
            except Exception as e:
                if config.fallback_to_single:
                    for fi in group.files:
                        results.append(await self.upload_single(chat_id, fi.path, ...))
                else:
                    results.extend([UploadResult(success=False, error_msg=str(e))] * len(group.files))
        else:
            for fi in group.files:
                results.append(await self.upload_single(chat_id, fi.path, ...))

    await self.cleanup_after_upload(results, delete_after_upload)
    return results
```

### 5.4 降级策略

| 失败场景 | 行为 |
|----------|------|
| 媒体组 API 返回 `MEDIA_INVALID`、`MEDIA_EMPTY` 等 | 当 `fallback_to_single=True` 时，将该组拆分为单文件依次上传。 |
| 单个文件大小超限 | 标记该文件失败，其余文件继续。 |
| 权限错误（`ChatAdminRequired`、`ChannelPrivate`） | 整组立即失败，不再重试。 |
| 网络超时 / FloodWait | 由外层重试机制处理，FileManager 仅抛出可识别异常。 |

---

## 6. 单文件上传详细设计

### 6.1 流程

```
1. 校验文件存在、可读、非空。
2. 校验文件大小：
   - 普通用户 > 2GB 或会员用户 > 4GB → 失败，返回错误码 UPLOAD_SIZE_LIMIT。
3. 根据 mime_type / 扩展名决定发送类型：
   - photo: send_photo
   - video: send_video（附带视频元数据）
   - audio: send_audio
   - 其他: send_document
4. 流式读取文件，chunk 大小 ≤ 512KB；内存中不保留完整文件。
   - 文件大小 > memory_limit_mb（默认 512MB）时，强制使用文件路径传入 Pyrogram，
     由 Pyrogram 内部自行分片，避免 Python 层缓存。
5. 调用 Pyrogram 发送 API，传入进度回调。
6. 上传成功后，提取 file_unique_id：
   - 调用 _extract_file_unique_id(message) 获取 file_unique_id。
   - 将 file_unique_id 写入 UploadResult。
7. 仓库模式回调（条件触发）：
   - 若 self.repository_manager 不为 None（仓库模式已启用）
     且目标 chat_id 为仓库频道
     且 source_chat_id / source_message_id 已提供：
     → 调用 repository_manager.on_upload_success() 记录来源与文件信息。
   - 触发来源可以是频道也可以是私聊：`on_upload_success()` 不区分 `source_type`，
     仅依赖 source_chat_id + source_message_id 作为唯一来源键。
   - 私聊消息没有公开 `source_link`，因此 source_chat_id + source_message_id
     是仓库映射的唯一可靠来源标识。
8. 根据 delete_after_upload 策略决定是否清理本地文件。
```

### 6.2 与现有 TelegramUploader 的兼容

- 现有 `TelegramUploader` 负责转发任务中的「下载后上传」流程，使用 `UploadTask` 与断点续传。
- FileManager 新增的 `upload_single` / `upload_media_group` 主要服务于 WebUI 的本地文件上传与 Bot 的简单上传场景。
- 两个上传路径在代码层面**不互相调用**，但共享以下工具：
  - `path_tool.safe_delete`
  - `path_tool.get_mime_from_extension`
  - `enums.UploadStatus`
  - `stdio.MetaData.suitable_units_display`
- 若后续需要统一，可在 M2/M5 阶段将 `TelegramUploader` 内部重构为调用 `FileManager`。

### 6.3 TelegramUploader 仓库模式集成

`TelegramUploader` 同样支持仓库模式，关键变更如下：

| 变更点 | 说明 |
|--------|------|
| `self.repository_manager` | 新增属性，外部注入，默认 `None`。 |
| `upload_complete_callback()` | 上传完成回调中，若仓库模式启用且目标为仓库频道，触发 `_repository_on_upload_success()`。 |
| `_repository_on_upload_success()` | 新增方法：从仓库频道获取消息，调用 `repository_manager.on_upload_success()` 记录来源与文件信息。 |
| `download_upload()` | 将 `source_chat_id` / `source_message_id` 传递给 `UploadTask`。 |

### 6.4 UploadTask 变更

`UploadTask` 新增以下可选参数以支持仓库模式来源追踪：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `source_chat_id` | `int | str | None` | `None` | 来源对话 ID（频道或私聊）。 |
| `source_message_id` | `int | None` | `None` | 来源消息 ID。与 source_chat_id 共同组成来源键；私聊消息无公开 source_link，此组合是仓库映射的主要来源标识。 |

### 6.5 流式与内存控制

| 文件大小 | 处理方式 |
|----------|----------|
| ≤ memory_limit_mb（512MB） | 可直接读取文件头计算 MD5/SHA256，或将 BytesIO 传入 Pyrogram。 |
| > memory_limit_mb | 仅传递文件路径，由 Pyrogram `save_file(path=...)` 内部流式分片；禁止全量读入内存。 |

### 6.6 下载任务仓库备份集成

`DOWNLOAD` 与 `LISTEN_DOWNLOAD` 任务完成本地下载后，若 `Task.params.enable_repository_backup == true`，
FileManager 与 RepositoryManager 应协作将文件上传至仓库频道。

**触发条件：**

- 任务类型为 `DOWNLOAD` 或 `LISTEN_DOWNLOAD`。
- `Task.params.enable_repository_backup` 为 `true`（任务级显式开启或继承全局配置 `repository.auto_backup_downloads`）。
- 本地文件下载成功且完整。

**备份流程（三级职责调用链）：**

> 此调用链与 PRD v2.3 描述一致。PRD 中的"TaskExecutor 调用 RepositoryManager"是决策层面的描述，实际执行链路经过 FileManager。

```
1. TaskExecutor 决策：检测到 enable_repository_backup == true，决定触发仓库备份。
2. FileManager 执行：调用 upload_single() / upload_media_group() 将本地文件上传至仓库频道，
   传入 source_chat_id 与 source_message_id（来自原始消息）。
3. RepositoryManager 记录：上传成功后，FileManager 触发 RepositoryManager.on_upload_success()
   记录来源映射（repository_sources）和分发记录（file_distributions）。
4. 根据 delete_after_upload 策略清理本地副本。
```

**LISTEN_DOWNLOAD 仓库备份触发路径：**

`LISTEN_DOWNLOAD` 任务的每条消息下载完成后，若 `enable_repository_backup == true`，同样通过上述三级调用链执行仓库备份：

```
新消息到达 → TaskExecutor._handle_listen_download()
    │
    ▼
复用 _execute_download() 下载文件到本地
    │
    ▼
检测 enable_repository_backup == true
    │
    ▼
调用 FileManager.upload_single() 上传至仓库频道（传入 source_chat_id / source_message_id）
    │
    ▼
FileManager 触发 RepositoryManager.on_upload_success() 记录来源映射
    │
    ▼
根据 delete_after_upload 策略清理本地副本
```

**来源标识：**

- 频道任务：`source_chat_id` + `source_message_id` 与原始 `source_link` 互为补充。
- 私聊任务：私聊消息无公开 `source_link`，`source_chat_id` + `source_message_id` 是仓库映射的主要来源标识。
- `RepositoryManager.on_upload_success()` 对频道来源与私聊来源统一处理，不区分 `source_type`。

---

## 7. 上传进度与回调

### 7.1 回调结构

FileManager 同时支持**全局回调**与**单次回调**：

```python
async def _progress_wrapper(
    self,
    task_id: str,
    file_path: str,
    current: int,
    total: int,
    callback: Callable[[UploadProgress], Awaitable[None]] | None,
):
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
```

### 7.2 进度粒度

- **单文件：** 每个分片上传后触发一次回调（Pyrogram `progress` 参数）。
- **媒体组：** 以组内单个文件为单位触发回调；媒体组整体发送成功后再统一更新状态为 `success`。

### 7.3 WebUI 实时推送

- WebAPI 层将 `progress_callback` 与 WebSocket 绑定。
- FileManager 本身不感知 WebSocket，仅调用回调；由上层决定如何广播。

---

## 8. 本地文件清理策略

### 8.1 策略定义

| 策略 | 默认值 | 说明 |
|------|--------|------|
| `delete_after_upload` | `True`（转发任务）/ `False`（普通上传任务） | 上传成功后是否删除本地文件。 |

### 8.2 清理流程

```python
async def cleanup_after_upload(self, results, delete_after_upload):
    for res in results:
        if not res.success:
            continue
        if delete_after_upload and res.file_path and os.path.exists(res.file_path):
            res.deleted = await self.delete_local_file(res.file_path)
    return results
```

### 8.3 安全约束

- 只删除**文件**，不删除非空目录。
- 删除前再次校验路径，避免误删系统目录或配置目录。
- 删除失败不影响上传结果，仅记录 warning。
- 不清理 `.json` 断点续传元数据文件；这些文件由 `UploadTask` / `TelegramUploader` 自行管理。

---

## 9. 错误处理

### 9.1 错误码

| 错误码 | 场景 | 建议行为 |
|--------|------|---------|
| `FILE_NOT_FOUND` | 文件不存在或不可读 | 跳过该文件，记录日志。 |
| `FILE_EMPTY` | 文件大小为 0 | 跳过。 |
| `UPLOAD_SIZE_LIMIT` | 超过 Telegram 单文件大小限制 | 失败，不重试。 |
| `MEDIA_GROUP_INVALID` | 媒体组类型/数量不符合 Telegram 要求 | 降级为单文件发送。 |
| `PERMISSION_DENIED` | 频道无权限 / 私有频道 | 失败，不重试。 |
| `NETWORK_ERROR` | 网络超时 / 连接错误 | 由外层重试。 |
| `FLOOD_WAIT_X` | Telegram 限流 | 等待指定时间后重试。 |
| `DELETE_FAILED` | 本地文件删除失败 | 记录 warning，不影响上传结果。 |
| `COPY_MESSAGE_FAILED` | 仓库分发 copy_message 失败 | 降级为 file_id_send，由 RepositoryManager 处理。 |
| `FILE_ID_SEND_FAILED` | 仓库分发 file_id_send 失败 | 降级为重新下载上传，由 RepositoryManager 处理。 |
| `REPOSITORY_WRITE_FAILED` | 仓库数据库写入失败 | 记录 error，不影响上传结果本身。 |

### 9.2 异常体系

```python
class FileManagerError(Exception):
    def __init__(self, code: str, message: str, file_path: str | None = None):
        self.code = code
        self.message = message
        self.file_path = file_path

class FileNotFound(FileManagerError): ...
class UploadSizeLimit(FileManagerError): ...
class MediaGroupInvalid(FileManagerError): ...
```

### 9.3 日志规范

- 文件浏览失败：`log.warning` + 错误码。
- 上传失败：`log.error` + 异常堆栈（仅调试模式）。
- 清理失败：`log.warning`。

---

## 10. TDD 测试策略

### 10.1 测试目标

- FileManager 核心逻辑单元测试覆盖率 ≥ 80%。
- 所有依赖 Pyrogram / OS / IO 的行为均通过 Mock 隔离。

### 10.2 单元测试用例清单

#### 文件浏览与选择

| ID | 用例 | 期望结果 |
|----|------|---------|
| FM-LIST-01 | 列出空目录 | 返回空列表 |
| FM-LIST-02 | 列出含文件与子目录的目录 | 正确返回 FileInfo，目录标记 is_directory=True |
| FM-LIST-03 | 递归列出多层目录 | 返回所有层级文件 |
| FM-LIST-04 | 路径不存在 | 抛出 FileNotFoundError |
| FM-LIST-05 | 过滤隐藏文件 | include_hidden=False 时隐藏文件不出现在结果中 |
| FM-SELECT-01 | 选择混合文件与目录 | 目录递归展开，文件直接入选 |
| FM-SELECT-02 | 选择含不存在路径的列表 | 跳过不存在路径，返回其余结果 |
| FM-SELECT-03 | 按扩展名过滤 | 只保留指定扩展名 |
| FM-INFO-01 | 获取图片文件信息 | telegram_type='photo'，mime_type 正确 |
| FM-INFO-02 | 获取 GIF 文件信息 | telegram_type='animation' |
| FM-INFO-03 | 获取文档文件信息 | telegram_type='document' |

#### 媒体组拆分

| ID | 用例 | 期望结果 |
|----|------|---------|
| FM-SPLIT-01 | 11 个图片均分 | 拆分为 10 + 1 两组 |
| FM-SPLIT-02 | 25 个视频均分 | 拆分为 10 + 10 + 5 三组 |
| FM-SPLIT-03 | 混合图片与文档 | 图片进媒体组，文档走单文件 |
| FM-SPLIT-04 | 混合 GIF 与图片 | GIF 走单文件，图片进媒体组 |
| FM-SPLIT-05 | max_group_size > 10 | 强制截断为 10 |
| FM-SPLIT-06 | 空列表 | 返回空分组 |

#### 单文件上传

| ID | 用例 | 期望结果 |
|----|------|---------|
| FM-SINGLE-01 | 上传普通图片 | 调用 send_photo，返回成功 |
| FM-SINGLE-02 | 上传视频 | 调用 send_video，附带元数据 |
| FM-SINGLE-03 | 上传文档 | 调用 send_document |
| FM-SINGLE-04 | 文件超过大小限制 | 返回 UPLOAD_SIZE_LIMIT，不调用 API |
| FM-SINGLE-05 | 上传后清理开启 | 成功后文件被删除 |
| FM-SINGLE-06 | 上传后清理关闭 | 成功后文件保留 |

#### 媒体组上传

| ID | 用例 | 期望结果 |
|----|------|---------|
| FM-ALBUM-01 | 10 个图片上传 | 调用一次 send_media_group |
| FM-ALBUM-02 | 12 个图片上传 | 调用两次 send_media_group（10 + 2） |
| FM-ALBUM-03 | 媒体组 API 失败且 fallback=True | 降级为单文件发送 |
| FM-ALBUM-04 | 媒体组 API 失败且 fallback=False | 整组失败 |
| FM-ALBUM-05 | 含文档的混合列表 | 文档单独发送，图片媒体组发送 |

#### 进度回调

| ID | 用例 | 期望结果 |
|----|------|---------|
| FM-PROG-01 | 单文件上传触发进度 | 回调至少被调用两次（0% 与 100%） |
| FM-PROG-02 | 媒体组上传触发进度 | 每个文件均触发进度回调 |
| FM-PROG-03 | 单次回调覆盖全局回调 | 仅单次回调生效 |

#### 仓库模式回调

| ID | 用例 | 期望结果 |
|----|------|---------|
| FM-REPO-01 | 上传成功后提供 source_chat_id / source_message_id | 调用 RepositoryManager.on_upload_success() |
| FM-REPO-02 | 私聊来源上传成功（无 source_link） | 以 source_chat_id + source_message_id 调用 on_upload_success() |
| FM-REPO-03 | 未提供来源 ID | 不触发 on_upload_success() |

### 10.3 Mock 点

| 依赖 | Mock 方式 | 说明 |
|------|----------|------|
| `pyrogram.Client` | `AsyncMock` | 模拟 `send_photo`、`send_video`、`send_document`、`send_media_group`。 |
| 文件系统 | `tmp_path` / `monkeypatch` | pytest 临时目录，避免污染真实环境。 |
| `os.scandir` | `unittest.mock.patch` | 用于测试隐藏文件过滤、权限异常。 |
| `path_tool.safe_delete` | `unittest.mock.patch` | 验证清理策略，不实际删除。 |
| 进度回调 | `AsyncMock` | 验证调用次数与参数。 |
| `RepositoryManager` | `MagicMock` / `AsyncMock` | 验证仓库模式回调触发及参数。 |
| 配置 | 传入 dict | 不读取真实 config.yaml。 |

### 10.4 覆盖率目标

| 模块 | 目标覆盖率 |
|------|-----------|
| `module/core/file_manager.py` | ≥ 85% |
| 数据模型（FileInfo / UploadResult / MediaGroupConfig） | ≥ 90% |
| 工具函数（_classify_files / _split_into_groups） | ≥ 90% |

---

## 11. 依赖关系

### 11.1 内部依赖

| 依赖模块 | 用途 |
|----------|------|
| `module.path_tool` | `safe_delete`、`get_mime_from_extension`、`split_path`、`calc_sha256` |
| `module.enums` | `UploadStatus` |
| `module.language` | `_t` 多语言文案 |
| `module.stdio` | `MetaData.suitable_units_display` |
| `module.task` | `UploadTask`（兼容现有转发上传路径） |
| `module.core.repository_manager` | `RepositoryManager`（仓库模式编排层，可选依赖） |
| `module.core.repository_db` | `RepositoryDB`（仓库数据库管理，通过 RepositoryManager 间接使用） |

### 11.2 外部依赖

| 依赖 | 用途 |
|------|------|
| `pyrogram` | Telegram 客户端 API：`send_media_group`、`send_photo`、`send_video`、`send_document`、`send_audio` |
| `pymediainfo` | 视频元数据获取（复用现有 `TelegramUploader.get_video_info`） |
| `pytest` / `pytest-asyncio` | 单元测试框架 |

### 11.3 被依赖方

| 使用方 | 用途 |
|--------|------|
| `module/api/routes/files.py` | WebUI 文件浏览、上传 API。 |
| `module/bot.py` | `/upload`、`/upload_r` 等命令。 |
| `module/core/task_manager.py` | 创建上传任务时调用 FileManager。 |
| `module/core/task_executor.py` | 下载任务完成后调用 FileManager 执行仓库备份上传。 |
| `module/core/repository_manager.py` | 通过 FileManager 的 `repository_manager` 属性注入，接收上传成功回调。 |

---

## 12. 风险与假设

### 12.1 风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 媒体组降级导致顺序变化 | 中 | 保持 `UploadResult` 与输入 `file_paths` 顺序一致；UI 层按索引回填状态。 |
| 大文件上传占用内存 | 高 | 严格使用文件路径传入 Pyrogram；单文件内存缓存上限 512MB。 |
| 路径穿越攻击 | 中 | 所有路径进入 OS 前规范化并校验白名单前缀。 |
| 删除策略误删用户文件 | 高 | 仅删除明确选中的文件，不递归删除非空目录；删除失败不影响业务结果。 |
| Pyrogram 版本升级导致 API 变化 | 低 | 将 Pyrogram 调用封装在 `_send_*` 私有方法中，便于集中适配。 |
| 并发上传导致 FloodWait | 中 | 由 TaskManager 控制 `max_upload_concurrency`，FileManager 仅处理单文件/单组上传。 |

### 12.2 假设

| 假设 | 说明 |
|------|------|
| Pyrogram Client 已授权并启动 | FileManager 不处理登录流程。 |
| 上层已做磁盘空间检查 | 资源保护由 TaskManager 统一负责，FileManager 仅执行上传。 |
| 单用户场景 | 无需多用户隔离，文件路径以当前进程工作目录为基准。 |
| Telegram 限制不变 | 媒体组最大 10 个文件、不支持 document/sticker/GIF 等限制写死为常量，便于后续调整。 |
| 文件路径使用 UTF-8 | 与现有项目约定一致，不额外处理 GBK 等编码。 |

---

## 附录 A：常量定义

```python
class FileManagerConstants:
    MAX_MEDIA_GROUP_SIZE: int = 10
    DEFAULT_MEMORY_LIMIT_MB: int = 512
    DEFAULT_DELETE_AFTER_UPLOAD: bool = False
    FORWARD_DELETE_AFTER_UPLOAD: bool = True

    SUPPORTED_ALBUM_TYPES: set = {'photo', 'video', 'audio'}
    UNSUPPORTED_ALBUM_TYPES: set = {'document', 'sticker', 'animation'}
```

---

## 附录 B：与主设计文档的对应关系

| 主设计文档章节 | 本文档章节 |
|----------------|-----------|
| 4.2.2 文件管理 | 第 4 章 |
| 4.2.1.3 转发任务本地文件清理 | 第 8 章 |
| 4.2.1.4 资源限制（memory_limit_mb） | 第 6.3 节 |
| 5.2 FileManager 模块签名 | 第 3 章 |
| 9.1 Telegram 媒体组限制 | 第 5.1 节 |
| 七、非功能性需求（测试覆盖 ≥ 80%） | 第 10 章 |

---

> **文档结束**
