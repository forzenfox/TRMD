# Telegram Bot 交互体验增强设计文档

> **项目名称**: Telegram_Restricted_Media_Downloader
> **文档版本**: v7.2
> **创建日期**: 2026-06-12
> **更新日期**: 2026-07-03
> **作者**: SOLO
> **状态**: 设计中（私聊对话文件操作 + 监听任务架构迁移）

---

## 变更记录

| 版本 | 日期 | 变更内容 | 状态 |
|------|------|----------|------|
| v7.2 | 2026-07-03 | 1. **新增私聊对话文件操作能力**：支持 Bot / 用户 / Saved Messages 通过 username / chat_id 访问<br>2. **新增 IdentifierService 统一解析服务**：替代多处 `_resolve_chat_id()` 重复实现<br>3. **扩展任务类型**：新增 `LISTEN_DOWNLOAD`、`LISTEN_FORWARD`<br>4. **扩展消息范围模式**：新增 `recent` 最近N条模式<br>5. **私聊下载/转发仅通过 WebUI 创建**；监听任务在迁移后同时支持 WebUI 和 Bot 命令<br>6. **监听任务架构迁移**：从 Bot 命令 + 内存 Handler + StateManager 迁移至 TaskManager / TaskExecutor + SQLite 持久化 | 设计中 |
| v7.1 | 2026-06-24 | 1. **移除 --web-only 模式**（功能残缺、无真实使用场景）<br>2. 集成 TaskExecutor 使 Web 任务可实际执行<br>3. 启用 RepositorySync 仓库自动同步<br>4. 修复 Dashboard 分页参数 bug<br>5. 清理所有 mock 数据降级分支和条件判断 | 已实现 |
| v7.0 | 2026-06-24 | 1. WebSocket 方案改为 REST API 轮询<br>2. Monitor 页面合并至 Dashboard，日志查看功能移除<br>3. Bot 命令体系补充完整命令列表（20+ 命令）<br>4. 文件结构更新：移除 websocket/ 目录和 monitor.html<br>5. 新增 task_executor.py、chats.py、chat.py 等组件说明<br>6. Bot 命令模块化：bot/ 目录结构说明 | 已实现 |
| v6.0 | 2026-06-21 | 初始设计文档：WebUI + Bot 增强方案 | 已审核 |

---

## 一、项目背景

### 1.1 痛点分析

当前项目存在以下用户体验痛点：

| 痛点 | 描述 | 影响 |
|------|------|------|
| **命令格式繁琐** | 转发命令必须按 `/forward 原始频道 目标频道 起始ID 结束ID` 格式书写 | 用户记忆负担重，容易出错 |
| **私聊对话无法操作** | 仅支持公开频道/群组的 `t.me` 链接，无法访问 Bot、用户、Saved Messages 等私聊对话中的文件 | 无法批量收集 Bot 资源、整理私聊文件、备份 Saved Messages |
| **本地文件媒体组上传缺失** | 无法将多个本地文件上传到同一媒体组 | 无法保持文件的媒体组关联 |
| **批量操作效率低** | 批量下载/转发需要预先整理好所有链接，一次性发送长命令 | 操作繁琐，容易遗漏或格式错误 |
| **配置管理困难** | 配置文件通过命令行交互式修改，不够直观 | 配置错误风险高 |
| **任务监控缺失** | 无法直观查看任务进度和状态 | 需要等待 Bot 通知，体验差 |
| **监听任务状态易丢失** | 监听任务状态保存在内存中，进程重启后丢失 | 无法持久化恢复，且与新 TaskManager 架构不统一 |

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
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │ IdentifierService│  │ RepositoryManager (仓库编排)    │  │
│  │(对话标识符解析)    │  │ ├─ RepositoryDB (数据访问)     │  │
│  │                  │  │ └─ RepositorySync (增量同步)   │  │
│  └──────────────────┘  └────────────────────────────────┘  │
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
| **Web API Module** | RESTful API、REST 轮询、Token 中间件 | WebUI 端 |
| **Task Manager** | 任务创建、执行、重试、取消、状态管理 | 共享 |
| **File Manager** | 文件浏览、选择、上传、媒体组处理 | 共享 |
| **Config Manager** | 配置读取、修改、保存 | 共享 |
| **Interaction Manager** | 交互状态管理、超时处理 | 共享 |
| **Monitor** | 任务进度监控、日志收集 | 共享 |
| **IdentifierService** | 统一对话标识符解析：username / chat_id / t.me 链接 → chat_id + 元信息 | 共享 |
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

## 三、Bot 端设计

### 3.1 命令体系

Bot 端提供轻量级命令入口，同时支持 WebUI 引导。私聊对话（Bot / 用户 / Saved Messages）的下载与转发操作仅通过 WebUI 创建；监听任务在架构迁移后同时支持 WebUI 和 Bot 命令：

#### 3.1.1 基础命令

| 命令 | 功能 | 复杂度 |
|------|------|--------|
| `/start` | 欢迎信息 + 使用说明 | 低 |
| `/help` | 展示可用命令及详细说明 | 低 |
| `/exit` | 退出软件 | 低 |

#### 3.1.2 下载命令

| 命令 | 功能 | 示例 | 复杂度 |
|------|------|------|--------|
| `/download` | 分配新的下载任务（多种使用方式见说明） | `/download https://t.me/x 起始ID 结束ID` | 中 |
| ~~`/download_chat`~~ | ~~下载指定频道（支持内联键盘自定义内容过滤）~~ 已移除，迁移至 WebUI | - | - |
| `/listen_download` | 实时监听该链接的最新消息（视频和图片）进行下载 | `/listen_download https://t.me/A https://t.me/B ...` | 中 |

#### 3.1.3 转发命令

| 命令 | 功能 | 示例 | 复杂度 |
|------|------|------|--------|
| `/forward` | 从源频道转发至目标频道（支持 ID 范围或链接） | `/forward https://t.me/A https://t.me/B 1 100` | 中 |
| `/listen_forward` | 实时监听该链接的最新消息（任意消息）进行转发 | `/listen_forward 源频道 目标频道` | 中 |

#### 3.1.4 上传命令

| 命令 | 功能 | 示例 | 复杂度 |
|------|------|------|--------|
| `/upload` | 上传本地的文件到指定频道 | `/upload 本地文件路径 目标频道` | 中 |
| `/upload_r` | 递归上传文件夹（包含子文件夹）到指定频道 | `/upload_r 本地文件夹 目标频道` | 中 |

#### 3.1.5 监控与状态命令

| 命令 | 功能 | 复杂度 |
|------|------|--------|
| `/table` | 在终端输出当前下载的统计信息 | 低 |
| `/listen_info` | 查看当前已经创建的监听任务 | 低 |
| `/cancel` | 取消当前正在进行的交互流程 | 低 |

#### 3.1.6 WebUI 相关命令（新增）

| 命令 | 功能 | 复杂度 |
|------|------|--------|
| `/web` | 获取 WebUI 访问链接（带 Token，1 小时有效期） | 低 |
| `/web_revoke` | 撤销所有已生成的 WebUI Token | 低 |
| `/batch` | 进入批量操作模式（简化版，多步引导） | 中 |
| `/status` | 查看当前任务状态概要（复杂操作请前往 WebUI） | 低 |

#### 3.1.7 仓库模式命令（新增）

| 命令 | 功能 | 复杂度 |
|------|------|--------|
| `/setup_repository` | 设置仓库频道（支持频道 ID、用户名、链接、邀请链接） | 中 |

#### 3.1.8 Bot 命令能力矩阵

| 功能 | 频道/群组 | 私聊对话（Bot/用户/Saved） | 支持入口 |
|------|----------|---------------------------|---------|
| **下载** | ✅ Bot 命令 / WebUI | ❌ 仅 WebUI | Bot + WebUI（频道）/ WebUI（私聊） |
| **转发** | ✅ Bot 命令 / WebUI | ❌ 仅 WebUI | Bot + WebUI（频道）/ WebUI（私聊） |
| **监听下载** | ✅ Bot 命令 / WebUI | ✅ Bot 命令 / WebUI | Bot + WebUI（迁移后统一支持） |
| **监听转发** | ✅ Bot 命令 / WebUI | ✅ Bot 命令 / WebUI | Bot + WebUI（迁移后统一支持） |
| **上传** | ✅ Bot 命令 / WebUI | — | Bot + WebUI |

> **说明**：
> - 私聊下载/转发因输入形式复杂（username / chat_id 解析、消息范围配置），统一引导至 WebUI 创建
> - 监听任务迁移至 TaskManager / TaskExecutor 后，Bot 命令与 WebUI 共用同一套 Handler 生命周期管理
> - Bot 的 `/listen_download`、`/listen_forward`、`/listen_info` 命令入口保持不变，底层改为调用 TaskManager

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

### 3.5 监听任务架构迁移说明

**旧架构（迁移前）**：
- Bot 命令入口直接调用 `downloader.py` 中的监听方法
- `add_listen_chat()` / `cancel_listen()` 在 User Client 上注册/移除 Handler
- 监听状态保存在 `StateManager` 的内存字典（`listen_download_chat` / `listen_forward_chat`）中
- 进程重启后监听任务丢失，且与新 TaskManager 架构不统一

**新架构（迁移后）**：
- Bot 命令入口仅作为参数转换层，统一调用 `TaskManager.create_task()`
- `TaskExecutor` 负责监听 Handler 的注册、移除、消息回调和异常恢复
- 监听任务状态持久化到 SQLite，进程重启后可恢复 running 状态并重新注册 Handler
- `LISTEN_DOWNLOAD` / `LISTEN_FORWARD` 与 DOWNLOAD / FORWARD 共用同一套 `_execute_download()` / `_execute_forward()` 执行逻辑

**迁移范围**：
- `downloader.py` 中的 `add_listen_chat()` / `cancel_listen()` / `listen_download()` / `listen_forward()` 移除
- `StateManager` 中的 `listen_download_chat` / `listen_forward_chat` 内存状态清理
- `CommandRouter.on_listen()` / `listen_info()` 改为查询 TaskManager
- `REMOVE_LISTEN_*` 回调按钮改为触发任务取消

---

## 四、WebUI 端设计（完整功能）

### 4.1 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| **后端框架** | FastAPI | 异步高性能，与 PRD 技术栈一致 |
| **前端** | 原生 HTML + Alpine.js + Tailwind CSS | 轻量无构建，易于集成 |
| **实时通信** | REST API 轮询 | 前端定时请求获取最新状态（任务列表 5s、监控数据 10s），简化架构 |
| **认证** | URL Token（1 小时有效期） | Bot `/web` 命令生成，链接自动携带，无需手动输入 |
| **数据库** | SQLite | 轻量，无外部依赖 |

> **设计变更说明（v7.0）**: 原 WebSocket 实时推送方案已改为 REST API 定时轮询。
> 理由：简化架构复杂度，避免 WebSocket 连接管理和断线重连逻辑；
> 轮询间隔采用智能策略（有活跃任务时 5s/10s，无活跃任务时停止轮询）。

### 4.2 功能模块

#### 4.2.1 任务管理

| 功能 | 描述 |
|------|------|
| **创建下载任务** | 输入源对话标识符（username / chat_id / t.me 链接），点击「解析」按钮解析为 chat_id，选择消息范围后预览并提交。支持频道/群组和私聊对话（Bot/用户/Saved Messages） |
| **创建转发任务** | 输入源/目标对话标识符（username / chat_id / t.me 链接），均支持「解析」按钮，选择消息范围和类型过滤，支持选择「上传后删除本地文件」（默认勾选），预览后确认提交 |
| **创建监听任务** | 选择 `listen_download` 或 `listen_forward`，输入源对话标识符（和目标标识符），配置媒体类型过滤，创建后 TaskExecutor 统一注册 Handler |
| **创建上传任务** | 输入本地文件路径，支持多文件选择、媒体组配置 |
| **任务队列** | 查看任务列表、开始/重试/取消任务 |
| **任务详情** | 查看任务进度、日志、错误信息 |

#### 4.2.1.1 消息范围选择

所有批量下载/转发任务支持以下五种消息范围选择模式：

| 模式 | 输入方式 | 适用场景 |
|------|---------|---------|
| **最近 N 条** | 输入消息数量 N（N > 0，上限 1000） | 快速获取最新若干条消息，如"最近 10 条视频" |
| **日期范围** | 选择开始日期 + 结束日期 | 按时间维度筛选，如"最近一周的视频" |
| **消息 ID 范围** | 输入最小 ID + 最大 ID（如 `100 - 500`） | 连续消息范围 |
| **多个消息 ID / 链接** | 输入一组消息 ID 或消息链接（每行一个，如 `100`、`150`、`https://t.me/ch/200`） | 零散/不连续的消息 |
| **全部消息** | 勾选「全部消息」复选框 | 处理目标频道/群组历史所有消息 |

**交互示例（最近 N 条模式）：**

```
┌─────────────────────────────────────────────────────┐
│  消息范围选择模式：                                   │
│  [●] 最近 N 条  [ ] 日期范围  [ ] 消息 ID 范围      │
│  [ ] 多个 ID/链接  [ ] 全部消息                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  获取最近消息数量: ┌──────────┐                     │
│                    │ 10       │                     │
│                    └──────────┘                     │
│  💡 上限 1000 条，超出将自动截断                     │
└─────────────────────────────────────────────────────┘
```

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

#### 4.2.1.5 WebUI 任务创建能力矩阵

| 能力 | 频道/群组 | 私聊对话（Bot/用户/Saved） | 说明 |
|------|----------|---------------------------|------|
| **下载任务** | ✅ | ✅ | 输入 username / chat_id / t.me 链接，点击「解析」按钮确认对话信息 |
| **转发任务** | ✅ | ✅ | 源/目标均支持「解析」按钮，私聊和频道可混合配对 |
| **监听下载** | ✅ | ✅ | 创建后 TaskExecutor 统一注册 NewMessage Handler |
| **监听转发** | ✅ | ✅ | 创建后 TaskExecutor 统一注册 NewMessage Handler |
| **上传任务** | ✅ | — | 仅支持频道/群组作为目标 |
| **消息范围 - recent** | ✅ | ✅ | 最近 N 条，上限 1000 |
| **消息范围 - 日期/ID/多 ID/全部** | ✅ | ✅ | 与现有频道任务保持一致 |
| **媒体类型过滤** | ✅ | ✅ | video / photo / document / audio |
| **文件大小过滤** | ✅ | ✅ | min_size / max_size（字节） |

> **解析按钮交互**：
> - 前端对「解析」按钮做至少 3 秒防抖，避免频繁调用 Telegram API 触发 FloodWait
> - 解析成功后展示对话信息卡片（名称、类型、消息数、媒体数）
> - 解析失败时根据错误码展示对应提示（`INVALID_IDENTIFIER` / `USER_NOT_FOUND` / `ACCESS_DENIED` / `RATE_LIMITED`）

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

#### 4.2.4 系统监控（已合并至 Dashboard）

> **设计变更（v7.0）**: 原设计的独立 Monitor 页面已取消，监控功能合并到 Dashboard 页面。
> 日志查看功能已移除，用户可通过 Bot `/status` 命令或终端日志查看任务状态。

| 功能 | 描述 | 所在页面 |
|------|------|----------|
| **实时统计** | 下载/上传速度、任务数、文件数 | Dashboard |
| **任务列表** | 进行中/已完成/失败任务 | Dashboard + Tasks |
| **系统状态** | CPU、内存、磁盘使用率 | Dashboard |

### 4.3 页面设计

#### 4.3.1 页面结构

```
┌─────────────────────────────────────────────────────────┐
│  Header: Logo | 导航 | 设置                              │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│  Sidebar │              Main Content                    │
│          │                                              │
│  - 首页   │  ┌──────────────────────────────────────┐  │
│  - 任务   │  │                                      │  │
│  - 文件   │  │                                      │  │
│  - 配置   │  │                                      │  │
│          │  │                                      │  │
│          │  └──────────────────────────────────────┘  │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

#### 4.3.2 核心页面

| 页面 | 文件 | 功能 |
|------|------|------|
| **Dashboard** | index.html | 概览统计、系统状态、快速操作入口、最近任务 |
| **Tasks** | tasks.html | 任务列表、创建任务、任务详情、任务操作 |
| **Files** | files.html | 文件浏览、选择、上传、媒体组配置 |
| **Settings** | config.html | 配置管理（基础/下载/上传/代理/仓库） |

> **设计变更说明（v7.0）**: 原 Monitor 页面已合并至 Dashboard，日志查看功能移除。

### 4.4 API 设计

#### 4.4.1 认证机制

所有 API 接口均需携带 Token 进行认证：

**认证流程：**
1. 用户通过 Bot `/web` 命令获取带 Token 的访问链接（`?token=xxx`）
2. URL Token 仅用于首次进入页面
3. 首次访问成功后，WebUI 通过 `Set-Cookie` 下发 **HttpOnly Cookie**
4. 后续 AJAX/Fetch 请求使用 `Authorization: Bearer xxx` Header

| 方式 | 说明 |
|------|------|
| **URL 参数** | `?token=xxx`，仅用于首次页面访问 |
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
| `/api/tasks` | POST | 创建任务（需指定 `task_type`：`download`/`forward`/`upload`/`listen_download`/`listen_forward`） | Token |
| `/api/tasks/{id}` | GET | 获取任务详情 | Token |
| `/api/tasks/{id}/start` | POST | 开始任务（手动触发排队中的任务） | Token |
| `/api/tasks/{id}` | DELETE | 取消任务 | Token |
| `/api/tasks/{id}/retry` | POST | 重试任务 | Token |

**频道与消息（带缓存）：**

| 端点 | 方法 | 功能 | 认证 | 缓存 |
|------|------|------|------|------|
| `/api/chats` | GET | 获取用户加入的频道列表（优先读缓存） | Token | 1 小时 |
| `/api/chats/resolve` | GET | 解析对话标识符（username / chat_id / t.me 链接）为 chat_id + 元信息 | Token | 无（避免 chat 信息不一致） |
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

#### 4.4.3 实时数据更新策略（轮询）

> **设计变更（v7.0）**: 原 WebSocket 实时推送方案已改为 REST API 定时轮询。

**轮询策略：**

| 数据类型 | API 端点 | 轮询间隔 | 触发条件 |
|----------|----------|----------|----------|
| 任务列表 | `GET /api/tasks?status=...` | 5 秒 | 存在 pending/running/queued 状态任务 |
| 监控统计 | `GET /api/monitor/stats` | 10 秒 | Dashboard 页面活跃 |
| 资源状态 | `GET /api/monitor/resource/status` | 10 秒 | Dashboard 页面活跃 |

**智能轮询优化：**
- 有活跃任务（pending/running/queued）时启动任务列表轮询
- 所有任务静止（completed/failed/cancelled）时自动停止轮询
- 页面不可见（切换标签页/最小化）时暂停轮询
- 页面重新可见时立即刷新一次并重新评估轮询需求
- 连续请求失败超过 3 次时停止轮询，避免无效请求

**对比原 WebSocket 方案：**

| 维度 | WebSocket（原方案） | REST 轮询（当前方案） |
|------|---------------------|---------------------|
| 实时性 | 毫秒级 | 秒级（5-10s） |
| 架构复杂度 | 高（连接管理、断线重连、心跳） | 低（标准 HTTP 请求） |
| 服务端资源 | 长连接占用 | 按需响应 |
| 浏览器兼容性 | 需考虑代理/防火墙限制 | 无特殊要求 |
| 适用场景 | 高频实时更新（聊天、协作） | 低频状态查询（任务监控） |

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

**任务类型定义：**

| 类型 | 说明 | 支持对话 | 终态 |
|------|------|---------|------|
| `download` | 批量下载任务 | 频道/群组 + 私聊 | `completed` / `failed` / `cancelled` |
| `forward` | 批量转发任务 | 频道/群组 + 私聊 | `completed` / `failed` / `cancelled` |
| `upload` | 本地文件上传任务 | 频道/群组 | `completed` / `failed` / `cancelled` |
| `listen_download` | 实时监听并下载新消息 | 频道/群组 + 私聊 | `running` / `failed` / `cancelled`（不进入 `completed`） |
| `listen_forward` | 实时监听并转发新消息 | 频道/群组 + 私聊 | `running` / `failed` / `cancelled`（不进入 `completed`） |

> **监听任务说明**：`LISTEN_*` 为长期运行任务，创建后进入 `running` 状态并注册 NewMessage Handler；取消或失败时进入对应终态，不会自动 `completed`。

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
    
    async def create_task(self, task_type: TaskType, params: dict, auto_start: bool = True) -> Task:
        """创建任务：资源检查 → 创建 → 排队或执行

        关键逻辑：
        - 标识符解析：优先识别 params.source_identifier，走 IdentifierService.resolve() 解析为 chat_id；
          不存在时回退到 params.chat_id；推导 source_type 写入 Task.extra。
        - 排他校验：对 LISTEN_DOWNLOAD / LISTEN_FORWARD 任务，检查同一 chat_id + task_type
          是否已存在 running / pending 任务，存在则抛出 TaskConflictError（API 转换为 409）。
        - 仓库备份配置解析：params.enable_repository_backup 为 null 时，读取全局配置
          repository.auto_backup_downloads 填充；仅对 DOWNLOAD / LISTEN_DOWNLOAD 生效。
        """
    
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

### 5.4 IdentifierService

**定位**：统一对话标识符解析服务，替代现有三处重复的 `_resolve_chat_id()` 实现，被 TaskManager、Web API、Bot 命令模块共享调用。

**与现有解析函数的关系**：
- `parse_link()`（`module/utils/helpers.py`）：负责链接级解析，返回 `chat_id` + `comment_id` + `topic_id`，被旧架构 `downloader.py` 大量使用，保留不合并
- `extract_info_from_link()`（`module/utils/helpers.py`）：负责链接格式提取，`IdentifierService` 内部复用此函数进行 t.me 链接检测
- `_resolve_chat_id()`（`module/api/routes/tasks.py` / `chats.py`）：负责标识符 → chat_id 转换，将被 `IdentifierService` 替代

**支持输入格式**：

| 格式 | 示例 | 说明 |
|------|------|------|
| 纯数字 ID | `8288406549` | 直接作为 chat_id 返回 |
| @username | `@seseYunBot` | 去掉 `@` 前缀后调用 `get_chat` |
| 纯 username | `seseYunBot` | 直接调用 `get_chat` |
| t.me 链接 | `https://t.me/seseYunBot` | 提取 username 后调用 `get_chat` |

**输出结构**：

```python
@dataclass
class ResolvedChat:
    chat_id: int              # 数字 ID
    chat_type: str            # "bot" | "private" | "channel" | "group" | "supergroup"
    chat_name: str            # 显示名称
    username: str | None      # 用户名（如果有）
    message_count: int        # 消息总数估算
    media_count: int          # 媒体消息数估算
    has_access: bool          # 是否可访问
    is_private: bool          # 是否为私聊类型
```

**错误处理规范**：

| 错误场景 | HTTP 状态码 | 错误码 | 错误消息 |
|---------|-----------|--------|---------|
| 无效输入格式 | 400 | `INVALID_IDENTIFIER` | 标识符格式不正确 |
| 不存在的用户名 | 404 | `USER_NOT_FOUND` | 无法找到该用户/频道 |
| 无对话权限 | 403 | `ACCESS_DENIED` | 您尚未与此用户建立对话 |
| 网络超时 | 504 | `RESOLVE_TIMEOUT` | 解析请求超时，请重试 |
| API 限流 | 429 | `RATE_LIMITED` | 请求过于频繁，请稍后再试（响应体含 `retry_after`） |

```python
class IdentifierService:
    """统一对话标识符解析服务"""

    async def resolve(self, identifier: str) -> ResolvedChat:
        """将 username / chat_id / t.me 链接解析为 ResolvedChat"""

    def _detect_format(self, identifier: str) -> IdentifierFormat:
        """自动检测输入格式"""
```

### 5.5 ConfigManager

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
  chat_id: null                          # 仓库频道 chat_id（与 repository_channel 二选一）
  repository_channel: ""                 # 仓库频道 username（当 auto_backup_downloads=true 时必需）
  auto_backup_downloads: true            # 全局自动备份开关（默认开启）
  dedup_enabled: true                    # 去重功能开关（启用时执行三级去重检查）
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

## 5.6 仓库模式（Repository Mode）

### 5.6.1 概述

仓库模式通过将下载的媒体文件集中存储到指定的 Telegram 频道（仓库频道），实现文件去重和高效分发。核心设计约束：

| 约束 | 说明 |
|------|------|
| **RepositoryManager 是编排层** | 不直接操作文件和 Telegram API，委托 FileManager/Uploader 执行操作 |
| **使用 User Client** | 所有仓库操作使用 User Client（file_id 作用域一致） |
| **file_unique_id 作为去重键** | 跨 Client 稳定标识，file_id 仅用于发送（可能过期） |

### 5.6.2 RepositoryDB - 数据访问层

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

### 5.6.3 RepositoryManager - 编排层

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

### 5.6.4 三级去重机制

| 级别 | 去重键 | 命中行为 | 适用场景 |
|------|--------|---------|---------|
| **L1** | source_chat_id + source_message_id | 跳过下载，直接从仓库分发 | 同一源消息重复转发 |
| **L2** | file_unique_id | 跳过上传，添加 source mapping，从仓库分发 | 同一文件不同消息来源 |
| **L3** | content_hash (SHA256) | 删除本地文件，跳过上传，添加 source mapping，从仓库分发 | 不同格式/来源的相同内容 |

**关键设计：**
- `file_unique_id` 作为去重主键（跨 Client 稳定），`file_id` 仅用于发送（可能过期）
- L1 在下载前检查（`forward()` / `create_download_task()`），L2/L3 在下载完成后检查（`_dedup_before_upload()`）
- L3 命中时删除本地文件以释放磁盘空间

### 5.6.5 分发降级链

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

### 5.6.6 RepositorySync - 增量同步

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

### 5.6.7 降级策略

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

### 5.6.8 集成点

| 模块 | 集成方式 |
|------|---------|
| **TelegramUploader** | 上传成功后触发 `RepositoryManager.on_upload_success`（`_repository_on_upload_success`） |
| **Downloader** | `forward()` 中 L1 去重检查，命中则从仓库分发；`_dedup_before_upload()` 执行 L2/L3 去重 |
| **FileManager** | `upload()` 新增 `source_chat_id`/`source_message_id` 参数；`UploadResult` 新增 `file_unique_id` 字段 |
| **BotCommands** | `/setup_repository` 命令：验证频道输入 → 解析频道 ID → 检查管理员权限 → 保存配置 |
| **ConfigManager** | 新增 `get_repository_config()`、`set_repository_chat_id()`、`validate_repository_config()` |

#### 5.6.9 enable_repository_backup 各模块间流转说明

`enable_repository_backup` 在各模块间的流转路径如下：

| 流转环节 | 说明 |
|---------|------|
| **全局配置** | `repository.auto_backup_downloads`（config.yaml），默认 `true` |
| **任务创建** | `TaskManager.create_task()` 中，若 `params.enable_repository_backup` 为 `null`，读取全局配置 `repository.auto_backup_downloads` 填充；仅对 `DOWNLOAD` / `LISTEN_DOWNLOAD` 生效 |
| **任务执行** | `TaskExecutor` 检查 `params.enable_repository_backup` 决定是否触发仓库备份（调用 FileManager 上传至仓库频道） |
| **WebUI 表单** | 下载/监听下载表单中"备份到仓库频道" checkbox 默认值 = 全局配置值 `repository.auto_backup_downloads`；用户可手动覆盖 |
| **Bot 命令** | `/batch` 创建下载任务时 `enable_repository_backup` 默认继承全局配置，用户无需在 Bot 交互中显式指定 |

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
│   ├── monitor.py           # 任务监控（已集成至 Dashboard）
│   ├── identifier_service.py # [新增] 统一对话标识符解析服务
│   ├── repository_db.py     # [新增] 仓库数据库管理（三张表 CRUD）
│   ├── repository_manager.py # [新增] 仓库频道编排器（去重/分发/回调）
│   ├── repository_sync.py   # [新增] 仓库增量同步器（可选，未启用）
│   └── task_executor.py     # [新增] 任务执行器（已定义，待集成）
│
├── api/                     # [新增] Web API 层
│   ├── __init__.py
│   ├── app.py               # FastAPI 应用
│   ├── routes/              # API 路由
│   │   ├── tasks.py
│   │   ├── files.py
│   │   ├── config.py
│   │   ├── monitor.py
│   │   ├── chats.py         # 频道与消息分析
│   │   └── auth.py
│   └── models/              # 数据模型
│       ├── task.py
│       ├── file.py
│       ├── config.py
│       └── chat.py          # 频道模型
│
├── web/                     # [新增] WebUI 前端
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── vendor/         # 第三方库（Tailwind, Alpine.js）
│   └── templates/
│       ├── index.html       # Dashboard（含系统监控）
│       ├── tasks.html       # 任务管理
│       ├── files.html       # 文件管理
│       ├── config.html      # 系统配置
│       └── login.html       # 登录页
│
├── bot/                     # [新增] Bot 命令模块化
│   ├── __init__.py
│   ├── bot.py               # Bot 主程序 + 原有命令（download/forward/upload/listen 等）
│   ├── commands.py          # WebUI 相关命令（web/web_revoke/batch/status/cancel/repository）
│   └── command_router.py    # 命令路由分发
│
├── downloader.py            # [修改] 核心下载器（保留原有功能）
├── uploader.py              # [修改] 支持媒体组上传
├── integration.py           # [新增] AppContext 全局上下文
└── enums.py                 # [修改] 添加新枚举
```

### 6.2 与现有代码的集成

| 文件 | 修改内容 |
|------|---------|
| **identifier_service.py** | 1. 新增统一对话标识符解析服务<br>2. 支持 username / chat_id / t.me 链接 → `ResolvedChat`<br>3. 被 TaskManager、Web API、Bot 命令模块共享调用 |
| **task_manager.py** | 1. 扩展 `TaskType`：新增 `listen_download`、`listen_forward`<br>2. 扩展 `create_task()`：支持 `source_identifier` / `target_identifier` 参数<br>3. 扩展 `RangeMode`：新增 `recent` 最近 N 条模式<br>4. 新增 `LISTEN_*` 任务的 chat_id + task_type 排他性校验（409 冲突）<br>5. 支持监听任务动态 Item 生成与持久化 |
| **task_executor.py** | 1. 新增 `LISTEN_DOWNLOAD` / `LISTEN_FORWARD` 执行分支<br>2. 新增 `_start_listener()` / `_stop_listener()` Handler 生命周期管理<br>3. 复用 `_execute_download()` / `_execute_forward()` 处理私聊和频道任务<br>4. 支持进程重启后恢复 running 状态监听任务 |
| **bot.py** | 1. 简化命令体系<br>2. 添加 `/web` 命令<br>3. 复杂操作引导到 WebUI<br>4. 保留原有命令兼容性<br>5. 注册 `/setup_repository` 命令 handler |
| **command_router.py** | 1. `on_listen()` / `listen_info()` 改为调用 TaskManager，替代直接注册 Handler<br>2. `REMOVE_LISTEN_*` 回调按钮改为触发任务取消<br>3. 复用 IdentifierService 解析私聊标识符 |
| **app.py** | 1. 集成 TaskManager<br>2. 集成 ConfigManager<br>3. 启动 Web API 服务<br>4. 初始化 RepositoryManager 和 RepositorySync |
| **main.py** | 1. 支持同时启动 Bot 和 Web API<br>2. 添加启动参数控制 |
| **enums.py** | 1. 新增 TaskType、TaskStatus 枚举<br>2. 新增 InteractionMode 枚举 |
| **downloader.py** | 1. forward() 中仓库模式启用时执行 L1 去重检查，命中则从仓库分发<br>2. 下载完成后执行 L2/L3 去重检查（`_dedup_before_upload`）<br>3. 为上传任务附加 source_chat_id/source_message_id<br>4. 移除旧监听实现：`add_listen_chat()` / `cancel_listen()` / `listen_download()` / `listen_forward()` |
| **uploader.py** | 1. 上传成功后触发 `_repository_on_upload_success` 回调<br>2. 去重命中时调用 `_dedup_distribute` 从仓库分发<br>3. UploadTask 支持 source_chat_id/source_message_id 字段 |
| **state_manager.py** | 1. 清理 `listen_download_chat` / `listen_forward_chat` 内存状态存储 |

### 6.3 启动方式

```bash
# 启动 Web API + Telegram Client
python main.py

# 指定 Web 服务端口
python main.py --port 8080
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
| v7.0 | 2026-06-24 | **WebUI 架构精简**：<br>1. WebSocket 方案改为 REST API 轮询<br>2. Monitor 页面合并至 Dashboard，日志查看功能移除<br>3. Bot 命令体系补充完整命令列表（20+ 命令）<br>4. 文件结构更新：移除 websocket/ 目录和 monitor.html<br>5. 新增 task_executor.py、chats.py、chat.py 等组件说明<br>6. Bot 命令模块化：bot/ 目录结构说明 | SOLO |
| v7.1 | 2026-06-24 | **集成与清理**：<br>1. 移除 `--web-only` 模式（功能残缺、无真实使用场景）<br>2. 集成 TaskExecutor 使 Web 任务可实际执行<br>3. 启用 RepositorySync 仓库自动同步<br>4. 修复 Dashboard 分页参数 bug<br>5. 清理所有 mock 数据降级分支和条件判断 | SOLO |
| v7.2 | 2026-07-03 | **私聊对话文件操作 + 监听任务架构迁移**：<br>1. 新增私聊对话文件操作能力：支持 Bot / 用户 / Saved Messages 通过 username / chat_id 访问<br>2. 新增 IdentifierService 统一解析服务：替代多处 `_resolve_chat_id()` 重复实现<br>3. 扩展任务类型：新增 `LISTEN_DOWNLOAD`、`LISTEN_FORWARD`<br>4. 扩展消息范围模式：新增 `recent` 最近 N 条模式<br>5. 私聊下载/转发仅通过 WebUI 创建；监听任务在迁移后同时支持 WebUI 和 Bot 命令<br>6. 监听任务架构迁移：从 Bot 命令 + 内存 Handler + StateManager 迁移至 TaskManager / TaskExecutor + SQLite 持久化 | SOLO |

---

> **文档结束**
