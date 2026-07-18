# Telegram 文件仓库模式 PRD

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **文档版本**: v2.0  
> **创建日期**: 2026-06-18  
> **更新日期**: 2026-06-18  
> **作者**: SOLO  
> **状态**: 已审核通过

---

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

### 4.3 文件结构

```
module/
├── core/
│   ├── repository_manager.py    # 仓库编排器（新增）
│   ├── repository_db.py         # 仓库数据表操作（新增）
│   └── repository_sync.py       # 定时同步（新增，可选）
├── downloader.py                # 修改：集成仓库模式
└── uploader.py                  # 修改：上传成功回调写入仓库记录
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

## 八、附录

### 8.1 术语表

| 术语 | 说明 |
|------|------|
| **file_id** | Telegram 文件标识符，在同一个 Bot/User Client 内有效，跨客户端不通用，**不保证永久有效** |
| **file_unique_id** | 跨客户端稳定的文件唯一标识符，**不能用于下载或发送文件**，推荐用于去重 |
| **仓库频道** | 专门用于存储文件的私有频道 |
| **分发** | 使用 copy_message 或 file_id 将文件发送到目标频道 |
| **三级回退** | file_id 失效时的回退策略：存储 file_id → 仓库消息刷新 → 重新下载 |
| **三级去重** | source 定位 → file_unique_id → 内容哈希（SHA256） |

### 8.2 设计约束

| 约束 | 说明 |
|------|------|
| **User Client 统一执行** | 仓库模式所有操作（上传、分发）统一由 User Client 执行，确保 file_id 在同一作用域内 |
| **file_id 不保证永久有效** | Telegram 保留随时使 file_id 失效的权利，通过三级回退机制处理 |
| **SQLite 单一数据库** | 仓库相关表加入现有 `trmd.db`，统一 WAL 模式 |
| **单一配置文件** | 合并 `config.yaml` 和 `global_config.yaml` 为单一配置文件 |
| **RepositoryManager 为编排层** | 不直接操作文件和 Telegram API，通过 FileManager/Uploader 执行 |

### 8.3 参考资料

- [Telegram Bot API - sendPhoto](https://core.telegram.org/bots/api#sendphoto)
- [Telegram Bot API - copyMessage](https://core.telegram.org/bots/api#copymessage)
- [Pyrogram - copy_message()](https://docs.pyrogram.org/api/methods/copy_message)
- [Pyrogram - send_photo()](https://docs.pyrogram.org/api/methods/send_photo)

---

**文档结束**
