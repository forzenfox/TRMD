# Telegram Bot 交互体验增强设计文档

> **项目名称**: Telegram_Restricted_Media_Downloader  
> **文档版本**: v1.0  
> **创建日期**: 2026-06-12  
> **作者**: SOLO  
> **状态**: 待审核

---

## 一、项目背景

### 1.1 痛点分析

当前项目的 Bot 交互存在以下用户体验痛点：

| 痛点 | 描述 | 影响 |
|------|------|------|
| **命令格式繁琐** | 转发命令必须按 `/forward 原始频道 目标频道 起始ID 结束ID` 格式书写，即使是单条文件转发也要严格按照格式 | 用户记忆负担重，容易出错 |
| **本地文件媒体组上传缺失** | 本地文件无法满足将多个文件上传到同一媒体组的需求，每次只能上传单个文件 | 无法保持文件的媒体组关联，影响浏览体验 |
| **批量操作效率低** | 批量下载/转发需要预先整理好所有链接，一次性发送长命令 | 操作繁琐，容易遗漏或格式错误 |

### 1.2 设计目标

在现有 Bot 基础上增加交互式操作模式，通过**状态机管理**实现：

1. **交互式批量下载/转发** - 用户逐条发送链接，Bot 自动收集并批量处理
2. **本地文件选择 + 媒体组上传** - 可视化文件列表选择，支持多文件作为同一媒体组上传
3. **向后兼容** - 所有原有命令保持不变，新功能作为可选增强

---

## 二、系统架构

### 2.1 状态机设计

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

### 2.2 核心概念

| 概念 | 说明 |
|------|------|
| **InteractionMode** | 交互模式类型枚举（批量下载、批量转发、相册选择） |
| **InteractionState** | 单个用户会话的状态对象 |
| **InteractionManager** | 全局交互状态管理器，管理所有活跃会话 |
| **超时机制** | 默认 5 分钟无操作自动退出交互模式，防止 Bot 状态卡死 |

---

## 三、功能详细设计

### 3.1 功能一：交互式批量下载

#### 3.1.1 触发方式

- **新命令**: `/download_batch`
- **原有命令保留**: `/download` 命令格式完全不变

#### 3.1.2 交互流程

```
用户: /download_batch
Bot: 📥 已进入批量下载模式
     请逐条发送下载链接（每条消息一条链接）
     发送 /done 结束，发送 /cancel 取消
     当前: 0 条链接待处理
     [/done 结束] [/cancel 取消]

用户: https://t.me/channel/123
Bot: ✅ 已添加: https://t.me/channel/123
     当前: 1 条链接待处理
     [/done 结束] [/cancel 取消]

用户: https://t.me/channel/456
Bot: ✅ 已添加: https://t.me/channel/456
     当前: 2 条链接待处理
     [/done 结束] [/cancel 取消]

用户: /done
Bot: 📥 开始处理 2 条下载链接...
     （调用现有下载逻辑）
     批量下载模式已关闭
```

#### 3.1.3 状态设计

```python
class InteractionState:
    mode: str = "download_batch"  # 交互模式类型
    user_id: int                  # 用户 Telegram ID
    target_link: str | None       # 转发目标频道（转发模式使用）
    pending_items: list[str]      # 待处理链接列表
    timeout: int = 300            # 超时时间（秒），默认 5 分钟
    created_at: datetime          # 会话创建时间
    last_activity: datetime       # 最后活动时间
```

#### 3.1.4 超时机制

- 默认 **5 分钟**无操作自动退出交互模式
- 退出时清理所有待处理数据
- 每次用户输入重置超时计时
- 超时前 1 分钟发送提醒消息

---

### 3.2 功能二：交互式批量转发

#### 3.2.1 触发方式

- **新命令**: `/forward_batch`
- **原有命令保留**: `/forward` 命令格式完全不变

#### 3.2.2 交互流程

```
用户: /forward_batch
Bot: 📤 批量转发模式
     请先发送目标频道链接：
     例如: https://t.me/target_channel

用户: https://t.me/target_channel
Bot: ✅ 目标频道已设置
     现在请逐条发送源频道链接（每条消息一条链接）
     支持格式:
       - https://t.me/source_channel （转发全部）
       - https://t.me/source_channel/100 （转发单条）
       - https://t.me/source_channel/100-200 （转发范围）
     当前: 0 条链接待处理
     [/done 结束] [/cancel 取消]

用户: https://t.me/source/100-200
Bot: ✅ 已添加: https://t.me/source/100-200 (101 条消息)
     当前: 1 条链接待处理，预计转发 101 条消息
     [/done 结束] [/cancel 取消]

用户: /done
Bot: 📤 开始处理 1 条转发任务，预计转发 101 条消息...
     （调用现有转发逻辑）
     批量转发模式已关闭
```

---

### 3.3 功能三：本地文件选择 + 媒体组上传

#### 3.3.1 触发方式

- **新命令**: `/upload_album`
- **原有命令保留**: `/upload` 和 `/upload_r` 命令格式完全不变

#### 3.3.2 交互流程（文件数量 >= 10，编号模式）

```
用户: /upload_album
Bot: 📁 请选择要上传的文件
     请输入文件所在目录路径：
     （或发送 . 表示当前工作目录）

用户: /downloads/videos
Bot: 📂 找到 35 个文件，共 2.5 GB
     由于文件数量较多，请使用编号选择：
     
     1. video_001.mp4 (85 MB)
     2. video_002.mp4 (120 MB)
     ...
     35. video_035.mp4 (65 MB)
     
     选择方式:
       - 单个或多个: 1,3,5
       - 范围: 1-10
       - 全选: all
     输入 /done 确认选择，/cancel 取消

用户: 1-5,8,10-15
Bot: ✅ 已选择 12 个文件，共 1.2 GB
     请输入目标频道链接：
     
用户: https://t.me/target_channel
Bot: 📤 开始上传媒体组...
     (1/12) video_001.mp4
     (2/12) video_002.mp4
     ...
     ✅ 媒体组上传完成！共 12 个文件
```

#### 3.3.3 交互流程（文件数量 < 10，按钮模式）

```
Bot: 📂 找到 5 个文件:
     
     [✓] video_001.mp4 (85 MB)
     [✓] video_002.mp4 (120 MB)
     [  ] video_003.mp4 (45 MB)
     [✓] video_004.mp4 (90 MB)
     [✓] video_005.mp4 (65 MB)
     
     点击按钮切换选择状态
     [/done 确认] [/cancel 取消]
```

#### 3.3.4 媒体组上传技术要点

| 要点 | 说明 |
|------|------|
| **API 使用** | 使用 pyrogram 的 `send_media_group` API |
| **InputMedia 对象** | 需要先将文件收集为 InputMedia 对象列表 |
| **数量限制** | Telegram 限制单个媒体组最多 **10 个文件** |
| **自动拆分** | 超过 10 个文件时自动拆分为多个媒体组 |
| **文件类型** | 支持图片、视频、音频等媒体类型，文档类型不支持媒体组 |

---

## 四、技术实现方案

### 4.1 文件结构变更

```
module/
├── interaction.py      # [新增] 状态机和交互管理核心模块
├── bot.py              # [修改] 添加新命令 handler
├── uploader.py         # [修改] 支持媒体组上传
├── enums.py            # [修改] 添加新枚举
└── language.py         # [修改] 添加新交互文案
```

### 4.2 InteractionManager 设计

```python
class InteractionManager:
    """全局交互状态管理器"""
    
    active_sessions: dict[int, InteractionState]  # user_id -> 会话状态
    
    def start_session(self, user_id: int, mode: InteractionMode, **kwargs) -> bool:
        """启动新的交互会话"""
    
    def add_item(self, user_id: int, item: str) -> bool:
        """添加待处理项到当前会话"""
    
    def end_session(self, user_id: int, execute: bool = True) -> list:
        """结束会话，返回所有待处理项"""
    
    def cancel_session(self, user_id: int) -> bool:
        """取消会话"""
    
    def get_session(self, user_id: int) -> InteractionState | None:
        """获取用户当前会话状态"""
    
    def check_timeout(self) -> list[int]:
        """检查超时会话，返回超时用户 ID 列表"""
    
    def reset_timeout(self, user_id: int) -> None:
        """重置用户会话超时计时"""
```

### 4.3 与现有代码的集成点

| 文件 | 修改内容 |
|------|---------|
| **bot.py** | 1. 添加 `/download_batch`、`/forward_batch`、`/upload_album` 命令 handler<br>2. 扩展 `handle_keyword_input` 处理交互模式下的普通消息<br>3. 在 `COMMANDS` 列表中注册新命令 |
| **interaction.py** | 新增核心模块，包含 `InteractionMode`、`InteractionState`、`InteractionManager` 类 |
| **uploader.py** | 新增 `upload_media_group()` 方法，支持多文件媒体组上传 |
| **enums.py** | 新增 `InteractionMode` 枚举，`BotCallbackText` 和 `BotButton` 新增交互相关文本 |
| **language.py** | 新增交互模式相关的多语言文案 |
| **app.py** | 在定时任务中添加超时会话检查 |

### 4.4 关键集成代码示意

#### 4.4.1 Bot 消息处理扩展

```python
# 在 bot.py 的消息处理流程中，优先检查交互模式
async def handle_keyword_input(self, ...):
    # 检查用户是否处于交互模式
    session = self.interaction_manager.get_session(user_id)
    if session:
        # 重置超时
        self.interaction_manager.reset_timeout(user_id)
        
        # 处理特殊命令
        if text == '/done':
            items = self.interaction_manager.end_session(user_id)
            await self.execute_batch_task(user_id, items)
            return
        elif text == '/cancel':
            self.interaction_manager.cancel_session(user_id)
            await self.send_cancel_notice(user_id)
            return
        
        # 根据模式处理输入
        if session.mode == InteractionMode.DOWNLOAD_BATCH:
            await self.process_download_link(user_id, text)
        elif session.mode == InteractionMode.FORWARD_BATCH:
            if not session.target_link:
                session.target_link = text  # 第一条消息作为目标频道
            else:
                await self.process_forward_link(user_id, text)
        elif session.mode == InteractionMode.ALBUM_SELECT:
            await self.process_file_selection(user_id, text)
```

#### 4.4.2 媒体组上传

```python
# 在 uploader.py 中新增
async def upload_media_group(
    self,
    client: pyrogram.Client,
    chat_id: Union[int, str],
    file_paths: List[str],
    progress_callback=None
) -> List[pyrogram.types.Message]:
    """
    将多个文件作为媒体组上传到指定频道
    
    Args:
        client: Pyrogram 客户端
        chat_id: 目标频道 ID 或链接
        file_paths: 文件路径列表
        progress_callback: 进度回调函数
        
    Returns:
        上传成功的消息列表
        
    Note:
        - Telegram 限制单个媒体组最多 10 个文件
        - 超过 10 个文件时自动拆分为多个媒体组
        - 文档类型不支持媒体组，使用单个上传
    """
    MAX_MEDIA_GROUP_SIZE = 10
    
    # 按 10 个拆分
    batches = [
        file_paths[i:i + MAX_MEDIA_GROUP_SIZE] 
        for i in range(0, len(file_paths), MAX_MEDIA_GROUP_SIZE)
    ]
    
    all_messages = []
    for batch in batches:
        media_group = []
        for file_path in batch:
            # 根据文件类型创建对应的 InputMedia 对象
            input_media = self._create_input_media(file_path)
            media_group.append(input_media)
        
        # 发送媒体组
        messages = await client.send_media_group(
            chat_id=chat_id,
            media=media_group
        )
        all_messages.extend(messages)
        
        if progress_callback:
            await progress_callback(batch, messages)
    
    return all_messages
```

---

## 五、枚举和常量设计

### 5.1 InteractionMode 枚举

```python
class InteractionMode(Enum):
    """交互模式类型"""
    DOWNLOAD_BATCH = "download_batch"    # 批量下载模式
    FORWARD_BATCH = "forward_batch"      # 批量转发模式
    ALBUM_SELECT = "album_select"        # 相册文件选择模式
```

### 5.2 新增 BotCallbackText

```python
class BotCallbackText:
    # 交互模式相关
    BATCH_DOWNLOAD = "batch_download"
    BATCH_FORWARD = "batch_forward"
    ALBUM_UPLOAD = "album_upload"
    ENTER_INTERACTION_MODE = "enter_interaction_mode"
    EXIT_INTERACTION_MODE = "exit_interaction_mode"
    TIMEOUT_WARNING = "timeout_warning"
```

### 5.3 新增 BotButton

```python
class BotButton:
    # 交互模式按钮
    DONE = "✅ 完成"
    CANCEL = "❌ 取消"
    SELECT_ALL = "全选"
    DESELECT_ALL = "全不选"
```

---

## 六、非功能性需求

| 类别 | 需求 | 验收标准 |
|------|------|---------|
| **兼容性** | 所有原有命令保持不变 | 现有 `/download`、`/forward`、`/upload` 命令功能不受影响 |
| **超时保护** | 交互模式默认超时机制 | 5 分钟无操作自动退出，超时前 1 分钟提醒 |
| **并发安全** | 多用户独立会话状态 | 不同用户的交互会话互不干扰 |
| **错误处理** | 无效输入友好提示 | 链接格式错误、文件不存在等情况给出明确提示 |
| **状态恢复** | Bot 重启后清理残留状态 | 重启后自动清理 `active_sessions` |
| **资源清理** | 超时/取消时清理数据 | 释放临时文件和会话数据 |
| **测试覆盖** | 单元测试 + 集成测试 | 核心交互流程单元测试覆盖率 ≥ 80% |

---

## 七、里程碑计划

| 阶段 | 内容 | 前置条件 |
|------|------|---------|
| **M1: 交互框架** | InteractionManager、InteractionState、超时机制 | 设计文档审核通过 |
| **M2: 批量下载** | `/download_batch` 命令、链接收集、批量处理 | M1 完成 |
| **M3: 批量转发** | `/forward_batch` 命令、目标频道设置、批量转发 | M2 完成 |
| **M4: 文件选择** | `/upload_album` 命令、文件列表展示、混合选择模式 | M1 完成 |
| **M5: 媒体组上传** | `upload_media_group()` 方法、自动拆分、进度显示 | M4 完成 |
| **M6: 测试与优化** | 单元测试、集成测试、错误处理完善 | M2-M5 完成 |

---

## 八、附录

### 8.1 Telegram 媒体组限制

| 限制 | 说明 |
|------|------|
| **最大文件数** | 单个媒体组最多 10 个文件 |
| **支持类型** | 图片、视频、音频 |
| **不支持类型** | 文档（document）、贴纸、GIF |
| **总大小限制** | 普通用户 2GB，会员用户 4GB（单文件限制） |

### 8.2 参考资源

- [pyrogram send_media_group 文档](https://docs.pyrogram.org/api/methods/send_media_group)
- [python-telegram-bot 文档](https://docs.python-telegram-bot.org/)
- [Telegram Bot API - InputMedia](https://core.telegram.org/bots/api#inputmedia)

---

## 九、变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-12 | 初始版本，完成交互体验增强设计 | SOLO |

---

> **文档结束**
