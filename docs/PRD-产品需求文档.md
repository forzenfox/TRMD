# TRMD 产品需求文档 (PRD)

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **文档版本**: v3.0  
> **创建日期**: 2026-06-18  
> **更新日期**: 2026-07-20  
> **作者**: SOLO / AI Assistant  
> **状态**: 持续更新

---

## 更新日志

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| v3.0 | 2026-07-20 | 合并仓库模式 PRD(v2.0) 和私聊按用户名下载 PRD(v2.3) 为统一文档，新增更新日志 | AI Assistant |
| v2.3 | 2026-07-03 | 私聊PRD技术评审定稿：明确监听任务状态机，补充动态Item管理规则，新增chat_id重复监听409排他校验 | AI Assistant |
| v2.2 | 2026-07-03 | 私聊PRD技术评审修订：采用方案A迁移统一监听架构，补充IdentifierService复用关系 | AI Assistant |
| v2.1 | 2026-07-02 | 私聊PRD新增仓库备份配置设计：全局配置 + 任务级覆盖 | AI Assistant |
| v2.0 | 2026-07-02 | 仓库PRD终版；私聊PRD架构重构：对齐TaskManager/TaskExecutor架构 | SOLO / AI Assistant |
| v1.1 | 2026-07-01 | 私聊PRD初版：仅支持WebUI，仅支持Username直接指定 | AI Assistant |
| v1.0 | 2026-06-18 | 仓库PRD初版；私聊PRD初始文档 | SOLO / AI Assistant |

---

# 第一部分：仓库模式

## 一、需求概述

### 1.1 背景

当前项目在处理文件时存在以下问题：

| 问题 | 描述 |
|------|------|
| **重复下载** | 同一文件多次处理时，每次都从源频道重新下载 |
| **重复上传** | 同一文件上传到不同目标频道时，每次都重新上传 |
| **本地存储占用** | 下载的文件长期占用本地磁盘空间 |
| **无去重机制** | 无法识别已处理过的文件 |

### 1.2 解决方案

引入 **TG 文件仓库模式**：

```
┌──────────────────────────────────────────────────────────────────┐
│                      仓库模式架构                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   源频道 ──下载──> 本地 ──上传──> 仓库频道 ──分发──> 目标频道       │
│                      │              │                            │
│                      └──删除──<─────┘                            │
│                                                                  │
│   关键特性：                                                      │
│   1. 所有文件统一上传到仓库频道，获取 file_id / file_unique_id     │
│   2. 后续分发使用 copy_message（默认）或 file_id，无需重新上传      │
│   3. 本地文件上传后立即删除，节省磁盘空间                           │
│   4. 数据表实时记录文件信息，避免频繁 API 调用                      │
│   5. 三级去重机制：source → file_unique_id → 内容哈希              │
│                                                                  │
│   设计约束：                                                      │
│   - 仓库模式所有操作统一由 User Client 执行                        │
│   - file_id 不保证永久有效，通过三级回退机制处理                    │
│   - 使用 file_unique_id 作为去重键（跨客户端稳定）                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 核心目标

| 目标 | 指标 |
|------|------|
| **减少重复下载** | 已处理文件不再重复下载（三级去重） |
| **减少重复上传** | 同一文件上传到多个目标时，只上传一次到仓库 |
| **节省本地存储** | 上传完成后立即删除本地文件 |
| **快速分发** | 使用 copy_message / file_id 分发，秒级完成 |

---

## 二、功能需求

### 2.1 仓库模式配置

#### 2.1.1 配置项

项目使用单一配置文件 `config.yaml`，仓库配置作为独立 section：

```yaml
# config.yaml

# 身份配置
credential:
  api_id: null
  api_hash: null
  bot_token: null

# 网络配置
proxy:
  enable_proxy: null
  scheme: null
  hostname: null
  port: null
  username: null
  password: null

# 任务配置
task:
  links: null
  save_directory: null
  temp_directory: null
  download_type: null
  is_shutdown: null
  max_tasks:
    download: null
    upload: null
  max_retries:
    download: null
    upload: null

# 行为偏好
preference:
  notice: true
  forward_type:
    video: true
    photo: true
    audio: true
    document: true
    voice: true
    text: true
    animation: true
    video_note: true
  upload:
    download_upload: true
    delete: false                    # 上传后是否删除本地文件（仓库模式复用此配置）
  export_table:
    link: false
    count: false
    upload: false

# 日志配置
log:
  file_log_level: INFO
  console_log_level: WARNING

# 仓库配置（新增）
repository:
  # 是否启用仓库模式（默认开启）
  enabled: true

  # 仓库频道 ID（必填）
  # 支持格式：
  #   - 频道 ID：-1001234567890
  #   - 频道用户名：@my_repository_channel
  #   - 频道链接：https://t.me/my_repository_channel
  #   - 邀请链接：https://t.me/+AbCdEfGhIjKlMnN
  chat_id: ""

  # 是否启用自动同步（可选，用于查漏补缺）
  auto_sync_enabled: false

  # 自动同步间隔（分钟）
  auto_sync_interval_minutes: 60
```

> **注意**：已删除原 `repository.delete_after_upload` 配置项，统一使用 `preference.upload.delete` 控制上传后是否删除本地文件。

#### 2.1.2 获取仓库频道 ID 的方法

| 方法 | 步骤 | 适用场景 |
|------|------|----------|
| **方法1：使用频道用户名** | 1. 创建私有频道<br>2. 设置频道用户名（如 `@my_repo`）<br>3. 配置 `chat_id: "@my_repo"` | 推荐，最简单 |
| **方法2：使用频道链接** | 1. 创建私有频道<br>2. 复制频道公开链接<br>3. 配置 `chat_id: "https://t.me/my_repo"` | 推荐 |
| **方法3：使用邀请链接** | 1. 创建私有频道<br>2. 生成邀请链接（如 `https://t.me/+AbCdEf`）<br>3. 配置 `chat_id: "https://t.me/+AbCdEf"`<br>4. 程序自动解析为频道 ID | 私有频道无用户名时 |
| **方法4：使用频道 ID** | 1. 创建私有频道<br>2. 使用 Bot 命令 `/get_chat_id` 获取 ID<br>3. 配置 `chat_id: -1001234567890` | 高级用户 |

**辅助功能**：
- 提供 Bot 命令 `/setup_repository`，引导用户完成仓库频道配置
- 自动验证频道权限（BOT 是否为管理员）
- 自动解析邀请链接获取频道 ID

### 2.2 文件处理流程

#### 2.2.1 下载流程（含三级去重）

```
┌──────────────────────────────────────────────────────────────────┐
│                      下载流程（三级去重）                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 接收下载任务                                                  │
│     ↓                                                            │
│  2. Level 1：查询 repository_sources                              │
│     检查 source_chat_id + source_message_id 是否已处理             │
│     ↓                                                            │
│     ├─ 命中 → 完全跳过，直接返回已有 file_id                      │
│     │                                                            │
│     └─ 未命中                                                    │
│         ↓                                                        │
│  3. 获取消息元数据（get_messages，不下载文件内容）                  │
│     ↓                                                            │
│  4. Level 2：查询 repository_files                                │
│     检查 file_unique_id 是否已存在                                 │
│     ↓                                                            │
│     ├─ 命中 → 跳过下载和上传，仅新增 source 映射记录               │
│     │                                                            │
│     └─ 未命中                                                    │
│         ↓                                                        │
│  5. 下载文件到本地临时目录                                         │
│     ↓                                                            │
│  6. 计算内容哈希（SHA256）                                        │
│     ↓                                                            │
│  7. Level 3：查询 repository_files.content_hash                   │
│     ↓                                                            │
│     ├─ 命中 → 删除本地文件 + 跳过上传 + 新增 source 映射记录       │
│     │                                                            │
│     └─ 未命中                                                    │
│         ↓                                                        │
│  8. 复用现有上传器上传到仓库频道                                   │
│     ↓                                                            │
│  9. 上传成功回调：写入 repository_files + repository_sources       │
│     ↓                                                            │
│  10. 根据 preference.upload.delete 决定是否删除本地文件            │
│     ↓                                                            │
│  11. 返回 file_unique_id 供后续使用                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### 2.2.2 分发流程（含降级链）

```
┌──────────────────────────────────────────────────────────────────┐
│                      分发流程（含降级链）                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 接收分发任务（目标频道 ID）                                    │
│     ↓                                                            │
│  2. 从数据表查询仓库消息位置（repo_chat_id, repo_message_id）      │
│     ↓                                                            │
│  3. 默认方式：copy_message                                        │
│     await client.copy_message(                                   │
│         chat_id=target_chat_id,                                  │
│         from_chat_id=repo_chat_id,                               │
│         message_id=repo_message_id                               │
│     )                                                            │
│     ↓                                                            │
│     ├─ 成功 → 记录分发日志（method=copy_message）                 │
│     │                                                            │
│     └─ 失败                                                      │
│         ↓                                                        │
│  4. 降级方式：从仓库消息刷新 file_id → file_id_send               │
│     ↓                                                            │
│     ├─ 成功 → 记录分发日志（method=file_id_send）                 │
│     │                                                            │
│     └─ 失败                                                      │
│         ↓                                                        │
│  5. 最终降级：重新下载 → 重新上传 → 分发                          │
│                                                                  │
│  优势：                                                          │
│  - copy_message 无需根据 file_type 选择 send 方法，代码更简洁     │
│  - copy_message 不依赖 file_id，避免过期问题                      │
│  - 仓库频道文件不受源频道受限转发限制                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### 2.2.3 file_id 三级回退机制

分发文件时，`file_id` 可能已过期，采用三级回退：

```
1. 尝试使用数据库中存储的 file_id
   ↓ 成功 → 完成
   ↓ 失败（Wrong file identifier）

2. 从仓库频道重新读取消息，获取新鲜 file_id
   ↓ 成功 → 更新数据库中的 file_id，完成分发
   ↓ 失败（消息被删除）

3. 降级：从源频道重新下载 → 上传到仓库 → 获取新 file_id → 分发
```

### 2.3 数据表设计

> 所有仓库相关表加入现有 `trmd.db` 数据库文件，统一使用 WAL 模式 + foreign_keys + busy_timeout=10000。

#### 2.3.1 文件记录表 `repository_files`

```sql
CREATE TABLE repository_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Telegram 文件标识
    file_unique_id TEXT UNIQUE NOT NULL,    -- 去重键（跨客户端稳定）
    file_id TEXT NOT NULL,                  -- 分发用（可能过期，通过三级回退刷新）

    -- 内容去重
    content_hash TEXT,                      -- SHA256 哈希（Level 3 去重键）

    -- 文件元数据
    file_size INTEGER NOT NULL,             -- 文件大小（字节）
    file_type TEXT NOT NULL,                -- photo/video/document/audio/animation
    mime_type TEXT,                         -- MIME 类型
    file_name TEXT,                         -- 文件名

    -- 仓库位置（file_id 刷新锚点）
    repository_chat_id INTEGER NOT NULL,    -- 仓库频道 ID
    repository_message_id INTEGER NOT NULL, -- 仓库中的消息 ID

    -- 时间戳
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    -- 状态
    status TEXT DEFAULT 'active'            -- active/deleted/invalid
);

-- 核心索引
CREATE INDEX idx_repo_files_file_id ON repository_files(file_id);
CREATE INDEX idx_repo_files_content_hash ON repository_files(content_hash);
CREATE INDEX idx_repo_files_chat_msg ON repository_files(repository_chat_id, repository_message_id);
```

#### 2.3.2 来源映射表 `repository_sources`

> 一个文件可对应多个源消息（不同频道/不同消息可能包含同一文件），支持 1:N 关系。

```sql
CREATE TABLE repository_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    file_unique_id TEXT NOT NULL,           -- 关联 repository_files
    source_chat_id INTEGER NOT NULL,        -- 源频道 ID
    source_message_id INTEGER NOT NULL,     -- 源消息 ID
    source_link TEXT,                       -- 原始链接（可选显示字段）

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source_chat_id, source_message_id),
    FOREIGN KEY (file_unique_id) REFERENCES repository_files(file_unique_id) ON DELETE CASCADE
);

CREATE INDEX idx_repo_sources_file_unique_id ON repository_sources(file_unique_id);
```

#### 2.3.3 分发记录表 `file_distributions`

```sql
CREATE TABLE file_distributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    file_unique_id TEXT NOT NULL,           -- 关联 repository_files
    target_chat_id INTEGER NOT NULL,        -- 目标频道 ID
    target_message_id INTEGER,              -- 目标频道的消息 ID

    -- 分发方式（记录实际使用的方式，便于问题排查）
    method TEXT NOT NULL,                   -- copy_message / file_id_send

    -- 关联任务
    task_id TEXT,                           -- 关联 TaskManager.tasks 表

    -- 时间戳
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (file_unique_id) REFERENCES repository_files(file_unique_id) ON DELETE CASCADE
);

CREATE INDEX idx_distributions_file_unique_id ON file_distributions(file_unique_id);
CREATE INDEX idx_distributions_task_id ON file_distributions(task_id);
```

### 2.4 数据同步策略

#### 2.4.1 主逻辑：实时写入

**原则**：上传到仓库成功后，通过回调立即写入数据表。

**与现有上传器的集成**：复用 `TelegramUploader` 的上传机制，在上传成功回调中写入仓库记录。

```python
async def on_repository_upload_success(self, message, source_chat_id, source_message_id):
    """上传成功回调：写入仓库记录"""

    # 获取文件信息
    media = message.photo or message.video or message.document or message.audio or message.animation
    file_unique_id = media.file_unique_id
    file_id = media.file_id

    # 计算内容哈希
    content_hash = self._compute_content_hash(local_file_path)

    # 写入 repository_files
    self.db.execute("""
        INSERT INTO repository_files (
            file_unique_id, file_id, content_hash, file_size, file_type,
            repository_chat_id, repository_message_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
    """, (file_unique_id, file_id, content_hash, ...))

    # 写入 repository_sources
    self.db.execute("""
        INSERT INTO repository_sources (
            file_unique_id, source_chat_id, source_message_id
        ) VALUES (?, ?, ?)
    """, (file_unique_id, source_chat_id, source_message_id))
```

#### 2.4.2 辅助逻辑：定时同步（可选）

**用途**：查漏补缺，处理异常情况（如程序崩溃导致数据不一致）。

**触发条件**：
- 配置 `repository.auto_sync_enabled: true`
- 默认关闭，用户可按需开启

**同步逻辑**：
```python
async def incremental_sync(self):
    """增量同步：仅扫描上次同步后的新消息"""

    # 获取上次同步的最大 message_id
    last_message_id = self._get_last_synced_message_id()

    # 扫描新消息
    async for message in self.client.get_chat_history(
        chat_id=self.repository_chat_id,
        offset_id=last_message_id,
        reverse=False
    ):
        # 检查是否已存在
        if not self._exists_in_db(message.id):
            # 写入数据表
            self._insert_file_record(message)
```

### 2.5 同步日志评估

#### 评估结论：**不需要**

| 因素 | 分析 |
|------|------|
| **项目性质** | 个人项目，数据量有限 |
| **数据重要性** | 文件记录可从仓库频道恢复 |
| **复杂度** | 增加同步日志会增加代码复杂度 |
| **收益** | 低，问题排查可通过日志文件完成 |

**替代方案**：
- 使用标准日志（`logging`）记录关键操作
- 异常时输出详细错误信息到控制台和日志文件

---

## 三、非功能需求

### 3.1 性能要求

| 指标 | 目标 | 前提条件 |
|------|------|----------|
| **文件查询** | < 0.1 秒 | 数据量 < 50 万条，SQLite 索引命中 |
| **分发速度** | < 5 秒 | 不触发 FloodWait，网络正常 |
| **数据表写入** | < 0.1 秒 | SQLite WAL 模式，无并发写锁竞争 |

> SQLite 统一启用 WAL 模式，避免读写互锁。

### 3.2 兼容性要求

| 要求 | 说明 |
|------|------|
| **向后兼容** | 原有下载/上传功能保持不变 |
| **降级策略** | 仓库模式失败时，降级为直接上传 |
| **配置灵活** | 可通过配置关闭仓库模式 |

### 3.3 安全要求

| 要求 | 说明 |
|------|------|
| **仓库频道权限** | BOT 必须是管理员，拥有发送消息权限 |
| **私有频道** | 建议仓库频道设为私有，仅 BOT 可见 |

---

## 四、实现计划

### 4.1 模块划分

| 模块 | 职责 | 说明 |
|------|------|------|
| `RepositoryManager` | 仓库编排层（判断是否走仓库、查询记录、分发决策） | 不直接操作文件和 Telegram API |
| `RepositoryDB` | 数据表操作（增删改查） | 管理 `repository_files`、`repository_sources`、`file_distributions` 表 |
| `RepositorySync` | 定时同步（可选功能） | 查漏补缺 |
| `FileManager` | 文件操作（上传、下载、删除） | 不感知仓库概念 |
| `TelegramUploader` | 实际上传 | 通过回调通知仓库记录写入 |

**调用关系**：`RepositoryManager` → 调用 `FileManager`/`Uploader` 执行操作 → 回调写入 `RepositoryDB`

### 4.2 实施阶段

| 阶段 | 任务 | 优先级 | 测试要求 |
|------|------|--------|----------|
| **Phase 1** | 数据表创建、基础配置项 | P0 | `test_repository_db.py`：表创建、CRUD、索引验证 |
| **Phase 2** | 上传到仓库、实时写入数据表 | P0 | `test_repository_upload.py`：上传 → 记录写入 → 本地删除 |
| **Phase 3** | 使用 copy_message 分发到目标频道 | P0 | `test_repository_distribute.py`：copy_message 分发、file_id_send 降级测试 |
| **Phase 4** | 三级去重（source → file_unique_id → 内容哈希） | P1 | `test_repository_dedup.py`：三级去重流程、source 映射 |
| **Phase 5** | 定时同步（可选功能） | P2 | `test_repository_sync.py`：增量同步、异常恢复 |
| **Phase 6** | Bot 命令 `/setup_repository` | P2 | `test_bot_setup_repository.py`：Bot 命令交互流程 |

### 4.3 文件结构（最终实现）

```
module/core/
├── repository/
│   ├── manager.py              # RepositoryManager - 仓库编排器
│   ├── db.py                   # RepositoryDB - 数据表操作
│   ├── sync.py                 # RepositorySync - 定时同步
│   └── models.py               # 仓库相关 SQLModel 表模型
```

---

## 五、API 设计

### 5.1 RepositoryManager 接口

```python
class RepositoryManager:
    """仓库频道编排器（不直接操作文件和 Telegram API）"""

    async def should_use_repository(self) -> bool:
        """判断是否应使用仓库模式"""
        pass

    async def check_dedup(
        self,
        source_chat_id: int,
        source_message_id: int,
        file_unique_id: Optional[str] = None,
        content_hash: Optional[str] = None
    ) -> Optional[dict]:
        """
        三级去重检查

        Args:
            source_chat_id: 源频道 ID
            source_message_id: 源消息 ID
            file_unique_id: 文件唯一标识（Level 2）
            content_hash: 内容哈希（Level 3）

        Returns:
            已存在的文件记录，或 None（未命中去重）
        """
        pass

    async def distribute_to_target(
        self,
        file_unique_id: str,
        target_chat_id: int,
        caption: Optional[str] = None
    ) -> int:
        """
        分发到目标频道（默认 copy_message，降级 file_id_send）

        Args:
            file_unique_id: 文件唯一标识
            target_chat_id: 目标频道 ID
            caption: 可选说明文字

        Returns:
            目标频道的消息 ID
        """
        pass

    async def on_upload_success(
        self,
        message,
        source_chat_id: int,
        source_message_id: int,
        content_hash: Optional[str] = None
    ) -> None:
        """
        上传成功回调：写入仓库记录

        Args:
            message: 上传后的消息对象
            source_chat_id: 源频道 ID
            source_message_id: 源消息 ID
            content_hash: 内容哈希
        """
        pass
```

### 5.2 RepositoryDB 接口

```python
class RepositoryDB:
    """仓库数据表操作"""

    def get_file_by_source(self, source_chat_id: int, source_message_id: int) -> Optional[dict]:
        """Level 1：根据源消息查询文件记录"""
        pass

    def get_file_by_unique_id(self, file_unique_id: str) -> Optional[dict]:
        """Level 2：根据 file_unique_id 查询文件记录"""
        pass

    def get_file_by_content_hash(self, content_hash: str) -> Optional[dict]:
        """Level 3：根据内容哈希查询文件记录"""
        pass

    def insert_file_record(self, file_unique_id: str, file_id: str, content_hash: Optional[str],
                           file_size: int, file_type: str, repo_chat_id: int, repo_message_id: int,
                           **kwargs) -> int:
        """插入文件记录"""
        pass

    def insert_source_mapping(self, file_unique_id: str, source_chat_id: int,
                              source_message_id: int, source_link: Optional[str] = None) -> int:
        """插入来源映射"""
        pass

    def update_file_id(self, file_unique_id: str, new_file_id: str) -> None:
        """更新 file_id（三级回退时刷新）"""
        pass

    def insert_distribution(self, file_unique_id: str, target_chat_id: int,
                            method: str, task_id: Optional[str] = None,
                            target_message_id: Optional[int] = None) -> int:
        """插入分发记录"""
        pass
```

### 5.3 配置接口

```python
class ConfigManager:
    """配置管理器（扩展）"""

    def get_repository_config(self) -> dict:
        """获取仓库配置"""
        pass

    def set_repository_chat_id(self, chat_id: str) -> bool:
        """设置仓库频道 ID"""
        pass

    def validate_repository_config(self) -> tuple[bool, str]:
        """验证仓库配置"""
        pass
```

---

## 六、降级策略

### 6.1 降级场景

| 场景 | 降级方式 |
|------|----------|
| 仓库频道未配置 | 直接上传到目标频道 |
| 仓库频道权限不足 | 直接上传到目标频道，输出警告 |
| 上传到仓库失败 | 直接上传到目标频道 |
| 数据表写入失败 | 继续上传，记录错误日志 |
| 仓库频道被删除/封禁 | 降级为直接上传，输出错误日志，建议用户重新配置 |
| Bot 被移出仓库频道 | 降级为直接上传，输出错误日志，建议用户重新配置 |
| 数据库文件损坏 | 降级为直接上传，提示用户运行同步恢复 |
| `file_id` 失效 | 从仓库频道重新获取 `file_id`，若消息也被删除则重新上传 |
| 并发写入冲突 | SQLite WAL 模式 + 写入重试（3次） |

### 6.2 降级逻辑

```python
async def upload_with_fallback(self, file_path: str, target_chat_id: int):
    """带降级的上传逻辑"""

    # 检查仓库模式是否启用
    if not self.repository_enabled:
        return await self.direct_upload(file_path, target_chat_id)

    try:
        # 尝试仓库模式：复用现有上传器上传到仓库频道
        result = await self.uploader.create_upload_task(
            file_path=file_path,
            target_chat_id=self.repository_chat_id
        )
        # 上传成功回调中已写入仓库记录
        return result

    except Exception as e:
        log.warning(f"仓库模式失败，降级为直接上传: {e}")
        # 降级为直接上传
        return await self.direct_upload(file_path, target_chat_id)
```

---

## 七、测试计划

### 7.1 测试用例

| 用例 | 输入 | 预期输出 |
|------|------|----------|
| 首次上传文件 | 新文件 | 上传到仓库，repository_files + repository_sources 新增记录 |
| Level 1 去重 | 已存在 source_chat_id + source_message_id | 完全跳过，直接返回已有 file_id |
| Level 2 去重 | 不同消息但相同 file_unique_id | 跳过下载和上传，仅新增 source 映射 |
| Level 3 去重 | 不同 file_unique_id 但相同内容哈希 | 删除本地文件，跳过上传，新增 source 映射 |
| 分发到多个目标 | 同一 file_unique_id | 使用 copy_message 分发 |
| copy_message 降级 | copy_message 失败 | 降级为 file_id_send |
| file_id 失效回退 | file_id 过期 | 从仓库消息刷新 file_id |
| 仓库模式降级 | 仓库频道未配置 | 直接上传到目标频道 |
| 邀请链接解析 | 邀请链接 | 正确解析为频道 ID |

### 7.2 验证指标

| 指标 | 验证方法 |
|------|----------|
| 减少重复下载 | 对比开启/关闭仓库模式的 API 调用次数 |
| 分发速度 | 测量使用 copy_message / file_id 分发的耗时 |
| 数据一致性 | 对比数据表与仓库频道实际消息数 |
| 去重准确性 | 验证三级去重各阶段的命中率 |

---

# 第二部分：私聊对话文件操作

## 一、功能背景与价值

### 1.1 现状问题

**当前限制**：
- 项目仅支持通过公开链接（https://t.me/channel_name）访问频道/群组
- 不支持访问私聊对话（private chat）中的文件操作
- 私聊对话没有公开链接，无法通过现有机制访问
- 现有监听功能仅通过 Bot 命令操作，状态存储在内存中，进程重启后丢失
- 监听逻辑散落在旧架构中，与新架构不统一

**用户痛点**：

| 场景 | 痛点 | 影响 |
|------|------|------|
| **Bot资源收集** | Bot发送的文件无法批量下载/转发，只能手动逐个操作 | 效率低，耗时 |
| **私聊文件整理** | 与朋友/同事交换的文件无法统一管理 | 文件分散，难以整理 |
| **Saved Messages** | 自己保存的重要文件无法批量导出/转发 | 无法备份整理 |
| **无链接对话** | 部分用户/Bot没有公开链接，无法访问 | 功能缺失 |

### 1.2 可行性验证结果

**测试结论**：
- ✅ **通过chat_id可以访问私聊对话**
- ✅ **可以获取私聊历史消息**
- ✅ **可以下载私聊中的媒体文件**
- ✅ **文件完整性验证通过**
- ✅ **通过username可以解析chat_id**

**技术可行性**：100%可行，已通过实际下载验证

### 1.3 功能价值

**核心价值**：
- 解锁私聊对话文件操作能力，扩展项目覆盖范围
- 支持完整的任务类型（下载、转发、监听下载、监听转发）
- 仅通过Username即可访问，无需公开链接
- 提升用户效率，无需手动逐个操作文件

**预期收益**：
- 功能覆盖率：从"仅公开频道/群组"扩展到"所有对话类型"
- 任务类型：从"下载+转发"扩展到"下载+转发+监听下载+监听转发"（含私聊支持）
- 监听架构：从"Bot命令+内存状态"统一到"TaskManager/TaskExecutor+SQLite持久化"
- 用户效率：从"手动逐个操作"提升到"批量自动处理"
- 场景支持：新增Bot资源收集、私聊文件整理、个人备份、实时监听等场景

---

## 二、用户场景与需求

### 2.1 目标用户

| 用户类型 | 典型场景 | 频次 |
|---------|---------|------|
| **Bot用户** | 收集Bot发送的资源文件（下载/转发） | 高频 |
| **私聊用户** | 整理与朋友/同事交换的文件 | 中频 |
| **个人用户** | 批量导出Saved Messages中的文件 | 低频 |

### 2.2 典型场景

#### 场景1：Bot资源批量下载

```
用户A: "我订阅了一个资源Bot(@seseYunBot)，它每天发送精选视频。
       我想把最近一个月的视频全部下载到本地整理，
       但现在只能手动逐个保存，太麻烦了。"
```

**需求**：
- 输入Bot username(@seseYunBot)
- 选择时间范围（最近一个月）
- 批量下载所有视频文件

#### 场景2：Bot资源转发

```
用户B: "我订阅了一个资源Bot(@seseYunBot)，它每天发送精选视频。
       我想把这些视频转发到我的私有频道保存，
       但现在只能手动逐个转发，效率很低。"
```

**需求**：
- 输入源Bot username(@seseYunBot)
- 输入目标频道链接或username
- 选择消息范围
- 批量转发所有文件

#### 场景3：监听Bot新资源

```
用户C: "我希望实时监听@seseYunBot的新消息，
       一旦它发送新视频就自动下载到本地，
       这样就不用手动查看和保存了。"
```

**需求**：
- 输入Bot username(@seseYunBot)
- 启动监听任务
- 实时自动下载新发送的文件

#### 场景4：监听转发到私有频道

```
用户D: "我希望实时监听@seseYunBot的新消息，
       一旦它发送新视频就自动转发到我的私有频道，
       这样就能自动同步收藏了。"
```

**需求**：
- 输入源Bot username(@seseYunBot)
- 输入目标频道链接或username
- 启动监听任务
- 实时自动转发新发送的文件

---

## 三、功能设计方案

### 3.1 功能架构

**新增能力矩阵**（基于现有架构扩展）：

| 维度 | 现有能力 | 新增能力 | 扩展方式 |
|------|---------|---------|---------|
| **对话类型** | 公开频道/群组 | 私聊对话（Bot/用户/Saved） | 扩展输入格式 |
| **访问方式** | 公开链接（t.me） | Username/chat_id/t.me链接 | 统一Identifier解析服务 |
| **任务类型** | DOWNLOAD/FORWARD/UPLOAD | + LISTEN_DOWNLOAD/LISTEN_FORWARD | 扩展TaskType枚举；LISTEN_*同时覆盖频道和私聊，统一迁移旧架构监听逻辑 |
| **消息范围** | date_range/id_range/multiple_ids/all | + recent | 扩展RangeMode枚举 |

**设计原则**：
- ✅ **复用现有入口**：不新增独立方法/API，扩展现有接口
- ✅ **统一解析逻辑**：消除三处重复实现，建立公共解析服务
- ✅ **执行逻辑共享**：私聊与频道的下载/转发使用相同执行路径
- ⚠️ **Bot监听命令迁移**：Bot的监听命令迁移至 TaskExecutor 统一管理（方案A：迁移统一）
- ❌ **不支持对话列表选择**：仅支持Username直接指定

### 3.2 核心功能模块

#### 模块1：Identifier统一解析服务

**定位**：替代现有三处重复的 `_resolve_chat_id()` 实现，提供统一的标识符解析能力

**与现有 `parse_link` 的关系**：
- `parse_link` 负责链接级解析，返回 `chat_id` + `comment_id` + `topic_id`，被旧架构大量使用，保留不合并
- `extract_info_from_link` 负责链接格式提取，IdentifierService 内部复用此函数进行 t.me 链接的格式检测
- `_resolve_chat_id`（API路由中）负责标识符→chat_id 转换，将被 IdentifierService 替代

**职责**：
- 接受 username / chat_id / t.me链接 三种输入格式
- 返回标准化的 chat_id + 对话元信息
- 提供输入格式自动检测与规范化
- 内部复用 `extract_info_from_link()` 进行链接格式提取

**支持的输入格式**：

| 格式 | 示例 | 说明 |
|------|------|------|
| 纯数字ID | `8288406549` | 直接作为chat_id返回 |
| @username | `@seseYunBot` | 去掉@前缀后调用get_chat |
| 纯username | `seseYunBot` | 直接调用get_chat |
| t.me链接 | `https://t.me/seseYunBot` | 提取username后调用get_chat |

**输出结构**：
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

**错误处理规范**：

| 错误场景 | HTTP状态码 | 错误码 |
|---------|-----------|--------|
| 无效输入格式 | 400 | `INVALID_IDENTIFIER` |
| 不存在的用户名 | 404 | `USER_NOT_FOUND` |
| 无对话权限 | 403 | `ACCESS_DENIED` |
| 网络超时 | 504 | `RESOLVE_TIMEOUT` |
| API限流 | 429 | `RATE_LIMITED` |

#### 模块2：TaskType枚举扩展

**现有类型**：
```python
class TaskType(Enum):
    DOWNLOAD = "download"
    FORWARD = "forward"
    UPLOAD = "upload"
```

**新增类型**：
```python
class TaskType(Enum):
    DOWNLOAD = "download"                 # 现有：频道/私聊下载
    FORWARD = "forward"                   # 现有：频道/私聊转发
    UPLOAD = "upload"                     # 现有：上传
    LISTEN_DOWNLOAD = "listen_download"   # 新增：监听并下载
    LISTEN_FORWARD = "listen_forward"     # 新增：监听并转发
```

**说明**：
- `DOWNLOAD` 和 `FORWARD` 类型同时支持公开频道和私聊对话，通过内部推导的 `source_type` 区分
- 新增的 `LISTEN_*` 类型用于实时监听类任务
- `LISTEN_*` 为长期运行任务，状态流转为 `pending → queued → running → cancelled/failed`，**不会进入 `completed` 状态**

#### 模块3：RangeMode枚举扩展

**现有模式**：
```python
RangeMode = Literal["date_range", "id_range", "multiple_ids", "all"]
```

**扩展后**：
```python
RangeMode = Literal["date_range", "id_range", "multiple_ids", "all", "recent"]
```

**新增 `recent` 模式参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `recent_count` | int | 是（recent模式） | 最近N条消息（N > 0，上限1000） |

**校验规则**：
1. **API层**：`recent_count` 必须大于0，否则返回 400 `INVALID_RECENT_COUNT`
2. **TaskManager层**：若 `recent_count > 1000`，自动截断至1000，并记录 warning 日志
3. 上限1000用于防止一次性拉取过多历史消息导致性能问题或FloodWait

#### 模块4：Task.create_task() 参数扩展

**扩展策略**：通过 `params` 字典传递私聊相关参数，不修改 Task dataclass 结构

**params 新增字段定义**：

| 字段 | 类型 | 必填 | 适用任务类型 | 说明 |
|------|------|------|-------------|------|
| `source_identifier` | str | **是**（私聊模式） | 全部 | 源对话标识符（username/chat_id/链接） |
| `target_identifier` | str | 是（FORWARD/LISTEN_FORWARD） | FORWARD/LISTEN_FORWARD | 目标对话标识符 |
| `media_types` | list[str] | 否 | 全部 | 媒体类型过滤 |
| `min_size` | int | 否 | 非监听任务 | 最小文件大小（字节） |
| `max_size` | int | 否 | 非监听任务 | 最大文件大小（字节） |
| `recent_count` | int | 是（recent模式） | 非监听任务 | 最近N条消息 |
| `enable_repository_backup` | bool | 否 | DOWNLOAD/LISTEN_DOWNLOAD | 是否备份到仓库频道；null=继承全局配置 |

> **注**：`source_type`（`channel`/`private`）不再作为 `params` 暴露字段，由系统内部通过 `IdentifierService.resolve()` 的结果自动推导，存储在 `Task.extra` 中供执行层使用。

**向后兼容性**：
- 当 `params` 包含 `chat_id`（t.me链接格式）→ 走原有频道逻辑（无破坏性变更）
- 当 `params` 包含 `source_identifier` → 走新的私聊解析逻辑
- 两者互斥，优先检查 `source_identifier`

**任务创建排他性校验**：

对于 `LISTEN_DOWNLOAD` / `LISTEN_FORWARD` 任务，`TaskManager.create_task()` 需检查同一 `chat_id` + `task_type` 组合是否已存在 `running` 或 `pending` 状态的任务：
- 若存在，抛出 `TaskConflictError`，API返回 409 `LISTEN_ALREADY_EXISTS`
- 此规则避免同一对话上重复注册 Handler 导致消息重复处理

#### 模块5：监听任务动态Item管理

**适用任务类型**：`LISTEN_DOWNLOAD` / `LISTEN_FORWARD`

**设计原则**：监听任务创建时 `items=[]`，新消息到达后动态生成 `TaskItem`，通过现有 `TaskManager` 接口统一持久化。

**动态Item生成规则**：

| 字段 | 取值规则 |
|------|---------|
| `item.id` | 由 `TaskManager` 统一生成的唯一ID |
| `item.task_id` | 所属监听任务的 `task_id` |
| `item.source_id` | 触发监听的消息ID（`message.id`） |
| `item.source_link` | 私聊消息无公开链接，此处为 `None` 或空字符串 |
| `item.status` | `pending → running → completed/failed/skipped` |
| `item.extra["message_id"]` | 原始消息ID |
| `item.extra["chat_id"]` | 源对话 `chat_id` |

**统计更新规则**：
- 不预先设置 `Task.total_count`
- 每处理一条消息，`total_count` 自动 `+1`
- 成功/失败/跳过时，对应计数自动 `+1`
- 通过 `TaskManager.add_items()` 新增Item，通过 `TaskManager.update_item_status()` 更新状态

#### 模块6：仓库备份配置

**设计原则**：全局配置 + 任务级覆盖，两层控制机制

**配置层级**：

| 层级 | 配置项 | 位置 | 默认值 | 说明 |
|------|--------|------|--------|------|
| **全局配置** | `repository.auto_backup_downloads` | config.yaml | `true` | 所有下载任务的默认备份行为 |
| **任务级配置** | `params.enable_repository_backup` | Task.params | 继承全局配置 | 单个任务的备份控制，可覆盖全局配置 |

**行为逻辑**：
1. 当 `repository.auto_backup_downloads = true` 时，所有下载任务默认上传到仓库频道
2. 创建任务时，用户可通过 `params.enable_repository_backup` 覆盖默认行为
3. 任务级配置的默认值 = 全局配置值（用户不指定时自动继承）
4. 仅对 `DOWNLOAD` 和 `LISTEN_DOWNLOAD` 任务类型生效（转发任务不涉及本地存储）

**API请求示例**（强制禁用备份）：
```json
{
  "task_type": "download",
  "params": {
    "source_identifier": "@seseYunBot",
    "enable_repository_backup": false
  }
}
```

---

## 四、技术实现方案

### 4.1 API契约

#### API 1：Identifier解析

**端点**：`GET /api/chats/resolve`

**请求参数**（Query String）：

| 参数 | 类型 | 必填 | 示例 | 说明 |
|------|------|------|------|------|
| `identifier` | string | 是 | `@seseYunBot` | 要解析的标识符 |

**成功响应**（200 OK）：
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

**错误响应**：
```json
// 400 - 格式无效
{ "code": 400, "message": "标识符格式不正确", "data": null }

// 403 - 无权限
{ "code": 403, "message": "您尚未与此用户建立对话", "data": null }

// 429 - API限流
{ "code": 429, "message": "请求过于频繁,请稍后再试", "data": { "retry_after": 30 } }
```

> **缓存与限流策略**：`GET /api/chats/resolve` 不实现服务端缓存，避免chat信息不一致；前端"解析"按钮需做至少3秒的防抖处理，降低触发Telegram FloodWait的概率。

#### API 2：创建任务（扩展现有端点）

**端点**：`POST /api/tasks`（复用现有端点，无变化）

**请求体**（私聊下载任务）：
```json
{
  "task_type": "download",
  "params": {
    "source_identifier": "@seseYunBot",
    "range_mode": "recent",
    "recent_count": 10,
    "media_types": ["video"]
  }
}
```

**请求体**（私聊转发任务）：
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

**请求体**（监听下载任务）：
```json
{
  "task_type": "listen_download",
  "params": {
    "source_identifier": "@seseYunBot",
    "media_types": ["video", "photo"]
  }
}
```

**请求体**（监听转发任务）：
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
                                      _execute_download() ← 复用现有逻辑
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

### 4.3 关键行为差异（私聊 vs 频道）

| 维度 | 频道任务 | 私聊任务 | 处理方式 |
|------|---------|---------|---------|
| **源标识符** | `params.chat_id`（t.me链接） | `params.source_identifier` | create_task内部判断 |
| **消息获取** | 公开频道直接遍历 | 需先验证对话可访问性 | get_chat检查 |
| **监听机制** | 旧：Bot命令+内存Handler；新：TaskExecutor统一管理 | 注册NewMessage Handler | 方案A迁移统一，频道/私聊均走TaskExecutor |
| **仓库备份** | 按全局配置 | 继承全局配置+可覆盖 | params.enable_repository_backup 控制 |
| **去重检查** | L1+L2+L3三级去重 | 同上 | 复用现有RepositoryManager |

### 4.4 监听任务迁移策略（方案A：迁移统一）

**现状分析**：

当前项目中存在两套监听实现：
- **旧架构**：通过 `self.user.add_handler()` 在 User Client 上注册监听 Handler，状态存储在 `StateManager` 的内存 dict 中
- **新架构**：PRD 提议在 `TaskExecutor` 中统一管理监听 Handler 生命周期，状态持久化到 TaskManager 的 SQLite 中

**问题**：两者操作同一个 User Client，若不迁移则同一 chat_id 上的 Handler 会重复触发，且状态互不感知。

**决策：方案A - 迁移统一**

将旧架构的监听逻辑完全迁移至 TaskExecutor，实现统一的 Handler 生命周期管理。

**迁移范围**：

| 迁移项 | 旧位置 | 新位置 | 迁移方式 |
|--------|--------|--------|---------|
| 监听 Handler 注册 | `downloader.py:add_listen_chat()` | `TaskExecutor._start_listener()` | 重写：通过 TaskManager 创建 LISTEN_* 任务 |
| 监听 Handler 移除 | `downloader.py:cancel_listen()` | `TaskExecutor._stop_listener()` | 重写：取消任务时移除 Handler |
| 监听下载回调 | `downloader.py:listen_download()` | `TaskExecutor._handle_listen_download()` | 迁移：复用 `_execute_download()` 逻辑 |
| 监听转发回调 | `downloader.py:listen_forward()` | `TaskExecutor._handle_listen_forward()` | 迁移：复用 `_execute_forward()` + RepositoryManager 降级链 |
| 监听状态存储 | `StateManager.listen_download_chat`（内存dict） | `TaskManager._tasks`（SQLite） | 迁移：持久化存储，进程重启后可恢复 |
| Bot 命令入口 | `CommandRouter.on_listen()` | 保持不变（参数转换层） | 改造：调用 `TaskManager.create_task()` 替代直接注册 Handler |
| 监听信息查询 | `CommandRouter.listen_info()` | 保持不变（查询层） | 改造：从 TaskManager 查询 LISTEN_* 任务 |
| 监听回调按钮 | `downloader.py:callback_data()`（REMOVE_LISTEN_*） | `TaskExecutor._stop_listener()` | 改造：按钮回调触发任务取消 |

**迁移后的 Bot 命令流程**：

```
用户发送 /listen_download @seseYunBot
        │
        ▼
[CommandRouter.on_listen()] (参数转换层,保持不变)
        │ 解析命令参数
        │ 调用 TaskManager.create_task()
        ▼
[TaskManager.create_task(task_type=LISTEN_DOWNLOAD, ...)]
        │ 创建 Task + TaskItem
        │ 持久化到 SQLite
        ▼
[TaskExecutor.execute_task()] (统一执行层)
        │ task_type == LISTEN_DOWNLOAD
        │ 调用 _start_listener()
        ▼
[TaskExecutor._start_listener()]
        │ 解析 source_identifier → chat_id
        │ 创建 MessageHandler(callback=_handle_listen_download)
        │ 注册到 User Client
        │ 存储 handler 引用到 Task.extra["handler"]
        ▼
[新消息到达] → _handle_listen_download() → 复用 _execute_download() 逻辑
```

**向后兼容保证**：
- Bot 命令入口的用户交互保持不变
- 现有频道监听功能正常工作
- 进程重启后，SQLite 中的 running 状态监听任务自动恢复

---

## 五、交互设计

### 5.1 交互方式

**交互方式**：✅ WebUI + ✅ Bot命令（监听命令迁移后支持）

> **注意**：私聊下载/转发任务仅通过 WebUI 创建；监听任务同时支持 WebUI 和 Bot 命令（方案A迁移统一后）

### 5.2 页面集成方案

**位置**：在现有 `tasks.html` 的任务创建表单中扩展

**改动要点**：
1. **源输入框增强**：接受 username / chat_id / t.me 链接，新增"[解析]"按钮，3秒防抖
2. **目标输入框增强**：转发/监听转发时显示，同源输入框
3. **消息范围选项扩展**：新增"最近N条"单选 + 数字输入框
4. **媒体过滤增强**：新增文件大小范围输入
5. **任务类型扩展**：新增 listen_download / listen_forward

---

## 六、验收标准

### 6.1 功能验收标准

| ID | 功能项 | 验收标准 | 优先级 |
|----|-------|---------|--------|
| F01 | **Identifier解析** | 支持4种输入格式，均能正确返回chat_id和元信息 | P0 |
| F02 | **私聊下载任务** | 成功下载私聊中的任意大小媒体文件 | P0 |
| F03 | **私聊转发任务** | 成功转发到目标频道；降级链全部可用 | P0 |
| F04 | **监听下载任务** | 新消息后30秒内开始下载；同一chat_id重复创建返回409 | P1 |
| F05 | **监听转发任务** | 新消息后30秒内转发到目标频道；同一chat_id重复创建返回409 | P1 |
| F06 | **消息范围-recent模式** | 正确获取最近N条消息；N=0时返回400 | P0 |
| F07 | **消息范围-其他模式** | id_range/date_range/all在私聊中正常工作 | P0 |
| F08 | **媒体类型过滤** | 仅下载/转发匹配类型的文件 | P1 |
| F09 | **文件大小过滤** | min_size/max_size边界值正确 | P1 |
| F10 | **向后兼容性** | 现有频道下载/转发任务不受影响 | P0 |
| F11 | **监听迁移回归** | Bot命令迁移后功能不变 | P0 |
| F12 | **监听任务持久化** | 进程重启后，running状态的监听任务自动恢复 | P1 |
| F13 | **监听动态Item管理** | 新消息到达后生成TaskItem并持久化 | P1 |

### 6.2 性能验收标准

| ID | 指标 | 目标值 |
|----|-----|--------|
| P01 | **Identifier解析延迟** | P50 < 500ms, P99 < 2000ms |
| P02 | **大文件下载** | 支持 ≥1GB 文件 |
| P03 | **并发私聊任务** | ≥3个私聊任务同时运行 |
| P04 | **监听消息延迟** | 新消息到达后 < 60秒内触发 |

### 6.3 安全验收标准

| ID | 安全项 | 验收标准 |
|----|-------|---------|
| S01 | **访问权限控制** | 对未建立对话的用户返回403+ACCESS_DENIED |
| S02 | **Token认证** | 所有新增API端点均需有效Token |
| S03 | **文件完整性校验** | 下载完成后比对文件大小 |
| S04 | **资源保护阈值** | 单任务总大小超过10GB时拒绝创建 |

---

## 七、实施计划

### 7.1 开发阶段划分

**阶段1：基础能力层（预计3天）**：
- [ ] 创建 IdentifierService - Identifier统一解析服务
- [ ] 重构 API 路由 - 使用公共解析服务替代内联实现
- [ ] 重构 Bot 命令路由 - 使用公共解析服务
- [ ] 扩展 TaskType / RangeMode 枚举
- [ ] 实现 `GET /api/chats/resolve` 端点
- [ ] 编写单元测试（覆盖率≥80%）

**阶段2：任务管理层（预计3天）**：
- [ ] 扩展 `TaskManager.create_task()` - 支持 `source_identifier` 参数
- [ ] 扩展 `TaskManager.create_task()` - LISTEN_* 任务的排他性校验
- [ ] 扩展 `TaskExecutor._resolve_message_ids()` - 支持 `recent` 模式
- [ ] 新增媒体类型+大小过滤逻辑
- [ ] 编写单元测试（覆盖率≥80%）

**阶段3：任务执行层 + 监听迁移（预计6天）**：
- [ ] 扩展 TaskExecutor - 新增 LISTEN_DOWNLOAD / LISTEN_FORWARD 分支
- [ ] 集成现有 `_execute_download()` / `_execute_forward()` 复用
- [ ] 迁移 Bot 监听命令入口
- [ ] 清理旧架构监听实现
- [ ] 编写单元测试（覆盖率≥80%）

**阶段4：WebUI界面层（预计3天）**：
- [ ] 扩展 tasks.html - 源/目标输入框增强
- [ ] 扩展 js/tasks.js - 解析API调用
- [ ] 新增消息范围 recent 选项UI
- [ ] 新增监听任务创建表单

**阶段5：集成测试与优化（预计2天）**：
- [ ] 完整流程E2E测试
- [ ] 向后兼容回归测试
- [ ] Bug修复与优化

**总计**：约17个工作日

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
                                           └──> 阶段4b(监听UI)

阶段1+2+3 ──> 阶段5(集成测试)
```

### 7.3 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| Handler双重注册（新旧架构冲突） | 高 | 高 | 采用方案A迁移统一，移除旧实现 |
| 监听任务进程中断丢失 | 中 | 高 | 监听任务状态持久化到SQLite，启动时恢复 |
| 大量历史消息遍历性能 | 低 | 中 | recent模式限制上限1000 |

---

## 八、附录

### 8.1 术语表

| 术语 | 说明 |
|------|------|
| **file_id** | Telegram 文件标识符，在同一个 Bot/User Client 内有效，不保证永久有效 |
| **file_unique_id** | 跨客户端稳定的文件唯一标识符，不能用于下载或发送文件，推荐用于去重 |
| **仓库频道** | 专门用于存储文件的私有频道 |
| **分发** | 使用 copy_message 或 file_id 将文件发送到目标频道 |
| **三级回退** | file_id 失效时的回退策略：存储 file_id → 仓库消息刷新 → 重新下载 |
| **三级去重** | source 定位 → file_unique_id → 内容哈希（SHA256） |
| **Identifier** | 泛指可用于定位对话的字符串，包括username、数字ID、t.me链接 |
| **ResolvedChat** | 解析后的标准化对话信息对象，包含chat_id及元信息 |
| **私聊对话** | Telegram中type为private/bot的对话，区别于公开channel/group |
| **监听任务** | 通过注册NewMessage Handler实时处理新消息的任务类型 |
| **降级链** | 转发失败时的多级备选方案，按效率从高到低排列 |
| **迁移统一（方案A）** | 将旧架构监听逻辑完整迁移至新架构TaskExecutor，消除双架构并存 |

### 8.2 设计约束

| 约束 | 说明 |
|------|------|
| **User Client 统一执行** | 仓库模式所有操作统一由 User Client 执行 |
| **file_id 不保证永久有效** | 通过三级回退机制处理 |
| **SQLite 单一数据库** | 所有表加入现有 `trmd.db`，统一 WAL 模式 |
| **单一配置文件** | 单一 `config.yaml` 配置文件 |
| **RepositoryManager 为编排层** | 不直接操作文件和 Telegram API |
| **Token认证** | 所有新增API端点必须经过认证 |
| **User Client唯一性** | 监听Handler统一注册在唯一的User Client上 |

### 8.3 相关文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 任务管理器模块设计 | `docs/模块设计-任务管理器.md` | TaskManager/Task架构参考 |
| 交互增强设计 | `docs/交互增强设计.md` | Bot/WebUI交互体系参考 |
| 文件管理器模块设计 | `docs/模块设计-文件管理器.md` | 上传/转发降级链参考 |
| 数据模型设计文档 | `docs/数据模型设计文档.md` | 数据库表结构详细设计 |
| 模块设计-WebAPI | `docs/模块设计-WebAPI.md` | API路由设计参考 |
| 模块设计-Web界面 | `docs/模块设计-Web界面.md` | 前端界面设计参考 |
| 模块设计-缓存层 | `docs/模块设计-缓存层.md` | 缓存子系统设计 |
| 模块设计-标识符服务 | `docs/模块设计-标识符服务.md` | IdentifierService 详细设计 |
| 模块设计-Bot重构 | `docs/模块设计-Bot重构.md` | Bot命令系统设计 |
| 模块设计-Token认证 | `docs/模块设计-Token认证.md` | Token认证机制设计 |
| E2E测试设计文档 | `docs/E2E测试设计文档.md` | E2E测试方案 |
| E2E测试用例 | `docs/E2E测试用例.md` | E2E测试用例详细 |
| 验收测试用例文档 | `docs/验收测试用例文档.md` | 验收测试用例 |

### 8.4 参考资料

- [Telegram Bot API - sendPhoto](https://core.telegram.org/bots/api#sendphoto)
- [Telegram Bot API - copyMessage](https://core.telegram.org/bots/api#copymessage)
- [Pyrogram - copy_message()](https://docs.pyrogram.org/api/methods/copy_message)
- [Pyrogram - send_photo()](https://docs.pyrogram.org/api/methods/send_photo)

---

**文档结束** | 版本: v3.0 | 状态: 持续更新 | 下一版本计划: 待定