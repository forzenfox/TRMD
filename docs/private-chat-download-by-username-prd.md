# 私聊对话文件操作功能PRD - Username访问模式

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **文档版本**: v2.3
> **创建日期**: 2026-07-01
> **更新日期**: 2026-07-03
> **作者**: AI Assistant
> **状态**: 最终版  
> **关联文档**: [私聊对话文件下载能力分析.md](../.trae/documents/私聊对话文件下载能力分析.md)

---

## 变更记录

| 版本 | 日期 | 变更内容 | 状态 |
|------|------|----------|------|
| v2.3 | 2026-07-03 | 技术评审定稿:明确监听任务状态机(不新增PAUSED),补充动态Item管理规则,新增chat_id重复监听409排他校验,移除source_type暴露字段,明确recent_count两层校验,补充resolve API限流与防抖,精简实施计划阶段3,清理术语表 | 最终版 |
| v2.2 | 2026-07-03 | 技术评审修订:采用方案A迁移统一监听架构,新增§4.4监听迁移策略,补充IdentifierService与parse_link复用关系,修复模块归属错误,修正频道监听描述,补充迁移范围(/listen_info/回调按钮),新增F11/F12验收项 | 已合并 |
| v2.1 | 2026-07-02 | 新增仓库备份配置设计:全局配置(auto_backup_downloads)+任务级覆盖(params.enable_repository_backup) | 已合并 |
| v2.0 | 2026-07-02 | 架构重构:对齐现有TaskManager/TaskExecutor架构,移除独立私聊方法/API,统一解析服务 | 已合并 |
| v1.1 | 2026-07-01 | 初版仅支持WebUI,仅支持Username直接指定,扩展任务类型支持(下载、转发、监听下载、监听转发) | 已废弃 |
| v1.0 | 2026-07-01 | 初始PRD文档 | 已废弃 |

---

## 一、功能背景与价值

### 1.1 现状问题

**当前限制**:
- 项目仅支持通过公开链接(https://t.me/channel_name)访问频道/群组
- 不支持访问私聊对话(private chat)中的文件操作
- 私聊对话没有公开链接,无法通过现有机制访问
- 现有监听功能(`listen_download`/`listen_forward`)仅通过Bot命令操作,状态存储在内存中,进程重启后丢失
- 监听逻辑散落在旧架构`downloader.py`中,与新架构`TaskManager`/`TaskExecutor`不统一

**用户痛点**:
| 场景 | 痛点 | 影响 |
|------|------|------|
| **Bot资源收集** | Bot发送的文件无法批量下载/转发,只能手动逐个操作 | 效率低,耗时 |
| **私聊文件整理** | 与朋友/同事交换的文件无法统一管理 | 文件分散,难以整理 |
| **Saved Messages** | 自己保存的重要文件无法批量导出/转发 | 无法备份整理 |
| **无链接对话** | 部分用户/Bot没有公开链接,无法访问 | 功能缺失 |

### 1.2 可行性验证结果

**测试结论** (详见测试报告):
- ✅ **通过chat_id可以访问私聊对话**
- ✅ **可以获取私聊历史消息**
- ✅ **可以下载私聊中的媒体文件**
- ✅ **文件完整性验证通过**
- ✅ **通过username可以解析chat_id**

**技术可行性**: 100%可行,已通过实际下载验证

### 1.3 功能价值

**核心价值**:
- 解锁私聊对话文件操作能力,扩展项目覆盖范围
- 支持完整的任务类型(下载、转发、监听下载、监听转发)
- 仅通过Username即可访问,无需公开链接
- 提升用户效率,无需手动逐个操作文件

**预期收益**:
- 功能覆盖率: 从"仅公开频道/群组"扩展到"所有对话类型"
- 任务类型: 从"下载+转发"扩展到"下载+转发+监听下载+监听转发"(含私聊支持)
- 监听架构: 从"Bot命令+内存状态"统一到"TaskManager/TaskExecutor+SQLite持久化"
- 用户效率: 从"手动逐个操作"提升到"批量自动处理"
- 场景支持: 新增Bot资源收集、私聊文件整理、个人备份、实时监听等场景

---

## 二、用户场景与需求

### 2.1 目标用户

| 用户类型 | 典型场景 | 频次 |
|---------|---------|------|
| **Bot用户** | 收集Bot发送的资源文件(下载/转发) | 高频 |
| **私聊用户** | 整理与朋友/同事交换的文件 | 中频 |
| **个人用户** | 批量导出Saved Messages中的文件 | 低频 |

### 2.2 典型场景

#### 场景1: Bot资源批量下载

**用户故事**:
```
用户A: "我订阅了一个资源Bot(@seseYunBot),它每天发送精选视频。
       我想把最近一个月的视频全部下载到本地整理,
       但现在只能手动逐个保存,太麻烦了。"
```

**需求**:
- 输入Bot username(@seseYunBot)
- 选择时间范围(最近一个月)
- 批量下载所有视频文件

#### 场景2: Bot资源转发

**用户故事**:
```
用户B: "我订阅了一个资源Bot(@seseYunBot),它每天发送精选视频。
       我想把这些视频转发到我的私有频道保存,
       但现在只能手动逐个转发,效率很低。"
```

**需求**:
- 输入源Bot username(@seseYunBot)
- 输入目标频道链接或username
- 选择消息范围
- 批量转发所有文件

#### 场景3: 监听Bot新资源

**用户故事**:
```
用户C: "我希望实时监听@seseYunBot的新消息,
       一旦它发送新视频就自动下载到本地,
       这样就不用手动查看和保存了。"
```

**需求**:
- 输入Bot username(@seseYunBot)
- 启动监听任务
- 实时自动下载新发送的文件

#### 场景4: 监听转发到私有频道

**用户故事**:
```
用户D: "我希望实时监听@seseYunBot的新消息,
       一旦它发送新视频就自动转发到我的私有频道,
       这样就能自动同步收藏了。"
```

**需求**:
- 输入源Bot username(@seseYunBot)
- 输入目标频道链接或username
- 启动监听任务
- 实时自动转发新发送的文件

---

## 三、功能设计方案

### 3.1 功能架构

**新增能力矩阵**(基于现有架构扩展):

| 维度 | 现有能力 | 新增能力 | 扩展方式 |
|------|---------|---------|---------|
| **对话类型** | 公开频道/群组 | 私聊对话(Bot/用户/Saved) | 扩展输入格式 |
| **访问方式** | 公开链接(t.me) | Username/chat_id/t.me链接 | 统一Identifier解析服务 |
| **任务类型** | DOWNLOAD/FORWARD/UPLOAD | + LISTEN_DOWNLOAD/LISTEN_FORWARD | 扩展TaskType枚举;LISTEN_*同时覆盖频道和私聊,统一迁移旧架构监听逻辑 |
| **消息范围** | date_range/id_range/multiple_ids/all | + recent | 扩展RangeMode枚举 |

**设计原则**:
- ✅ **复用现有入口**: 不新增独立方法/API,扩展现有接口
- ✅ **统一解析逻辑**: 消除三处重复实现,建立公共解析服务
- ✅ **执行逻辑共享**: 私聊与频道的下载/转发使用相同执行路径
- ⚠️ **Bot监听命令迁移**: Bot的 `/listen_download` `/listen_forward` 命令迁移至 TaskExecutor 统一管理(方案A:迁移统一)
- ❌ **不支持对话列表选择**: 仅支持Username直接指定

### 3.2 核心功能模块

#### 模块1: Identifier统一解析服务 (新增)

**定位**: 替代现有三处重复的 `_resolve_chat_id()` 实现,提供统一的标识符解析能力

**与现有 `parse_link` 的关系**:
- `parse_link`([helpers.py](../module/utils/helpers.py)) 负责**链接级解析**,返回 `chat_id` + `comment_id` + `topic_id`,被旧架构 `downloader.py` 大量使用,保留不合并
- `extract_info_from_link`([helpers.py](../module/utils/helpers.py)) 负责**链接格式提取**,IdentifierService 内部复用此函数进行 t.me 链接的格式检测
- `_resolve_chat_id`([tasks.py](../module/api/routes/tasks.py) / [chats.py](../module/api/routes/chats.py)) 负责标识符→chat_id 转换,**将被 IdentifierService 替代**

**职责**:
- 接受 username / chat_id / t.me链接 三种输入格式
- 返回标准化的 chat_id + 对话元信息
- 提供输入格式自动检测与规范化
- 内部复用 `extract_info_from_link()` 进行链接格式提取

**支持的输入格式**:

| 格式 | 示例 | 说明 |
|------|------|------|
| 纯数字ID | `8288406549` | 直接作为chat_id返回 |
| @username | `@seseYunBot` | 去掉@前缀后调用get_chat |
| 纯username | `seseYunBot` | 直接调用get_chat |
| t.me链接 | `https://t.me/seseYunBot` | 提取username后调用get_chat |

**输出结构**:
```python
@dataclass
class ResolvedChat:
    chat_id: int              # 数字ID
    chat_type: str            # "bot" | "private" | "channel" | "group" | "supergroup"
    chat_name: str            # 显示名称
    username: str | None      # 用户名(如果有)
    message_count: int        # 消息总数估算
    media_count: int          # 媒体消息数估算
    has_access: bool          # 是否可访问
    is_private: bool          # 是否为私聊类型
```

**错误处理规范**:

| 错误场景 | HTTP状态码 | 错误码 | 错误消息 |
|---------|-----------|--------|---------|
| 无效输入格式 | 400 | `INVALID_IDENTIFIER` | 标识符格式不正确 |
| 不存在的用户名 | 404 | `USER_NOT_FOUND` | 无法找到该用户/频道 |
| 无对话权限 | 403 | `ACCESS_DENIED` | 您尚未与此用户建立对话 |
| 网络超时 | 504 | `RESOLVE_TIMEOUT` | 解析请求超时,请重试 |
| API限流 | 429 | `RATE_LIMITED` | 请求过于频繁,请稍后再试(响应体含 `retry_after`) |

#### 模块2: TaskType枚举扩展

**现有类型** (来自 [task_manager.py](../module/core/task_manager.py)):
```python
class TaskType(Enum):
    DOWNLOAD = "download"
    FORWARD = "forward"
    UPLOAD = "upload"
```

**新增类型**:
```python
class TaskType(Enum):
    DOWNLOAD = "download"           # 现有: 频道/私聊下载
    FORWARD = "forward"             # 现有: 频道/私聊转发
    UPLOAD = "upload"               # 现有: 上传
    LISTEN_DOWNLOAD = "listen_download"   # 新增: 监听并下载
    LISTEN_FORWARD = "listen_forward"     # 新增: 监听并转发
```

**说明**: 
- `DOWNLOAD` 和 `FORWARD` 类型同时支持公开频道和私聊对话,通过内部推导的 `source_type` 区分
- 新增的 `LISTEN_*` 类型用于实时监听类任务
- `LISTEN_*` 为长期运行任务,状态流转为 `pending → queued → running → cancelled/failed`,**不会进入 `completed` 状态**

#### 模块3: RangeMode枚举扩展

**现有模式** (来自 [task.py](../module/api/models/task.py)):
```python
RangeMode = Literal["date_range", "id_range", "multiple_ids", "all"]
```

**扩展后**:
```python
RangeMode = Literal["date_range", "id_range", "multiple_ids", "all", "recent"]
```

**新增 `recent` 模式参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `recent_count` | int | 是(recent模式) | 最近N条消息(N > 0,上限1000) |

**校验规则**:
1. **API层**: `recent_count` 必须大于0,否则返回 400 `INVALID_RECENT_COUNT`
2. **TaskManager层**: 若 `recent_count > 1000`,自动截断至1000,并记录 warning 日志
3. 上限1000用于防止一次性拉取过多历史消息导致性能问题或FloodWait

#### 模块4: Task.create_task() 参数扩展

**扩展策略**: 通过 `params` 字典传递私聊相关参数,不修改 Task dataclass 结构

**params 新增字段定义**:

| 字段 | 类型 | 必填 | 适用任务类型 | 说明 |
|------|------|------|-------------|------|
| `source_identifier` | str | **是**(私聊模式) | 全部 | 源对话标识符(username/chat_id/链接) |
| `target_identifier` | str | 是(FORWARD/LISTEN_FORWARD) | FORWARD/LISTEN_FORWARD | 目标对话标识符 |
| `media_types` | list[str] | 否 | 全部 | 媒体类型过滤: `["video","photo","document","audio"]` |
| `min_size` | int | 否 | 非监听任务 | 最小文件大小(字节) |
| `max_size` | int | 否 | 非监听任务 | 最大文件大小(字节) |
| `recent_count` | int | 是(recent模式) | 非监听任务 | 最近N条消息 |
| `enable_repository_backup` | bool | 否 | DOWNLOAD/LISTEN_DOWNLOAD | 是否备份到仓库频道；null=继承全局配置 |

> **注**: `source_type` (`channel`/`private`) 不再作为 `params` 暴露字段,由系统内部通过 `IdentifierService.resolve()` 的结果自动推导,存储在 `Task.extra` 中供执行层使用。

**向后兼容性**:
- 当 `params` 包含 `chat_id`(t.me链接格式) → 走原有频道逻辑(无破坏性变更)
- 当 `params` 包含 `source_identifier` → 走新的私聊解析逻辑
- 两者互斥,优先检查 `source_identifier`

**任务创建排他性校验**:

对于 `LISTEN_DOWNLOAD` / `LISTEN_FORWARD` 任务,`TaskManager.create_task()` 需检查同一 `chat_id` + `task_type` 组合是否已存在 `running` 或 `pending` 状态的任务:
- 若存在,抛出 `TaskConflictError`,API返回 409 `LISTEN_ALREADY_EXISTS`
- 此规则避免同一对话上重复注册 Handler 导致消息重复处理

**错误响应示例**(409):
```json
{
  "code": 409,
  "message": "该对话已存在运行中的监听下载任务",
  "data": null
}
```

#### 模块4.1: 监听任务动态Item管理

**适用任务类型**: `LISTEN_DOWNLOAD` / `LISTEN_FORWARD`

**设计原则**: 监听任务创建时 `items=[]`,新消息到达后动态生成 `TaskItem`,通过现有 `TaskManager` 接口统一持久化。

**动态Item生成规则**:

| 字段 | 取值规则 |
|------|---------|
| `item.id` | 由 `TaskManager` 统一生成的唯一ID |
| `item.task_id` | 所属监听任务的 `task_id` |
| `item.source_id` | 触发监听的消息ID (`message.id`) |
| `item.source_link` | 私聊消息无公开链接,此处为 `None` 或空字符串 |
| `item.status` | `pending → running → completed/failed/skipped` |
| `item.extra["message_id"]` | 原始消息ID |
| `item.extra["chat_id"]` | 源对话 `chat_id` |

**统计更新规则**:
- 不预先设置 `Task.total_count`
- 每处理一条消息,`total_count` 自动 `+1`
- 成功/失败/跳过时,对应 `success_items` / `failed_items` / `skipped_items` 自动 `+1`
- 通过 `TaskManager.add_items()` 新增Item,通过 `TaskManager.update_item_status()` 更新状态

**实现要点**:
- `TaskExecutor._handle_listen_download()` / `_handle_listen_forward()` 内部调用 `_execute_download()` / `_execute_forward()` 前,先创建临时 `TaskItem`
- 执行完成后根据结果更新Item状态
- 避免为已处理消息重复生成Item(通过 `source_id` 去重)

---

#### 模块5: 仓库备份配置

**设计原则**: 全局配置 + 任务级覆盖，两层控制机制

**配置层级**:

| 层级 | 配置项 | 位置 | 默认值 | 说明 |
|------|--------|------|--------|------|
| **全局配置** | `repository.auto_backup_downloads` | config.yaml | `true` | 所有下载任务的默认备份行为 |
| **任务级配置** | `params.enable_repository_backup` | Task.params | 继承全局配置 | 单个任务的备份控制，可覆盖全局配置 |

**全局配置定义** (config.yaml):
```yaml
repository:
  auto_backup_downloads: true       # 全局自动备份开关(默认开启)
  repository_channel: "@my_repo"    # 仓库频道username(必需)
  dedup_enabled: true               # 去重功能开关(默认启用)
```

**行为逻辑**:
1. 当 `repository.auto_backup_downloads = true` 时，所有下载任务默认上传到仓库频道
2. 创建任务时，用户可通过 `params.enable_repository_backup` 覆盖默认行为
3. 任务级配置的默认值 = 全局配置值（用户不指定时自动继承）
4. 仅对 `DOWNLOAD` 和 `LISTEN_DOWNLOAD` 任务类型生效（转发任务不涉及本地存储）

**params 字段扩展**:

| 字段 | 类型 | 必填 | 适用任务类型 | 说明 |
|------|------|------|-------------|------|
| `enable_repository_backup` | bool | 否 | DOWNLOAD / LISTEN_DOWNLOAD | 是否备份到仓库频道；null=继承全局配置，true=强制启用，false=强制禁用 |

**API请求示例** (强制禁用备份):
```json
{
  "task_type": "download",
  "params": {
    "source_identifier": "@seseYunBot",
    "enable_repository_backup": false   // 覆盖全局配置，禁用备份
  }
}
```

**WebUI界面选项**:
```
┌─────────────────────────────────────────────────────────┐
│  仓库备份选项:                                            │
│  [●] 备份到仓库频道 (全局默认: 开启)                      │
│      仓库频道: @my_repo                                  │
│                                                          │
│  💡 取消勾选可禁用当前任务的备份                          │
└─────────────────────────────────────────────────────────┘
```

**实现要点**:
- TaskManager.create_task() 中判断：若 `params.enable_repository_backup` 为 null，则读取全局配置填充
- 最终决策值存储在 `Task.params.enable_repository_backup` 中（true/false）
- TaskExecutor 执行时根据 `params.enable_repository_backup` 决定是否调用 RepositoryManager
- 应用启动时检查：若 `repository.auto_backup_downloads=true` 但 `repository_channel` 未配置，记录 warning 日志并降级为 `false`，避免下载任务失败

---

## 四、技术实现方案

### 4.1 API契约

#### API 1: Identifier解析 (新增)

**端点**: `GET /api/chats/resolve`

**请求参数** (Query String):

| 参数 | 类型 | 必填 | 示例 | 说明 |
|------|------|------|------|------|
| `identifier` | string | 是 | `@seseYunBot` | 要解析的标识符 |

**成功响应** (200 OK):
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "chat_id": 8288406549,
    "chat_type": "bot",
    "chat_name": "sosov2☁️精选资源",
    "username": "seseYunBot",
    "message_count": 9,
    "media_count": 2,
    "has_access": true,
    "is_private": true
  }
}
```

**错误响应示例**:
```json
// 400 - 格式无效
{
  "code": 400,
  "message": "标识符格式不正确",
  "data": null
}

// 403 - 无权限
{
  "code": 403,
  "message": "您尚未与此用户建立对话",
  "data": null
}

// 429 - API限流
{
  "code": 429,
  "message": "请求过于频繁,请稍后再试",
  "data": { "retry_after": 30 }
}
```

> **缓存与限流策略**: `GET /api/chats/resolve` 不实现服务端缓存,避免chat信息不一致;前端"解析"按钮需做至少3秒的防抖处理,降低触发Telegram FloodWait的概率。

#### API 2: 创建任务 (扩展现有端点)

**端点**: `POST /api/tasks` (复用现有端点,无变化)

**请求体** (私聊下载任务):
```json
{
  "task_type": "download",
  "params": {
    "source_identifier": "@seseYunBot",
    "range_mode": "recent",
    "recent_count": 10,
    "media_types": ["video"],
    "min_size": null,
    "max_size": null
  }
}
```

**请求体** (私聊转发任务):
```json
{
  "task_type": "forward",
  "params": {
    "source_identifier": "@seseYunBot",
    "target_identifier": "@my_channel",
    "range_mode": "id_range",
    "min_id": 14425,
    "max_id": 14426,
    "media_types": ["video"]
  }
}
```

**请求体** (监听下载任务):
```json
{
  "task_type": "listen_download",
  "params": {
    "source_identifier": "@seseYunBot",
    "media_types": ["video", "photo"]
  }
}
```

**请求体** (监听转发任务):
```json
{
  "task_type": "listen_forward",
  "params": {
    "source_identifier": "@seseYunBot",
    "target_identifier": "@my_channel",
    "media_types": ["video"]
  }
}
```

**响应体** (无变化,复用现有响应格式):
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "task_abc123",
    "task_type": "download",
    "status": "pending",
    "progress": 0,
    "total_count": 2,
    "created_at": "2026-07-02T12:00:00Z"
  }
}
```

### 4.2 数据流

#### 私聊下载任务数据流

```
[WebUI] ──POST /api/tasks──> [Router]
                                    │
                              params含source_identifier?
                              /                \
                           Yes                  No
                            │                    │
                     [IdentifierService]    [IdentifierService]
                      .resolve()            .resolve() ← 统一入口
                            │                    │
                     ResolvedChat对象      ResolvedChat对象
                            │                    │
                     [TaskManager.create_task()]
                       │ 识别source_type="private" / "channel"
                       │ 解析消息范围(_resolve_message_ids + recent模式)
                       │ 过滤媒体消息
                       │ 创建TaskItem列表
                       │
                       ▼
                     [TaskQueue] ──> [TaskExecutor.execute_task()]
                                           │
                                     task_type=download
                                     source_type=private
                                           │
                                      _execute_download() ← 复用现有逻辑!
```

#### 私聊转发任务降级链

```
[TaskExecutor._execute_forward()] (复用现有方法)
        │
        ▼
[RepositoryManager.distribute_to_target()] ← 复用现有三级降级链
        │
        ├── Level 1: client.copy_message() (直接转发)
        │       ↓ 失败
        ├── Level 2: file_id_send (通过file_id重发)
        │       ↓ 失败
        └── Level 3: 下载后上传 (完整降级)
```

### 4.3 关键行为差异 (私聊 vs 频道)

| 维度 | 频道任务 | 私聊任务 | 处理方式 |
|------|---------|---------|---------|
| **源标识符** | `params.chat_id`(t.me链接) | `params.source_identifier` | create_task内部判断 |
| **消息获取** | 公开频道直接遍历 | 需先验证对话可访问性 | get_chat检查 |
| **监听机制** | 旧:Bot命令+内存Handler;新:TaskExecutor统一管理 | 注册NewMessage Handler | 方案A迁移统一,频道/私聊均走TaskExecutor |
| **仓库备份** | 按全局配置 | 继承全局配置+可覆盖 | params.enable_repository_backup 控制 |
| **去重检查** | L1+L2+L3三级去重 | 同上 | 复用现有RepositoryManager |

### 4.4 监听任务迁移策略 (方案A: 迁移统一)

**现状分析**:

当前项目中存在两套监听实现:
- **旧架构**: `TelegramRestrictedMediaDownloader`([downloader.py](../module/downloader.py)) 通过 `self.user.add_handler()` 在 User Client 上注册监听 Handler,状态存储在 `StateManager` 的内存 dict 中(`listen_download_chat` / `listen_forward_chat`)
- **新架构**: PRD 提议在 `TaskExecutor` 中统一管理监听 Handler 生命周期,状态持久化到 TaskManager 的 SQLite 中

**问题**: 两者操作同一个 User Client (`self.app.client`),若不迁移则同一 chat_id 上的 Handler 会重复触发,且状态互不感知。

**决策: 方案A - 迁移统一**

将旧架构的监听逻辑完全迁移至 TaskExecutor,实现统一的 Handler 生命周期管理。

**迁移范围**:

| 迁移项 | 旧位置 | 新位置 | 迁移方式 |
|--------|--------|--------|---------|
| 监听 Handler 注册 | `downloader.py:add_listen_chat()` | `TaskExecutor._start_listener()` | 重写:通过 TaskManager 创建 LISTEN_DOWNLOAD/LISTEN_FORWARD 任务 |
| 监听 Handler 移除 | `downloader.py:cancel_listen()` | `TaskExecutor._stop_listener()` | 重写:取消任务时移除 Handler |
| 监听下载回调 | `downloader.py:listen_download()` | `TaskExecutor._handle_listen_download()` | 迁移:复用 `_execute_download()` 逻辑 |
| 监听转发回调 | `downloader.py:listen_forward()` | `TaskExecutor._handle_listen_forward()` | 迁移:复用 `_execute_forward()` + RepositoryManager 降级链 |
| 监听状态存储 | `StateManager.listen_download_chat`(内存dict) | `TaskManager._tasks`(SQLite) | 迁移:持久化存储,进程重启后可恢复 |
| Bot 命令入口 | `CommandRouter.on_listen()` | 保持不变(参数转换层) | 改造:调用 `TaskManager.create_task()` 替代直接注册 Handler |
| 监听信息查询 | `CommandRouter.listen_info()` | 保持不变(查询层) | 改造:从 TaskManager 查询 LISTEN_* 任务替代遍历内存dict |
| 监听回调按钮 | `downloader.py:callback_data()`(REMOVE_LISTEN_*) | `TaskExecutor._stop_listener()` | 改造:按钮回调触发任务取消 |

**迁移后的 Bot 命令流程**:

```
用户发送 /listen_download @seseYunBot
        │
        ▼
[CommandRouter.on_listen()] (参数转换层,保持不变)
        │ 解析命令参数
        │ 调用 TaskManager.create_task()
        ▼
[TaskManager.create_task(task_type=LISTEN_DOWNLOAD, params={source_identifier: ...})]
        │ 创建 Task + TaskItem
        │ 持久化到 SQLite
        ▼
[TaskExecutor.execute_task()] (统一执行层)
        │ task_type == LISTEN_DOWNLOAD
        │ 调用 _start_listener()
        ▼
[TaskExecutor._start_listener()]
        │ 解析 source_identifier → chat_id (通过 IdentifierService)
        │ 创建 MessageHandler(callback=_handle_listen_download, filters=chat(chat_id))
        │ 注册到 User Client: self._client.add_handler(handler)
        │ 存储 handler 引用到 Task.extra["handler"]
        ▼
[新消息到达] → _handle_listen_download() → 复用 _execute_download() 逻辑
```

**迁移步骤** (在阶段3中执行):

1. **阶段3a**: 实现 `TaskExecutor` 的监听任务分支 + Handler 生命周期管理
2. **阶段3b**: 改造 `CommandRouter.on_listen()`,将 Bot 命令入口从直接注册 Handler 改为调用 `TaskManager.create_task()`
3. **阶段3c**: 移除 `downloader.py` 中的 `add_listen_chat()` / `cancel_listen()` / `listen_download()` / `listen_forward()` 旧实现
4. **阶段3d**: 清理 `StateManager` 中的 `listen_download_chat` / `listen_forward_chat` 内存存储

**向后兼容保证**:
- Bot 命令入口 (`/listen_download`, `/listen_forward`, `/listen_info`) 的用户交互保持不变
- 现有频道监听功能正常工作(通过 IdentifierService 的 `is_private` 判断走不同路径)
- 进程重启后,SQLite 中的 running 状态监听任务自动恢复(重新注册 Handler)

---

## 五、交互设计

### 5.1 交互方式

**交互方式**: ✅ WebUI + ✅ Bot命令(监听命令迁移后支持)

> **注意**: 私聊下载/转发任务仅通过 WebUI 创建;监听任务同时支持 WebUI 和 Bot 命令(方案A迁移统一后)

### 5.2 页面集成方案

**位置**: 在现有 [tasks.html](../module/web/tasks.html) 的任务创建表单中扩展

**改动要点**:

1. **源输入框增强**
   - 现有: 仅接受 t.me 链接
   - 新增: 同时接受 username / chat_id / t.me 链接
   - 新增: "[解析]"按钮,调用 `GET /api/chats/resolve?identifier=xxx`
   - 新增: 解析按钮至少3秒防抖,避免频繁请求触发Telegram FloodWait
   - 新增: 解析成功后展示对话信息卡片

2. **目标输入框增强** (转发/监听转发时显示)
   - 同源输入框,增加解析按钮

3. **消息范围选项扩展**
   - 现有: ID范围 / 时间范围 / 多个ID / 全部
   - 新增: "最近N条" 单选 + 数字输入框

4. **媒体过滤增强**
   - 现有: 文件类型多选
   - 新增: 文件大小范围输入(最小/最大,单位可选MB/GB)

5. **任务类型扩展**
   - 现有: download / forward / upload
   - 新增: listen_download / listen_forward (频道/私聊均可选;频道监听迁移自旧架构)

### 5.3 交互流程图

#### 流程1: 创建下载任务

```
┌─────────────────────────────────────────────────────────┐
│  创建下载任务                                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  源对话: ┌──────────────────────┐ [解析]              │
│          │ @seseYunBot          │                      │
│          └──────────────────────┘                      │
│                                                          │
│  ✅ 对话信息:                                            │
│     名称: sosov2☁️精选资源                               │
│     类型: Bot                                            │
│     消息数: 9                                            │
│     媒体数: 2                                            │
│                                                          │
│  消息范围选择:                                            │
│  [●] 最近N条: ┌────┐                                     │
│               │ 10 │                                     │
│               └────┘                                     │
│  [ ] ID范围                                              │
│  [ ] 时间范围                                            │
│  [ ] 全部消息                                            │
│                                                          │
│  媒体类型过滤:                                            │
│  [●] 视频  [●] 图片  [ ] 文档  [ ] 音频                 │
│                                                          │
│  📊 预估: 2个文件, ~879 MB (示例数据)                    │
│                                                          │
│  [取消]  [创建任务]                                      │
└─────────────────────────────────────────────────────────┘
```

#### 流程2: 创建转发任务

```
┌─────────────────────────────────────────────────────────┐
│  创建转发任务                                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  源对话: ┌──────────────────────┐ [解析]              │
│          │ @seseYunBot          │                      │
│          └──────────────────────┘                      │
│                                                          │
│  目标对话: ┌──────────────────────┐ [解析]            │
│            │ @my_private_channel   │                   │
│            └──────────────────────┘                    │
│                                                          │
│  ✅ 对话信息:                                            │
│     源对话: sosov2☁️精选资源 (Bot)                       │
│     目标对话: my_private_channel (Channel)              │
│                                                          │
│  消息范围选择:                                            │
│  [ ] 最近N条                                             │
│  [●] ID范围: ┌────┐ - ┌────┐                           │
│              │ 14425 │ │ 14426 │                       │
│              └────┘   └────┘                           │
│                                                          │
│  媒体类型过滤:                                            │
│  [●] 视频                                                │
│                                                          │
│  📊 预估: 1个视频, ~879 MB (示例数据)                    │
│                                                          │
│  [取消]  [创建任务]                                      │
└─────────────────────────────────────────────────────────┘
```

#### 流程3: 创建监听任务

```
┌─────────────────────────────────────────────────────────┐
│  创建监听任务                                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  任务类型:                                               │
│  [●] 监听下载  [ ] 监听转发                              │
│                                                          │
│  源对话: ┌──────────────────────┐ [解析]              │
│          │ @seseYunBot          │                      │
│          └──────────────────────┘                      │
│                                                          │
│  ✅ 对话信息:                                            │
│     名称: sosov2☁️精选资源                               │
│     类型: Bot                                            │
│                                                          │
│  媒体类型过滤:                                            │
│  [●] 视频  [●] 图片                                      │
│                                                          │
│  💡 提示: 监听任务将持续运行,实时处理新消息              │
│                                                          │
│  [取消]  [创建监听]                                      │
└─────────────────────────────────────────────────────────┘

---

## 六、验收标准

### 6.1 功能验收标准

| ID | 功能项 | 验收标准(量化) | 测试方法 | 优先级 |
|----|-------|----------------|---------|--------|
| F01 | **Identifier解析** | 支持4种输入格式,均能正确返回chat_id和元信息;错误格式返回400+错误码 | API自动化测试 | P0 |
| F02 | **私聊下载任务** | 成功下载私聊中的任意大小媒体文件;文件hash与Telegram一致 | E2E测试 | P0 |
| F03 | **私聊转发任务** | 成功转发到目标频道;降级链(copy→file_id→download_upload)全部可用 | E2E测试 | P0 |
| F04 | **监听下载任务** | 发送新消息后30秒内开始下载;支持启动/取消操作;同一chat_id重复创建返回409 | E2E测试 | P1 |
| F05 | **监听转发任务** | 发送新消息后30秒内转发到目标频道;同一chat_id重复创建返回409 | E2E测试 | P1 |
| F06 | **消息范围-recent模式** | 正确获取最近N条消息;N=0时返回400拒绝;N>1000时截断至1000 | 功能测试 | P0 |
| F07 | **消息范围-其他模式** | id_range/date_range/all在私聊中正常工作 | 功能测试 | P0 |
| F08 | **媒体类型过滤** | 仅下载/转发匹配类型的文件;非媒体消息被跳过 | 功能测试 | P1 |
| F09 | **文件大小过滤** | min_size/max_size边界值正确;超出范围被跳过 | 功能测试 | P1 |
| F10 | **向后兼容性** | 现有频道下载/转发任务不受影响;旧版params格式仍可工作 | 回归测试 | P0 |
| F11 | **监听迁移回归** | Bot命令 `/listen_download` `/listen_forward` `/listen_info` 迁移后功能不变;频道监听正常工作 | E2E回归测试 | P0 |
| F12 | **监听任务持久化** | 进程重启后,running状态的监听任务自动恢复Handler注册 | 重启恢复测试 | P1 |
| F13 | **监听动态Item管理** | 新消息到达后生成TaskItem并持久化;同一message_id不重复生成Item | 功能测试 | P1 |

### 6.2 性能验收标准

| ID | 指标 | 目标值 | 测试条件 | 测试方法 |
|----|-----|--------|---------|---------|
| P01 | **Identifier解析延迟** | P50 < 500ms, P99 < 2000ms | 正常网络 | 性能基准测试 |
| P02 | **大文件下载** | 支持 ≥1GB 文件 | 单文件 | E2E测试 |
| P03 | **并发私聊任务** | ≥3个私聊任务同时运行 | 相同或不同对话 | 并发测试 |
| P04 | **监听消息延迟** | 新消息到达后 < 60秒内触发下载/转发 | 正常网络 | 监听测试 |

### 6.3 安全验收标准

| ID | 安全项 | 验收标准 | 测试方法 |
|----|-------|---------|---------|
| S01 | **访问权限控制** | 对未建立对话的用户返回403+ACCESS_DENIED | 权限测试 |
| S02 | **Token认证** | `/api/chats/resolve` 和 `POST /api/tasks` 均需有效Token | 安全扫描 |
| S03 | **文件完整性校验** | 下载完成后比对文件大小;不一致标记为失败 | 完整性测试 |
| S04 | **资源保护阈值** | 单任务总大小超过10GB时拒绝创建 | 阈值测试 |
| S05 | **输入消毒** | identifier参数防注入;特殊字符正确转义 | 安全扫描 |

---

## 七、实施计划

### 7.1 开发阶段划分

**阶段1: 基础能力层 (预计3天)**:
- [ ] 创建 `module/core/identifier_service.py` - Identifier统一解析服务
- [ ] 重构 `routes/tasks.py` 和 `routes/chats.py` - 使用公共解析服务替代内联实现
- [ ] 重构 `bot/command_router.py` - 使用公共解析服务替代内联实现
- [ ] 扩展 `api/models/task.py` - TaskType新增listen_*, RangeMode新增recent
- [ ] 实现 `GET /api/chats/resolve` 端点
- [ ] 编写单元测试 (覆盖率≥80%)

**阶段2: 任务管理层 (预计3天)**:
- [ ] 扩展 `TaskManager.create_task()` - 支持 `source_identifier` 参数
- [ ] 扩展 `TaskManager.create_task()` - 新增 `LISTEN_*` 任务的 chat_id+task_type 排他性校验
- [ ] 扩展 `TaskExecutor._resolve_message_ids()` - 支持 `recent` 模式
- [ ] 新增 `TaskExecutor._filter_media_messages_by_criteria()` - 媒体类型+大小过滤
- [ ] 新增 `source_type` 内部推导逻辑 - 基于 `IdentifierService.resolve()` 结果自动判断
- [ ] 编写单元测试 (覆盖率≥80%)

**阶段3: 任务执行层 + 监听迁移 (预计6天)**:
- [ ] 扩展 `TaskExecutor` - 新增 `LISTEN_DOWNLOAD` / `LISTEN_FORWARD` 分支
  - [ ] 实现 `_start_listener()` - Handler注册与引用存储
  - [ ] 实现 `_stop_listener()` - Handler移除
  - [ ] 实现 `_handle_listen_download()` / `_handle_listen_forward()` - 监听消息回调
  - [ ] 实现动态 `TaskItem` 生成与持久化
  - [ ] 实现监听任务异常恢复与重启后Handler重注册
- [ ] 集成现有 `_execute_download()` / `_execute_forward()` - 私聊/频道任务复用
- [ ] 迁移 Bot 监听命令入口:
  - [ ] 改造 `CommandRouter.on_listen()` - 改为调用 `TaskManager.create_task()`
  - [ ] 更新 `CommandRouter.listen_info()` - 从 TaskManager 查询 `LISTEN_*` 任务
  - [ ] 更新回调按钮 `REMOVE_LISTEN_*` - 触发任务取消
- [ ] 清理旧架构监听实现:
  - [ ] 移除 `downloader.py` 中的 `add_listen_chat()` / `cancel_listen()` / `listen_download()` / `listen_forward()`
  - [ ] 清理 `StateManager` 中的 `listen_download_chat` / `listen_forward_chat` 内存状态
- [ ] 编写单元测试 (覆盖率≥80%)

**阶段4: WebUI界面层 (预计3天)**:
- [ ] 扩展 `tasks.html` - 源/目标输入框增强(支持username+解析按钮)
- [ ] 扩展 `js/tasks.js` - 解析API调用+对话信息展示
- [ ] 新增消息范围 `recent` 选项UI
- [ ] 新增媒体过滤(大小范围)UI
- [ ] 新增监听任务创建表单
- [ ] 手动E2E测试

**阶段5: 集成测试与优化 (预计2天)**:
- [ ] 完整流程E2E测试(下载/转发/监听下载/监听转发)
- [ ] 向后兼容回归测试(确保现有频道任务正常)
- [ ] 性能基准测试
- [ ] 安全扫描(Token认证/输入消毒/权限控制)
- [ ] Bug修复与优化

**总计**: 约17个工作日

### 7.2 依赖关系

```
阶段1(Identifier服务) ──> 阶段2(TaskManager扩展)
                                 │
                                 ├──> 阶段3a(非监听任务执行)
                                 │         │
                                 │         └──> 阶段4a(下载/转发UI)
                                 │
                                 └──> 阶段3b(监听任务执行+旧架构迁移)
                                           │
                                           ├──> 阶段3c(移除旧监听实现)
                                           │         │
                                           │         └──> 阶段3d(清理旧状态存储)
                                           │
                                           └──> 阶段4b(监听UI)
                                                   
阶段1+2+3 ──> 阶段5(集成测试)
```

### 7.3 前置依赖

| 依赖项 | 状态 | 影响说明 |
|--------|------|---------|
| 任务模块重构完成 | ✅ 已完成 | TaskManager/TaskExecutor架构已稳定 |
| RangeMode枚举扩展 | ⏳ 本阶段包含 | 新增recent模式 |
| RepositoryManager三级降级链 | ✅ 已实现 | 转发任务可直接复用 |
| 监听迁移方案确认 | ✅ 已确认(方案A) | 旧架构监听逻辑需完整迁移至TaskExecutor,避免Handler双重注册 |

### 7.4 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| Handler双重注册(新旧架构冲突) | 高 | 高 | 采用方案A迁移统一:将旧监听逻辑完整迁移至TaskExecutor,移除downloader.py中的旧实现,确保同一User Client上只有一套Handler管理 |
| 监听任务进程中断丢失 | 中 | 高 | 监听任务状态持久化到SQLite;启动时遍历running状态监听任务重新注册Handler |
| 大量历史消息遍历性能 | 低 | 中 | recent模式限制上限1000;全量模式下分页异步获取 |
| 负数chat_id(Bot/Saved Messages) | 低 | 低 | 解析服务统一处理负数ID,明确区分Bot和用户私聊 |
| Bot命令迁移回归风险 | 中 | 中 | 迁移后保留Bot命令入口的用户交互不变;增加Bot监听命令的E2E回归测试 |

---

## 八、附录

### 8.1 技术约束与假设

**约束条件**:
1. Telegram API限制: 私聊消息获取需要已建立对话关系(用户向Bot发送过至少一条消息,或与目标用户有过聊天记录)
2. Pyrogram框架: Handler注册是全局性的,需避免与现有Bot Handler冲突;方案A确保旧监听Handler完全移除后再注册新Handler
3. 监听任务状态: `LISTEN_*` 任务为长期运行任务,合法终态为 `running` / `cancelled` / `failed`,不会进入 `completed` 状态
4. Token认证: 所有新增API端点必须经过TrustedHostMiddleware + require_token
5. User Client唯一性: 监听Handler统一注册在唯一的User Client上,不允许分散注册

**假设条件**:
1. 用户已通过Telegram客户端或Bot与目标私聊建立对话关系
2. Telegram账号具有足够的API调用额度(FloodWait处理)
3. WebUI前端保持纯HTML+Alpine.js技术栈,不引入构建工具

### 8.2 相关文档索引

| 文档 | 路径 | 关联说明 |
|------|------|---------|
| 私聊对话文件下载能力分析 | `.trae/documents/私聊对话文件下载能力分析.md` | 技术可行性前置研究 |
| 任务管理器模块设计 | `docs/module-design-task-manager.md` | TaskManager/Task架构参考 |
| 交互增强设计 | `docs/interaction-enhancement-design.md` | Bot/WebUI交互体系参考 |
| 文件管理器模块设计 | `docs/module-design-file-manager.md` | 上传/转发降级链参考 |
| 仓库管理器实现 | `module/core/repository_manager.py` | 三级去重/分发降级实现 |
| 现有API路由 | `module/api/routes/router.py` | 路由注册参考 |
| WebUI前端 | `module/web/` | 前端代码参考 |
| 旧监听实现(迁移源) | `module/downloader.py` | `add_listen_chat`/`cancel_listen`/`listen_download`/`listen_forward` 待迁移 |
| 监听状态管理(迁移源) | `module/bot/state_manager.py` | `listen_download_chat`/`listen_forward_chat` 待清理 |
| Bot命令路由(迁移源) | `module/bot/command_router.py` | `on_listen`/`listen_info` 待改造 |

### 8.3 术语表

| 术语 | 定义 |
|------|------|
| **Identifier** | 泛指可用于定位对话的字符串,包括username、数字ID、t.me链接 |
| **ResolvedChat** | 解析后的标准化对话信息对象,包含chat_id及元信息 |
| **私聊对话** | Telegram中type为private/bot的对话,区别于公开channel/group |
| **监听任务** | 通过注册NewMessage Handler实时处理新消息的任务类型 |
| **降级链** | 转发失败时的多级备选方案,按效率从高到低排列 |
| **迁移统一(方案A)** | 将旧架构监听逻辑完整迁移至新架构TaskExecutor,消除双架构并存,确保Handler统一管理 |

---

**PRD文档结束** | 版本: v2.3 | 状态: 最终版 | 下一步: 按TDD方法启动阶段1实施
