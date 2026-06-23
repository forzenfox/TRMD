# Telegram Bot 交互体验增强设计文档

> **项目名称**: Telegram_Restricted_Media_Downloader
> **文档版本**: v6.0
> **创建日期**: 2026-06-12
> **更新日期**: 2026-06-21
> **作者**: SOLO
> **状态**: 待审核

---

## 一、项目背景

### 1.1 痛点分析

当前项目存在以下用户体验痛点：

| 痛点 | 描述 | 影响 |
|------|------|------|
| **命令格式繁琐** | 转发命令必须按 `/forward 原始频道 目标频道 起始ID 结束ID` 格式书写 | 用户记忆负担重，容易出错 |
| **本地文件媒体组上传缺失** | 无法将多个本地文件上传到同一媒体组 | 无法保持文件的媒体组关联 |
| **批量操作效率低** | 批量下载/转发需要预先整理好所有链接，一次性发送长命令 | 操作繁琐，容易遗漏或格式错误 |
| **配置管理困难** | 配置文件通过命令行交互式修改，不够直观 | 配置错误风险高 |
| **任务监控缺失** | 无法直观查看任务进度和状态 | 需要等待 Bot 通知，体验差 |

### 1.2 设计目标

采用**模块化设计**，重新划分 Bot 和 WebUI 的职责边界：

| 端 | 定位 | 职责 |
|----|------|------|
| **Bot 端** | 轻量级操作入口 | 简单命令、状态查询、WebUI 引导 |
| **WebUI 端** | 完整管理界面 | 复杂任务配置、文件管理、任务监控、配置管理 |

**核心原则：**
1. **Bot 简化** - Bot 只保留简单命令，复杂操作引导用户到 WebUI
2. **WebUI 增强** - 提供完整的任务管理、文件管理、配置管理功能
3. **共享核心** - Bot 和 WebUI 共享核心业务逻辑层，避免重复实现
4. **向后兼容** - 所有原有命令保持不变，新增功能作为可选增强
5. **单用户** - 当前版本仅支持单用户，无需多用户隔离
6. **Token 认证** - Bot `/web` 命令生成临时 Token（1 小时有效期），WebUI 通过 URL Token 认证，无需手动登录
7. **资源保护** - 单次任务 5GB 告警、10GB 禁止，转发任务默认上传后删除本地文件，多任务并发限制（可配置）

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                               │
│  ┌──────────────────┐         ┌──────────────────────────┐  │
│  │  Telegram Bot    │         │      WebUI (浏览器)       │
│  │  (轻量操作入口)   │         │   (完整管理界面)          │  │
│  └────────┬─────────┘         └────────────┬─────────────┘  │
└───────────┼────────────────────────────────┼────────────────┘
            │                                │
┌───────────▼────────────────────────────────▼────────────────┐
│                    Token 认证层（新增）                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  TokenManager: 生成/验证临时访问 Token                   │ │
│  │  - Bot: /web 命令生成 Token，有效期 1 小时              │ │
│  │  - WebUI: 链接自动携带 Token，无需手动输入              │ │
│  │  - API: 所有接口校验 Token 有效性                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
            │                                │
┌───────────▼────────────────────────────────▼────────────────┐
│                      API 网关层                              │
│  ┌──────────────────┐         ┌──────────────────────────┐  │
│  │  Bot API Handler │         │    FastAPI REST API      │  │
│  │  (命令解析)       │         │    (WebUI 接口)          │  │
│  │  +filters.user   │         │    +Token 中间件          │  │
│  └────────┬─────────┘         └────────────┬─────────────┘  │
└───────────┼────────────────────────────────┼────────────────┘
            │                                │
┌───────────▼────────────────────────────────▼────────────────┐
│                      核心业务层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ TaskManager  │  │FileManager   │  │ ConfigManager    │  │
│  │ (任务管理)    │  │(文件管理)     │  │ (配置管理)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │InteractionMgr│  │Monitor       │  │ TelegramClient   │  │
│  │(交互状态)     │  │(任务监控)     │  │ (Telegram API)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ RepositoryManager (仓库编排)                          │  │
│  │ ├─ RepositoryDB (数据访问)                            │  │
│  │ └─ RepositorySync (增量同步)                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────┐
│                      数据持久层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   SQLite     │  │  File System │  │   Config Files   │  │
│  │  (任务/日志)  │  │  (文件存储)   │  │  (YAML 配置)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ trmd.db (仓库数据库)                                  │  │
│  │ ├─ repository_files (文件记录)                        │  │
│  │ ├─ repository_sources (来源映射)                      │  │
│  │ └─ file_distributions (分发记录)                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

| 模块 | 职责 | 使用方 |
|------|------|--------|
| **TokenManager** | 生成/验证临时访问 Token，管理过期时间 | Bot + WebAPI 共享 |
| **Bot Module** | 命令解析、消息处理、状态查询（已有 `filters.user(self.root)` 保护） | Bot 端 |
| **Web API Module** | RESTful API、WebSocket 实时推送、Token 中间件 | WebUI 端 |
| **Task Manager** | 任务创建、执行、重试、取消、状态管理 | 共享 |
| **File Manager** | 文件浏览、选择、上传、媒体组处理 | 共享 |
| **Config Manager** | 配置读取、修改、保存 | 共享 |
| **Interaction Manager** | 交互状态管理、超时处理 | 共享 |
| **Monitor** | 任务进度监控、日志收集 | 共享 |
| **RepositoryManager** | 仓库频道编排：三级去重、分发降级、上传回调（不直接操作文件和 Telegram API） | 共享 |
| **RepositoryDB** | 仓库数据访问：三张表 CRUD、去重查询、来源追踪 | RepositoryManager 内部 |
| **RepositorySync** | 仓库频道增量同步：定时扫描、查漏补缺 | 可选（独立启动） |

### 2.3 状态机设计

```
                    ┌─────────────┐
                    │   IDLE      │ ← 默认状态
                    └──────┬──────┘
                           │
          用户触发批量命令 │
                    ┌──────▼──────┐
                    │ WAITING     │ ← 等待用户输入
                    │ _INPUT      │
                    └──────┬──────┘
                           │
              用户输入链接  │ / 文件选择
                    ┌──────▼──────┐
                    │ PROCESSING  │ ← 处理单条输入
                    │ _INPUT      │
                    └──────┬──────┘
                           │
              处理完成，返回 │
                    ┌──────▼──────┐
                    │ WAITING     │ ← 继续等待
                    │ _INPUT      │
                    └──────┬──────┘
                           │
              用户发送 /done 或超时
                    ┌──────▼──────┐
                    │ EXECUTING   │ ← 执行批量任务
                    │ _TASK       │
                    └──────┬──────┘
                           │
              任务完成
                    ┌──────▼──────┐
                    │   IDLE      │
                    └─────────────┘
```

---

## 三、Bot 端设计（轻量级）

### 3.1 命令体系

Bot 端只保留简单命令，复杂操作引导到 WebUI：

| 命令 | 功能 | 复杂度 |
|------|------|--------|
| `/start` | 欢迎信息 + WebUI 地址 | 低 |
| `/help` | 帮助信息 | 低 |
| `/download <链接>` | 单条链接下载 | 低 |
| `/forward <源> <目标> <起始> <结束>` | 单条转发（原有格式保留） | 中 |
| `/upload <文件> <目标>` | 单文件上传（原有格式保留） | 中 |
| `/status` | 查看当前任务状态 | 低 |
| `/web` | 获取 WebUI 访问链接（带 Token，1 小时有效期） | 低 |
| `/web_revoke` | 撤销所有已生成的 WebUI Token | 低 |
| `/batch` | 进入批量操作模式（简化版） | 中 |
| `/setup_repository` | 设置仓库频道（支持频道 ID、用户名、链接、邀请链接） | 中 |

### 3.2 `/web` 命令

用户通过 `/web` 命令获取 WebUI 访问链接，链接自动携带认证 Token：

```
用户: /web
Bot: 🌐 WebUI 管理面板

     访问链接: http://192.168.1.100:8080/?token=eyJhbGciOi...
     有效期: 1 小时（2026-06-12 15:30 过期）
     
     💡 点击链接即可直接进入管理界面，无需额外登录
     ⚠️ Token 过期后请重新发送 /web 获取新链接
```

**认证原理：**
- Bot 端沿用现有机制：只有登录的用户账户 ID（`self.root`）才能下达 Bot 指令
- 用户发送 `/web` 命令时，Bot 已通过 `filters.user(self.root)` 验证身份
- 验证通过后生成临时 Token，有效期 1 小时
- Token 以 URL 参数形式附带在链接中（`?token=xxx`）
- WebUI 收到请求时，通过 Token 验证身份，无需手动输入 User ID

**Token 设计：**
- 格式：随机字符串（如 `secrets.token_urlsafe(32)`）
- 存储：内存字典 `{token: {expires_at}}`
- 有效期：1 小时
- 每次 `/web` 命令生成新 Token，旧 Token 仍然有效（直到过期）

### 3.3 简化批量操作

Bot 端提供简化版批量操作，复杂场景引导到 WebUI：

```
用户: /batch
Bot: 📦 批量操作模式
     请逐条发送链接（每条消息一条）
     发送 /done 结束，/cancel 取消
     当前: 0 条待处理
     [/done] [/cancel]
     
     💡 提示：复杂批量操作请使用 WebUI
     发送 /web 获取访问地址
```

### 3.4 WebUI 引导

当用户尝试复杂操作时，Bot 引导到 WebUI：

```
用户: /upload_album
Bot: 📁 媒体组上传功能请使用 WebUI 操作
     WebUI 支持：
     ✅ 可视化文件浏览
     ✅ 勾选式文件选择
     ✅ 实时上传进度
     ✅ 自动媒体组拆分
     
     获取访问地址: /web
```

---

## 四、WebUI 端设计（完整功能）

### 4.1 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| **后端框架** | FastAPI | 异步高性能，与 PRD 技术栈一致 |
| **前端** | 原生 HTML + Alpine.js + Tailwind CSS | 轻量无构建，易于集成 |
| **实时通信** | WebSocket | 任务进度实时推送 |
| **认证** | URL Token（1 小时有效期） | Bot `/web` 命令生成，链接自动携带，无需手动输入 |
| **数据库** | SQLite | 轻量，无外部依赖 |

### 4.2 功能模块

#### 4.2.1 任务管理

| 功能 | 描述 |
|------|------|
| **创建下载任务** | 输入频道链接 + 消息范围（日期范围/ID 范围/多个 ID 或链接/全部消息）+ 类型过滤，预览后确认提交 |
| **创建转发任务** | 输入源/目标频道链接 + 消息范围（日期范围/ID 范围/多个 ID 或链接/全部消息）+ 类型过滤，支持选择「上传后删除本地文件」（默认勾选），预览后确认提交 |
| **创建上传任务** | 输入本地文件路径，支持多文件选择、媒体组配置 |
| **任务队列** | 查看任务列表、开始/重试/取消任务 |
| **任务详情** | 查看任务进度、日志、错误信息 |

#### 4.2.1.1 消息范围选择

所有批量下载/转发任务支持以下四种消息范围选择模式：

| 模式 | 输入方式 | 适用场景 |
|------|---------|---------|
| **日期范围** | 选择开始日期 + 结束日期 | 按时间维度筛选，如"最近一周的视频" |
| **消息 ID 范围** | 输入最小 ID + 最大 ID（如 `100 - 500`） | 连续消息范围 |
| **多个消息 ID / 链接** | 输入一组消息 ID 或消息链接（每行一个，如 `100`、`150`、`https://t.me/ch/200`） | 零散/不连续的消息 |
| **全部消息** | 勾选「全部消息」复选框 | 处理目标频道/群组历史所有消息 |

**交互示例（日期范围模式）：**

```
┌─────────────────────────────────────────────────────┐
│  消息范围选择模式：                                   │
│  [ ] 日期范围  [●] 消息 ID 范围  [ ] 多个 ID/链接   │
│  [ ] 全部消息                                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  最小消息 ID: ┌──────────┐  最大消息 ID: ┌──────────┐│
│               │ 100      │               │ 500      ││
│               └──────────┘               └──────────┘│
└─────────────────────────────────────────────────────┘
```

**交互示例（多个 ID / 链接模式）：**

```
┌─────────────────────────────────────────────────────┐
│  消息范围选择模式：                                   │
│  [ ] 日期范围  [ ] 消息 ID 范围  [●] 多个 ID/链接   │
│  [ ] 全部消息                                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  请输入消息 ID 或链接（每行一个）：                    │
│  ┌─────────────────────────────────────────────┐    │
│  │ 100                                         │    │
│  │ 150                                         │    │
│  │ https://t.me/source_channel/200             │    │
│  │ 250                                         │    │
│  │ ...                                         │    │
│  └─────────────────────────────────────────────┘    │
│  已输入 4 条                                        │
└─────────────────────────────────────────────────────┘
```

**交互示例（全部消息模式）：**

```
┌─────────────────────────────────────────────────────┐
│  消息范围选择模式：                                   │
│  [ ] 日期范围  [ ] 消息 ID 范围  [ ] 多个 ID/链接   │
│  [●] 全部消息                                       │
├─────────────────────────────────────────────────────┤
│  ⚠️ 将处理频道历史所有消息，可能耗时较长             │
│  💡 统计时将采用抽样估算，避免大量 API 调用           │
│  确认要继续吗？ [ 取消 ]  [ 继续统计 ]               │
└─────────────────────────────────────────────────────┘
```

> **注意：**「全部消息」模式下，消息统计采用**抽样估算**策略（获取头尾各 10 条消息作为样本），避免遍历全部消息导致 API 超限。

#### 4.2.1.2 资源保护

为防止单次任务消耗过多服务器资源（磁盘空间、带宽），所有下载/转发任务预览时进行边界判断：

| 阈值 | 行为 | 说明 |
|------|------|------|
| **< 5GB** | 正常创建 | 无告警，直接确认创建 |
| **5GB - 10GB** | 告警 + 二次确认 | 弹窗提示任务总量，用户确认后继续 |
| **> 10GB** | 禁止创建 | 弹窗提示超出上限，要求缩小范围 |

**告警弹窗示例：**

```
┌─────────────────────────────────────────────────────┐
│  ⚠️ 资源告警                                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  当前任务统计结果：                                  │
│  - 消息总数：850 条                                  │
│  - 总大小：7.2 GB                                    │
│  - 预估时间：约 45 分钟                              │
│                                                      │
│  ⚠️ 任务总量超过 5GB，请确认：                       │
│  - 你的服务器磁盘有足够空间                          │
│  - 你知晓该任务可能消耗较多带宽                      │
│                                                      │
│          [ 返回修改 ]        [ 确认创建 ]            │
└─────────────────────────────────────────────────────┘
```

**超限禁止示例：**

```
┌─────────────────────────────────────────────────────┐
│  ❌ 任务超出限制                                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  当前任务统计结果：                                  │
│  - 消息总数：2,000 条                                │
│  - 总大小：15.3 GB                                   │
│                                                      │
│  ❌ 单次任务上限为 10GB，请缩小范围后重试            │
│                                                      │
│  建议：                                             │
│  - 缩小消息 ID 范围                                  │
│  - 缩小日期范围                                      │
│  - 使用类型过滤（如只选择视频或图片）                 │
│                                                      │
│                     [ 返回修改 ]                     │
└─────────────────────────────────────────────────────┘
```

#### 4.2.1.3 转发任务本地文件清理

转发任务（先下载再上传）支持配置本地文件清理策略：

| 选项 | 说明 |
|------|------|
| **上传成功后删除本地文件**（默认 ✅ 勾选） | 文件上传到目标频道后立即删除本地副本，及时释放磁盘 |
| **保留本地文件** | 上传后保留本地副本，用于后续查看或重试 |

**交互示例：**

```
┌─────────────────────────────────────────────────────┐
│  转发任务配置                                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  [✓] 上传成功后自动删除本地文件                      │
│      （释放磁盘空间，推荐开启）                      │
│                                                      │
│  [ ] 保留本地文件                                    │
│      （文件保留在下载目录）                          │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### 4.2.1.4 多任务并发资源限制

为防止多个任务同时执行导致 CPU 满载、内存溢出、磁盘占满等问题，系统提供多维度资源限制，**所有参数均可配置**：

**任务并发控制：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_concurrent_tasks` | 1 | 同时执行的最大任务数（超出部分进入队列等待） |
| `max_download_concurrency` | 3 | 单个任务内同时下载的文件数 |
| `max_upload_concurrency` | 1 | 单个任务内同时上传的文件数 |
| `max_forward_concurrency` | 1 | 转发任务并发数（同时占用上下行带宽，需保守） |

**带宽参考与建议值（以用户服务器实际带宽为准）：**

| 服务器带宽 | 建议下载并发 | 建议上传并发 | 建议任务并发 |
|-----------|------------|------------|------------|
| 上行 30 Mbps / 下行 200 Mbps | 3 | 1 | 1 |
| 上行 100 Mbps / 下行 500 Mbps | 5 | 2 | 2 |
| 上行 500 Mbps+ / 下行 1000 Mbps+ | 10 | 5 | 3 |

**资源保护限制：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `min_disk_space_gb` | 2 | 剩余磁盘空间低于此值时禁止新任务 |
| `memory_limit_mb` | 512 | 单文件内存缓存上限（流式下载避免全量加载） |
| `task_size_warning_gb` | 5 | 单次任务总量超过此值告警 |
| `task_size_max_gb` | 10 | 单次任务上限，超过禁止创建 |

**配置示例（config.yaml）：**

```yaml
# config.yaml - 资源限制配置

resource_limits:
  # 任务并发
  max_concurrent_tasks: 1        # 同时执行的最大任务数
  max_download_concurrency: 3    # 单任务下载并发数
  max_upload_concurrency: 1      # 单任务上传并发数
  max_forward_concurrency: 1     # 转发任务并发数

  # 磁盘与内存保护
  min_disk_space_gb: 2           # 最小剩余磁盘空间（GB）
  memory_limit_mb: 512           # 单文件内存缓存上限（MB）

  # 任务大小限制
  task_size_warning_gb: 5        # 告警阈值（GB）
  task_size_max_gb: 10           # 最大限制（GB）
```

**任务队列行为：**

```
┌─────────────────────────────────────────────────────┐
│  任务队列状态                                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  正在执行（1/1）：                                   │
│    📥 #101  下载任务  ████████░░  80%               │
│                                                      │
│  等待队列（2 个）：                                  │
│    📤 #102  转发任务  [ 排队中 ]                     │
│    📥 #103  下载任务  [ 排队中 ]                     │
│                                                      │
│  队列规则：                                          │
│  - 当前最大并发任务数：1                             │
│  - 任务按创建顺序执行                                │
│  - 当前任务完成后自动启动下一个                      │
│  - 可取消排队中的任务                                │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**磁盘空间不足告警：**

```
┌─────────────────────────────────────────────────────┐
│  ❌ 无法创建任务                                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  当前磁盘状态：                                      │
│  - 总空间：50 GB                                     │
│  - 已用：49.5 GB                                     │
│  - 剩余：0.5 GB                                      │
│                                                      │
│  ❌ 剩余空间不足 2 GB（配置的 min_disk_space_gb）    │
│  请清理磁盘空间后重试                                │
│                                                      │
│                     [ 我知道了 ]                     │
└─────────────────────────────────────────────────────┘
```

#### 4.2.2 文件管理

| 功能 | 描述 |
|------|------|
| **文件浏览** | 树形目录结构，支持路径导航 |
| **文件选择** | 勾选式多选，支持全选/反选 |
| **媒体组配置** | 设置分组大小、排序方式 |
| **上传预览** | 预览待上传文件列表 |
| **上传进度** | 实时显示上传进度和状态 |

#### 4.2.3 配置管理

| 功能 | 描述 |
|------|------|
| **基础配置** | API ID、API Hash、Bot Token |
| **下载配置** | 下载类型、并发数、重试次数 |
| **上传配置** | 上传类型、并发数、媒体组设置 |
| **代理配置** | 代理开关、类型、地址、认证 |
| **通知配置** | 完成通知、错误通知开关 |

#### 4.2.4 监控面板

| 功能 | 描述 |
|------|------|
| **实时统计** | 下载/上传速度、任务数、文件数 |
| **任务列表** | 进行中/已完成/失败任务 |
| **日志查看** | 实时日志流，支持过滤 |
| **系统状态** | CPU、内存、磁盘使用率 |

### 4.3 页面设计

#### 4.3.1 页面结构

```
┌─────────────────────────────────────────────────────────┐
│  Header: Logo | 导航 | 设置                              │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│  Sidebar │              Main Content                    │
│          │                                              │
│  - 任务   │  ┌──────────────────────────────────────┐  │
│  - 文件   │  │                                      │  │
│  - 配置   │  │                                      │  │
│  - 监控   │  │                                      │  │
│  - 日志   │  │                                      │  │
│          │  │                                      │  │
│          │  └──────────────────────────────────────┘  │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

#### 4.3.2 核心页面

| 页面 | 功能 |
|------|------|
| **Dashboard** | 概览统计、快速操作入口 |
| **Tasks** | 任务列表、创建任务、任务详情 |
| **Files** | 文件浏览、选择、上传 |
| **Settings** | 配置管理 |
| **Monitor** | 实时监控、日志查看 |

### 4.4 API 设计

#### 4.4.1 认证机制

所有 API 接口（包括 WebSocket）均需携带 Token 进行认证：

**认证流程：**
1. 用户通过 Bot `/web` 命令获取带 Token 的访问链接（`?token=xxx`）
2. URL Token 仅用于首次进入页面
3. 首次访问成功后，WebUI 通过 `Set-Cookie` 下发 **HttpOnly Cookie**
4. 后续 AJAX/Fetch 请求使用 `Authorization: Bearer xxx` Header
5. WebSocket 连接使用 URL 参数传递 Token

| 方式 | 说明 |
|------|------|
| **URL 参数** | `?token=xxx`，仅用于首次页面访问和 WebSocket 连接 |
| **HttpOnly Cookie** | 首次验证后自动下发，防止 XSS 泄露 |
| **请求头** | `Authorization: Bearer xxx`，用于 AJAX/Fetch 请求 |

Token 无效或过期时，所有接口返回 `401 Unauthorized`。

**Token 安全：**
- Token 存储于 SQLite 数据库，进程重启后可恢复
- Token 有效期 1 小时，支持手动撤销（Bot 端 `/web_revoke` 命令）
- 每次 `/web` 命令生成新 Token，旧 Token 仍然有效（直到过期或撤销）

#### 4.4.2 RESTful API

**任务管理：**

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/tasks` | GET | 获取任务列表（支持 `?status=pending` 过滤） | Token |
| `/api/tasks` | POST | 创建任务（需指定 `task_type`：`download`/`forward`/`upload`） | Token |
| `/api/tasks/{id}` | GET | 获取任务详情 | Token |
| `/api/tasks/{id}/start` | POST | 开始任务（手动触发排队中的任务） | Token |
| `/api/tasks/{id}` | DELETE | 取消任务 | Token |
| `/api/tasks/{id}/retry` | POST | 重试任务 | Token |

**频道与消息（带缓存）：**

| 端点 | 方法 | 功能 | 认证 | 缓存 |
|------|------|------|------|------|
| `/api/chats` | GET | 获取用户加入的频道列表（优先读缓存） | Token | 1 小时 |
| `/api/chats/{chat_id}/messages/estimate` | POST | 估算消息范围统计（样本采样） | Token | 10 分钟 |
| `/api/chats/{chat_id}/messages/analyze` | POST | 精确分析消息范围（遍历全部） | Token | 按参数缓存 |

**文件与配置：**

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/files` | GET | 获取文件列表（`?path=xxx`） | Token |
| `/api/files/upload` | POST | 上传文件 | Token |
| `/api/config` | GET | 获取配置 | Token |
| `/api/config` | PUT | 更新配置 | Token |
| `/api/monitor/stats` | GET | 获取监控统计 | Token |
| `/api/resource/status` | GET | 获取资源状态（磁盘/内存/并发数） | Token |

#### 4.4.3 WebSocket

| 端点 | 功能 | 认证 | 断线重连 |
|------|------|------|---------|
| `/ws/tasks` | 任务状态实时推送 | Token（URL 参数） | 自动重连，重发最后状态 |
| `/ws/monitor` | 监控数据实时推送 | Token（URL 参数） | 自动重连 |
| `/ws/logs` | 日志实时推送 | Token（URL 参数） | 自动重连 |

**WebSocket Token 续期：**
- 长任务执行期间 Token 可能过期，WebSocket 连接保持活跃
- 连接建立后，Token 过期不影响已建立的 WebSocket 连接
- 断线重连时需携带新的有效 Token

---

## 五、核心模块设计

### 5.1 TaskManager

**任务状态定义：**

| 状态 | 说明 | 转换路径 |
|------|------|---------|
| `pending` | 已创建，等待队列 | 创建 → pending |
| `running` | 正在执行 | pending → running |
| `completed` | 执行成功 | running → completed |
| `failed` | 执行失败 | running → failed |
| `cancelled` | 用户取消 | pending/running → cancelled |
| `queued` | 排队等待（超出并发限制） | 创建 → queued → pending |

**任务与队列关系：**
- `self.tasks`：所有任务的存储字典，键为任务 ID
- `self.task_queue`：FIFO 队列，存放状态为 `queued` 的任务
- 当前执行任务数 < `max_concurrent_tasks` 时，自动从队列取出下一个任务

```python
class TaskManager:
    """任务管理器 - Bot 和 WebUI 共享（单用户）"""
    
    def __init__(self, config: dict):
        self.tasks: dict[str, Task] = {}          # 所有任务
        self.task_queue: asyncio.Queue = asyncio.Queue()  # 排队中的任务
        self.running_count: int = 0               # 当前执行中任务数
        self.max_concurrent: int = config.get('max_concurrent_tasks', 1)
    
    async def create_task(self, task_type: TaskType, params: dict) -> Task:
        """创建任务：资源检查 → 创建 → 排队或执行"""
    
    async def start_task(self, task_id: str) -> bool:
        """手动开始排队中的任务（或任务满时排队）"""
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务：running → cancelled，queued 直接移除"""
    
    async def retry_task(self, task_id: str) -> bool:
        """重试任务：基于子任务状态只重试失败的文件"""
    
    async def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
    
    async def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """获取任务列表"""
    
    async def _on_task_complete(self, task: Task) -> None:
        """任务完成后，自动启动队列中下一个"""
    
    async def _check_resource_limits(self, task: Task) -> tuple[bool, str]:
        """资源检查：磁盘空间、任务大小、并发数"""
```

#### 5.1.1 任务持久化

| 维度 | 方案 |
|------|------|
| **任务状态** | SQLite 存储，进程重启后可恢复任务列表 |
| **子任务状态** | 每个文件/消息作为子任务记录状态（pending/success/failed/skipped） |
| **重试恢复** | 基于子任务状态，跳过已成功的文件，只重试失败的 |

#### 5.1.2 重试逻辑原则

重试功能的核心原则：**避免无效操作，节省带宽和 API 调用**

| 原则 | 说明 |
|------|------|
| **避免重复下载/上传** | 已成功的文件不重新下载/上传，只重试失败的子项 |
| **避免无效 API 调用** | 因消息被删除、频道被封等导致的失败不重试 |
| **避免无效带宽消耗** | 已下载部分不重新下载 |

**重试判断逻辑：**

```
任务失败 → 检查失败原因
  ├─ 文件已存在且完整 → 跳过，不重试
  ├─ 消息/文件已被删除 → 标记为不可重试，不重试
  ├─ 频道/群组无权限 → 标记为不可重试，不重试
  ├─ 网络超时/连接错误 → 可重试
  ├─ FloodWait 限制 → 等待指定时间后可重试
  └─ 其他可恢复错误 → 可重试
```

**下载任务重试：**
- 检查本地文件是否存在且大小与 Telegram 返回的 `file_size` 一致
- 一致 → 跳过该文件，不重新下载
- 不一致或不存在 → 重新下载

**上传任务重试：**
- 查询目标频道是否已有该文件（通过 `file_id` 或文件名匹配）
- 已存在 → 跳过该文件，不重新上传
- 不存在 → 重新上传

#### 5.1.3 仓库模式去重集成

当仓库模式启用时，任务执行流程中嵌入三级去重检查，避免重复下载和上传：

| 去重时机 | 去重级别 | 触发位置 | 命中后行为 |
|---------|---------|---------|-----------|
| **下载前** | L1: source_chat_id + source_message_id | `forward()` / `create_download_task()` | 跳过下载，直接从仓库分发 |
| **下载完成后、上传前** | L2: file_unique_id | `_dedup_before_upload()` | 跳过上传，添加 source mapping，从仓库分发 |
| **下载完成后、上传前** | L3: content_hash (SHA256) | `_dedup_before_upload()` | 删除本地文件，跳过上传，添加 source mapping，从仓库分发 |

**去重流程：**

```
转发任务开始
  │
  ├─ 仓库模式未启用 → 正常下载+上传流程
  │
  └─ 仓库模式启用
       │
       ├─ L1 去重命中 (source 定位)
       │    └─ 跳过下载，从仓库分发到目标频道
       │
       └─ L1 未命中 → 执行下载
            │
            ├─ L2 去重命中 (file_unique_id)
            │    └─ 跳过上传，添加 source mapping，从仓库分发
            │
            ├─ L3 去重命中 (content_hash)
            │    └─ 删除本地文件，跳过上传，添加 source mapping，从仓库分发
            │
            └─ 均未命中 → 上传到仓库频道 → 写入仓库记录 → 分发到目标频道
```

### 5.2 FileManager

> **仓库模式集成**：`UploadResult` 新增 `file_unique_id` 字段；`upload()` 方法新增 `source_chat_id` / `source_message_id` 参数，上传到仓库频道时自动调用 `RepositoryManager.on_upload_success` 写入仓库记录。

```python
@dataclass
class UploadResult:
    """描述一次上传任务的最终结果。"""
    success: bool
    file_path: str | None = None
    message: object | None = None          # Pyrogram Message 对象
    error_code: str | None = None
    error_msg: str | None = None
    deleted: bool = False                  # 本地文件是否已清理
    file_unique_id: str | None = None      # 文件唯一标识（仓库模式使用）

class FileManager:
    """文件管理器 - Bot 和 WebUI 共享"""

    async def list_files(self, path: str, recursive: bool = False) -> list[FileInfo]:
        """列出文件"""

    async def get_file_info(self, path: str) -> FileInfo:
        """获取文件信息"""

    async def select_files(self, paths: list[str]) -> list[FileInfo]:
        """选择文件"""

    async def upload_media_group(
        self,
        client: pyrogram.Client,
        chat_id: Union[int, str],
        file_paths: list[str],
        progress_callback=None
    ) -> list[pyrogram.types.Message]:
        """上传媒体组"""

    async def upload_single(
        self,
        client: pyrogram.Client,
        chat_id: Union[int, str],
        file_path: str,
        progress_callback=None
    ) -> pyrogram.types.Message:
        """上传单个文件"""

    async def upload(
        self,
        file_path: str,
        chat_id: int,
        progress_callback=None,
        delete_after: bool = False,
        caption: str = "",
        source_chat_id: int | None = None,
        source_message_id: int | None = None,
    ) -> UploadResult:
        """上传单个文件到 Telegram 频道/群组

        仓库模式集成：
        - 上传目标是仓库频道时，上传成功后调用 on_upload_success 写入仓库记录
        - 上传目标不是仓库频道时，先上传到仓库频道，再分发到目标频道
        """
```

### 5.3 InteractionManager

```python
class InteractionManager:
    """交互状态管理器 - 管理 Bot 交互状态"""
    
    active_sessions: dict[int, InteractionState]
    
    def start_session(self, user_id: int, mode: InteractionMode, **kwargs) -> bool:
        """启动交互会话"""
    
    def add_item(self, user_id: int, item: str) -> bool:
        """添加待处理项"""
    
    def end_session(self, user_id: int, execute: bool = True) -> list:
        """结束会话"""
    
    def cancel_session(self, user_id: int) -> bool:
        """取消会话"""
    
    def get_session(self, user_id: int) -> InteractionState | None:
        """获取会话状态"""
    
    def check_timeout(self) -> list[int]:
        """检查超时会话"""
    
    def reset_timeout(self, user_id: int) -> None:
        """重置超时"""
```

### 5.4 ConfigManager

> **BREAKING 变更**：`config.yaml` 和 `global_config.yaml` 已合并为单一 `config.yaml`。新分组结构包含：credential、proxy、task、preference、log、repository。`GlobalConfig` 类已被完全移除，所有配置直接从 `UserConfig` 读取。

**config.yaml 分组结构：**

```yaml
credential:
  api_id: null
  api_hash: null
  bot_token: null

proxy:
  enable_proxy: null
  scheme: null
  hostname: null
  port: null
  username: null
  password: null

task:
  links: null
  save_directory: null
  temp_directory: null
  session_directory: null
  download_type: null
  is_shutdown: null
  max_tasks:
    download: null
    upload: null
  max_retries:
    download: null
    upload: null

preference:
  notice: true
  forward_type: { ... }
  upload:
    download_upload: true
    delete: false
  export_table: { ... }

log:
  file_log_level: INFO
  console_log_level: WARNING

repository:
  enabled: true
  chat_id: ""
  auto_sync_enabled: false
  auto_sync_interval_minutes: 60
```

```python
class ConfigManager:
    """配置管理器 - Bot 和 WebUI 共享

    包装 UserConfig，提供统一配置读写接口。
    所有配置已合并到单一 config.yaml，不再依赖独立的 GlobalConfig。
    """

    def load_config(self) -> dict:
        """加载配置"""

    def save_config(self, config: dict) -> bool:
        """保存配置"""

    def get_config(self, key: str, default=None):
        """获取配置项"""

    def set_config(self, key: str, value) -> bool:
        """设置配置项"""

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        """验证配置"""

    def get_repository_config(self) -> dict:
        """获取 repository 分组配置"""

    def set_repository_chat_id(self, chat_id: str) -> bool:
        """设置 repository.chat_id 并保存"""

    def validate_repository_config(self) -> tuple[bool, str]:
        """验证 repository 配置（启用时 chat_id 必填且格式合法）"""
```

---

## 5.5 仓库模式（Repository Mode）

### 5.5.1 概述

仓库模式通过将下载的媒体文件集中存储到指定的 Telegram 频道（仓库频道），实现文件去重和高效分发。核心设计约束：

| 约束 | 说明 |
|------|------|
| **RepositoryManager 是编排层** | 不直接操作文件和 Telegram API，委托 FileManager/Uploader 执行操作 |
| **使用 User Client** | 所有仓库操作使用 User Client（file_id 作用域一致） |
| **file_unique_id 作为去重键** | 跨 Client 稳定标识，file_id 仅用于发送（可能过期） |

### 5.5.2 RepositoryDB - 数据访问层

管理 `trmd.db` 中的三张表，提供文件去重、来源追踪、分发记录的 CRUD 和查询接口。

**数据库表结构：**

| 表名 | 用途 | 关键约束 |
|------|------|---------|
| `repository_files` | 仓库文件记录 | `file_unique_id` UNIQUE |
| `repository_sources` | 文件来源映射 | `(source_chat_id, source_message_id)` UNIQUE, FK → repository_files |
| `file_distributions` | 文件分发记录 | FK → repository_files |

**repository_files 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `file_unique_id` | TEXT UNIQUE | 文件唯一标识（跨 Client 稳定） |
| `file_id` | TEXT | 文件发送标识（可能过期，需刷新） |
| `content_hash` | TEXT | SHA256 内容哈希（L3 去重） |
| `file_size` | INTEGER | 文件大小 |
| `file_type` | TEXT | 文件类型（photo/video/document/audio/animation） |
| `mime_type` | TEXT | MIME 类型 |
| `file_name` | TEXT | 文件名 |
| `repository_chat_id` | INTEGER | 仓库频道 ID |
| `repository_message_id` | INTEGER | 仓库频道消息 ID |
| `status` | TEXT | 状态（active） |
| `created_at` / `updated_at` | TEXT | 时间戳 |

**repository_sources 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `file_unique_id` | TEXT FK | 关联 repository_files |
| `source_chat_id` | INTEGER | 源频道 ID |
| `source_message_id` | INTEGER | 源消息 ID |
| `source_link` | TEXT | 源链接 |
| `created_at` | TEXT | 时间戳 |

**file_distributions 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `file_unique_id` | TEXT FK | 关联 repository_files |
| `target_chat_id` | INTEGER | 目标频道 ID |
| `target_message_id` | INTEGER | 目标消息 ID |
| `method` | TEXT | 分发方法（copy_message / file_id_send） |
| `task_id` | TEXT | 关联任务 ID |
| `created_at` | TEXT | 时间戳 |

**SQLite 配置：** WAL 模式、外键约束启用、busy_timeout=10000ms。

```python
class RepositoryDB:
    """仓库数据库管理器"""

    def __init__(self, db_path: str) -> None: ...

    # CRUD
    def insert_file_record(self, record: RepositoryFile) -> int: ...
    def insert_source_mapping(self, record: RepositorySource) -> int: ...
    def update_file_id(self, file_unique_id: str, new_file_id: str) -> None: ...
    def insert_distribution(self, record: FileDistribution) -> int: ...

    # 去重查询
    def get_file_by_source(self, source_chat_id: int, source_message_id: int) -> RepositoryFile | None: ...
    def get_file_by_unique_id(self, file_unique_id: str) -> RepositoryFile | None: ...
    def get_file_by_content_hash(self, content_hash: str) -> RepositoryFile | None: ...

    # 分发查询
    def get_repository_message_id(self, file_unique_id: str) -> tuple[int, int] | None: ...
```

### 5.5.3 RepositoryManager - 编排层

仓库频道的核心编排器，协调去重检查、上传回调、分发降级等流程。

```python
class RepositoryManager:
    """仓库频道编排器（不直接操作文件和 Telegram API）"""

    def __init__(self, repository_db: RepositoryDB, config_manager) -> None: ...

    # 配置
    def should_use_repository(self) -> bool: ...
    def get_repository_chat_id(self) -> str | None: ...

    # 三级去重
    def check_dedup(
        self,
        source_chat_id: int,
        source_message_id: int,
        file_unique_id: str | None = None,
        content_hash: str | None = None,
    ) -> RepositoryFile | None: ...

    # 上传成功回调
    async def on_upload_success(
        self, message, source_chat_id: int, source_message_id: int,
        content_hash: str | None = None,
    ) -> None: ...

    # 内容哈希
    @staticmethod
    def compute_content_hash(file_path: str) -> str: ...

    # 分发（含降级链）
    async def distribute_to_target(
        self, client, file_unique_id: str, target_chat_id: int,
        caption: str | None = None,
    ) -> int | None: ...
```

### 5.5.4 三级去重机制

| 级别 | 去重键 | 命中行为 | 适用场景 |
|------|--------|---------|---------|
| **L1** | source_chat_id + source_message_id | 跳过下载，直接从仓库分发 | 同一源消息重复转发 |
| **L2** | file_unique_id | 跳过上传，添加 source mapping，从仓库分发 | 同一文件不同消息来源 |
| **L3** | content_hash (SHA256) | 删除本地文件，跳过上传，添加 source mapping，从仓库分发 | 不同格式/来源的相同内容 |

**关键设计：**
- `file_unique_id` 作为去重主键（跨 Client 稳定），`file_id` 仅用于发送（可能过期）
- L1 在下载前检查（`forward()` / `create_download_task()`），L2/L3 在下载完成后检查（`_dedup_before_upload()`）
- L3 命中时删除本地文件以释放磁盘空间

### 5.5.5 分发降级链

从仓库频道分发文件到目标频道时，采用逐级降级策略：

| 优先级 | 方法 | 说明 | 失败原因 |
|--------|------|------|---------|
| **1** | `copy_message` | 从仓库频道直接复制消息 | 权限不足、消息被删除 |
| **2** | `file_id_send` | 刷新 file_id 后使用对应 send 方法发送 | file_id 过期、消息被删除 |
| **3** | 重新下载上传 | 返回 None，由调用方处理 | 仓库消息被删除 |

**file_id 三级刷新策略：**

| 级别 | 来源 | 说明 |
|------|------|------|
| **1** | 数据库存储的 file_id | 直接使用，可能已过期 |
| **2** | 从仓库消息刷新 | `get_messages()` 获取最新 file_id 并更新数据库 |
| **3** | 重新下载 | 仓库消息也被删除时，需从源频道重新下载 |

### 5.5.6 RepositorySync - 增量同步

可选的定时同步器，用于查漏补缺（程序崩溃或数据不一致时的恢复）。

```python
class RepositorySync:
    """仓库频道定时同步器（可选功能）"""

    def __init__(self, repository_db: RepositoryDB, config_manager) -> None: ...

    def start(self) -> None: ...      # 启动定时同步（需 auto_sync_enabled=True）
    def stop(self) -> None: ...       # 停止同步

    async def incremental_sync(self, client=None) -> int: ...
        # 增量同步：追踪上次同步的最大 message_id，仅扫描新消息
        # 同步时不计算 content_hash，仅记录元数据
```

**配置项：**

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `repository.auto_sync_enabled` | false | 是否启用自动同步 |
| `repository.auto_sync_interval_minutes` | 60 | 同步间隔（分钟） |

### 5.5.7 降级策略

覆盖 9 种异常场景的降级处理：

| 场景 | 降级方式 |
|------|----------|
| 仓库频道未配置 | 直接上传到目标频道 |
| 仓库频道权限不足 | 直接上传到目标频道，输出警告 |
| 上传到仓库失败 | 直接上传到目标频道 |
| 数据表写入失败 | 继续上传，记录错误日志 |
| 仓库频道被删除/封禁 | 降级为直接上传，输出错误日志，建议用户重新配置 |
| Bot 被移出仓库频道 | 降级为直接上传，输出错误日志，建议用户重新配置 |
| file_id 失效 | 从仓库频道重新获取 file_id，若消息也被删除则重新上传 |
| 数据库文件损坏 | 降级为直接上传，提示用户运行同步恢复 |
| 并发写入冲突 | SQLite WAL 模式 + busy_timeout=10000ms |

### 5.5.8 集成点

| 模块 | 集成方式 |
|------|---------|
| **TelegramUploader** | 上传成功后触发 `RepositoryManager.on_upload_success`（`_repository_on_upload_success`） |
| **Downloader** | `forward()` 中 L1 去重检查，命中则从仓库分发；`_dedup_before_upload()` 执行 L2/L3 去重 |
| **FileManager** | `upload()` 新增 `source_chat_id`/`source_message_id` 参数；`UploadResult` 新增 `file_unique_id` 字段 |
| **BotCommands** | `/setup_repository` 命令：验证频道输入 → 解析频道 ID → 检查管理员权限 → 保存配置 |
| **ConfigManager** | 新增 `get_repository_config()`、`set_repository_chat_id()`、`validate_repository_config()` |

---

## 六、技术实现方案

### 6.1 文件结构变更

```
module/
├── core/                    # [新增] 核心业务层
│   ├── __init__.py
│   ├── task_manager.py      # 任务管理器
│   ├── file_manager.py      # 文件管理器
│   ├── config_manager.py    # 配置管理器
│   ├── interaction.py       # 交互状态管理
│   ├── monitor.py           # 任务监控
│   ├── repository_db.py     # [新增] 仓库数据库管理（三张表 CRUD）
│   ├── repository_manager.py # [新增] 仓库频道编排器（去重/分发/回调）
│   └── repository_sync.py   # [新增] 仓库增量同步器（可选）
│
├── api/                     # [新增] Web API 层
│   ├── __init__.py
│   ├── app.py               # FastAPI 应用
│   ├── routes/              # API 路由
│   │   ├── tasks.py
│   │   ├── files.py
│   │   ├── config.py
│   │   ├── monitor.py
│   │   └── auth.py
│   ├── models/              # 数据模型
│   │   ├── task.py
│   │   ├── file.py
│   │   └── config.py
│   └── websocket/           # WebSocket 处理
│       ├── tasks.py
│       └── monitor.py
│
├── web/                     # [新增] WebUI 前端
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   └── templates/
│       ├── index.html
│       ├── tasks.html
│       ├── files.html
│       ├── settings.html
│       └── monitor.html
│
├── bot.py                   # [修改] 简化命令，添加 WebUI 引导
├── uploader.py              # [修改] 支持媒体组上传
├── enums.py                 # [修改] 添加新枚举
└── language.py              # [修改] 添加新文案
```

### 6.2 与现有代码的集成

| 文件 | 修改内容 |
|------|---------|
| **bot.py** | 1. 简化命令体系<br>2. 添加 `/web` 命令<br>3. 复杂操作引导到 WebUI<br>4. 保留原有命令兼容性<br>5. 注册 `/setup_repository` 命令 handler |
| **app.py** | 1. 集成 TaskManager<br>2. 集成 ConfigManager<br>3. 启动 Web API 服务<br>4. 初始化 RepositoryManager 和 RepositorySync |
| **main.py** | 1. 支持同时启动 Bot 和 Web API<br>2. 添加启动参数控制 |
| **enums.py** | 1. 新增 TaskType、TaskStatus 枚举<br>2. 新增 InteractionMode 枚举 |
| **downloader.py** | 1. forward() 中仓库模式启用时执行 L1 去重检查，命中则从仓库分发<br>2. 下载完成后执行 L2/L3 去重检查（`_dedup_before_upload`）<br>3. 为上传任务附加 source_chat_id/source_message_id |
| **uploader.py** | 1. 上传成功后触发 `_repository_on_upload_success` 回调<br>2. 去重命中时调用 `_dedup_distribute` 从仓库分发<br>3. UploadTask 支持 source_chat_id/source_message_id 字段 |

### 6.3 启动方式

```bash
# 仅启动 Bot（默认）
python main.py

# 同时启动 Bot 和 WebUI
python main.py --web

# 仅启动 WebUI
python main.py --web-only

# 指定 WebUI 端口
python main.py --web --port 8080
```

---

## 七、非功能性需求

| 类别 | 需求 | 验收标准 |
|------|------|---------|
| **兼容性** | 所有原有命令保持不变 | 现有 `/download`、`/forward`、`/upload` 命令功能不受影响 |
| **安全性** | Bot + WebUI 统一认证 | Bot 已有 `filters.user(self.root)` 保护，WebUI 使用 URL Token（1 小时有效期），所有 API 接口强制 Token 校验 |
| **性能** | WebUI 响应时间 | API 响应 < 200ms，页面加载 < 3s |
| **单用户** | 仅支持单用户 | 无需多用户隔离、无需登录系统 |
| **稳定性** | 服务可用性 | Bot 和 WebUI 独立运行，互不影响 |
| **资源保护** | 并发/磁盘/内存限制 | 任务并发、磁盘阈值、内存限制均可配置，磁盘不足时禁止新任务 |
| **测试覆盖** | 单元测试 + 集成测试 | 核心模块覆盖率 ≥ 80% |

---

## 八、里程碑计划

| 阶段 | 内容 | 前置条件 |
|------|------|---------|
| **M1: 核心层重构** | TaskManager、FileManager、ConfigManager 抽象 | 设计文档审核通过 |
| **M2: Bot 简化** | 简化命令体系、添加 `/web` 命令、WebUI 引导 | M1 完成 |
| **M3: Web API** | FastAPI 应用、RESTful API、WebSocket | M1 完成 |
| **M4: WebUI 基础** | 页面框架、Dashboard、任务管理 | M3 完成 |
| **M5: WebUI 文件** | 文件浏览、选择、媒体组上传 | M3 完成 |
| **M6: WebUI 配置** | 配置管理、监控面板 | M3 完成 |
| **M7: 测试与优化** | 单元测试、集成测试、性能优化 | M2-M6 完成 |

---

## 九、附录

### 9.1 Telegram 媒体组限制

| 限制 | 说明 |
|------|------|
| **最大文件数** | 单个媒体组最多 10 个文件 |
| **支持类型** | 图片、视频、音频 |
| **不支持类型** | 文档（document）、贴纸、GIF |
| **总大小限制** | 普通用户 2GB，会员用户 4GB（单文件限制） |

### 9.2 参考资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [pyrogram send_media_group 文档](https://docs.pyrogram.org/api/methods/send_media_group)
- [Alpine.js 文档](https://alpinejs.dev/)
- [Tailwind CSS 文档](https://tailwindcss.com/)

---

## 十、变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-12 | 初始版本，完成交互体验增强设计 | SOLO |
| v2.0 | 2026-06-12 | **重构为模块化设计**：<br>1. 重新划分 Bot 和 WebUI 职责<br>2. Bot 简化为轻量操作入口<br>3. 新增 WebUI 完整管理界面设计<br>4. 抽象核心业务层（TaskManager、FileManager 等）<br>5. 新增 Web API 设计（RESTful + WebSocket）<br>6. 更新文件结构和里程碑计划 | SOLO |
| v2.1 | 2026-06-12 | **修正**：<br>1. 移除暂停/恢复任务，仅保留开始/重试/取消<br>2. 移除多用户设计，改为单用户<br>3. 新增重试逻辑原则（避免重复下载/上传、避免无效 API 调用、避免无效带宽消耗） | SOLO |
| v3.0 | 2026-06-12 | **简化认证方案**：<br>1. 移除「## 三、用户白名单设计」整个章节（包括配置、验证逻辑、UserValidator 模块、登录页面）<br>2. 移除 `/web_login` 命令，整合到 `/web` 命令<br>3. Bot 端沿用现有 `filters.user(self.root)` 机制（登录用户账户 ID 才能下达指令）<br>4. WebUI 改为 Token 认证，无需手动输入 User ID | SOLO |
| v4.0 | 2026-06-12 | **Token 认证方案**：<br>1. 新增 TokenManager 模块，生成/验证临时 Token（1 小时有效期）<br>2. `/web` 命令返回带 Token 的访问链接，无需手动输入 User ID<br>3. 所有 API 接口（REST + WebSocket）强制 Token 校验<br>4. Token 以 URL 参数或 Authorization Header 形式传递<br>5. 更新架构图、认证流程、非功能性需求 | SOLO |
| v5.0 | 2026-06-12 | **消息范围 + 资源限制**：<br>1. 新增消息范围选择四种模式（日期范围/ID 范围/多个 ID 或链接/全部消息）<br>2. 新增资源保护机制（5GB 告警、10GB 禁止）<br>3. 新增转发任务本地文件清理策略（默认上传后删除）<br>4. 新增多任务并发资源限制（任务并发/文件并发/磁盘保护/内存保护，所有参数可配置）<br>5. 提供带宽参考建议表，方便用户根据服务器配置调整 | SOLO |
| v6.0 | 2026-06-21 | **仓库模式（Repository Mode）**：<br>1. 新增 RepositoryDB 模块，管理 trmd.db 三张表（repository_files/repository_sources/file_distributions）<br>2. 新增 RepositoryManager 编排层，实现三级去重（L1:source定位/L2:file_unique_id/L3:content_hash）<br>3. 新增 RepositorySync 增量同步器（可选，定时查漏补缺）<br>4. **BREAKING**: config.yaml 与 global_config.yaml 合并为单一 config.yaml，新增 repository 分组<br>5. GlobalConfig 从 UserConfig 的 preference/log 分组读取，回退 .CONFIG.yaml 向后兼容<br>6. 分发降级链：copy_message → file_id_send → 重新下载上传<br>7. file_id 三级刷新：存储值 → 从仓库消息刷新 → 重新下载<br>8. 9 种降级场景覆盖（未配置/权限不足/上传失败/DB写入失败/频道删除/Bot移出/file_id失效/DB损坏/并发冲突）<br>9. 新增 `/setup_repository` Bot 命令<br>10. FileManager.UploadResult 新增 file_unique_id，upload() 新增 source_chat_id/source_message_id<br>11. Downloader 集成 L1 去重（forward）和 L2/L3 去重（_dedup_before_upload）<br>12. Uploader 集成上传成功回调（_repository_on_upload_success）和去重分发（_dedup_distribute） | SOLO |

---

> **文档结束**
