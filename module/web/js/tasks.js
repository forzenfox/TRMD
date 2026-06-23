/**
 * 任务管理逻辑模块
 * 
 * 处理任务列表、创建、操作（启动/取消/重试/删除）
 * WebSocket 实时更新任务状态
 */

class TaskManager {
  constructor() {
    this.tasks = [];
    this.loading = false;
    this.error = null;
    this.filter = 'all'; // all, pending, running, completed, failed, cancelled
    this.selectedTask = null;
    this.showDetailDrawer = false;
    this.showCreateModal = false;
    this.ws = null;
    
    // 分页
    this.page = 1;
    this.pageSize = 20;
    this.totalTasks = 0;
    this.totalPages = 0;

    // 创建任务表单
    this.createForm = this._resetCreateForm();
  }

  /**
   * 重置创建表单
   */
  _resetCreateForm() {
    return {
      taskName: '',
      taskType: 'download', // download, forward, upload
      sourceChat: '',
      targetChat: '',
      messageRangeMode: 'id_range', // date_range, id_range, id_list, all
      startDate: '',
      endDate: '',
      minId: '',
      maxId: '',
      rawItems: '',
      typeFilters: [], // video, photo, document, audio, etc.
      savePath: '',
      deleteAfterUpload: false,
      sendAsMediaGroup: false,
    };
  }

  /**
   * 加载任务列表
   * @param {boolean} resetPage - 是否重置到第一页
   */
  async loadTasks(resetPage = false) {
    this.loading = true;
    this.error = null;

    if (resetPage) {
      this.page = 1;
    }

    try {
      const offset = (this.page - 1) * this.pageSize;
      const params = {
        offset: offset,
        limit: this.pageSize,
      };

      if (this.filter !== 'all') {
        params.status = this.filter;
      }

      const response = await api.getTasks(params);
      this.tasks = response.items || [];
      this.totalTasks = response.total || 0;
      this.totalPages = Math.ceil(this.totalTasks / this.pageSize) || 1;
    } catch (error) {
      this.error = error.message;
      console.error('加载任务列表失败:', error);
    } finally {
      this.loading = false;
    }
  }

  /**
   * 创建新任务
   */
  async createTask() {
    try {
      const payload = this._buildCreatePayload();
      const task = await api.createTask(payload);
      
      // 关闭弹窗，重置表单
      this.showCreateModal = false;
      this.createForm = this._resetCreateForm();
      
      // 重新加载任务列表
      await this.loadTasks(true);
      
      // 显示成功通知
      this._notify('success', '任务创建成功');
      
      return task;
    } catch (error) {
      this._notify('error', `创建任务失败: ${error.message}`);
      throw error;
    }
  }

  /**
   * 构建创建任务的请求体
   */
  _buildCreatePayload() {
    const params = {};

    // 辅助：将嵌套消息范围展平为后端期望的扁平字段
    const _flattenRange = (range) => {
      params.range_mode = range.mode;
      if (range.mode === 'id_range') {
        params.min_id = range.min_id;
        params.max_id = range.max_id;
      } else if (range.mode === 'date_range') {
        params.start_date = range.start_date;
        params.end_date = range.end_date;
      } else if (range.mode === 'multiple_ids') {
        params.message_list = range.message_list;
      }
    };

    if (this.createForm.taskType === 'download') {
      params.chat_id = this.createForm.sourceChat;
      _flattenRange(this._buildMessageRange());
    } else if (this.createForm.taskType === 'forward') {
      params.chat_id = this.createForm.sourceChat;
      params.forward_target = this.createForm.targetChat;
      _flattenRange(this._buildMessageRange());
    } else if (this.createForm.taskType === 'upload') {
      params.chat_id = this.createForm.target_chat;
      params.file_paths = this.createForm.selectedFiles || [];
    }

    return {
      task_type: this.createForm.taskType,
      params,
    };
  }

  /**
   * 构建消息范围对象
   */
  _buildMessageRange() {
    const mode = this.createForm.messageRangeMode;
    
    switch (mode) {
      case 'date_range':
        return {
          mode: 'date_range',
          start_date: this.createForm.startDate,
          end_date: this.createForm.endDate,
        };
      
      case 'id_range':
        return {
          mode: 'id_range',
          min_id: parseInt(this.createForm.minId),
          max_id: parseInt(this.createForm.maxId),
        };
      
      case 'multiple_ids':
        const messageList = this.createForm.rawItems
          .split('\n')
          .map(line => line.trim())
          .filter(line => line.length > 0);
        return {
          mode: 'multiple_ids',
          message_list: messageList,
        };
      
      case 'all':
        return { mode: 'all' };
      
      default:
        return { mode: 'all' };
    }
  }

  /**
   * 生成默认任务名称
   */
  _generateTaskName() {
    const typeNames = {
      download: '下载',
      forward: '转发',
      upload: '上传',
    };
    const typeName = typeNames[this.createForm.taskType] || '任务';
    const timestamp = new Date().toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).replace(/[/:]/g, '');
    return `${typeName}_${timestamp}`;
  }

  /**
   * 启动任务
   * @param {string} taskId - 任务 ID
   */
  async startTask(taskId) {
    try {
      await api.startTask(taskId);
      await this.loadTasks();
      this._notify('success', '任务已启动');
    } catch (error) {
      this._notify('error', `启动任务失败: ${error.message}`);
    }
  }

  /**
   * 取消任务
   * @param {string} taskId - 任务 ID
   */
  async cancelTask(taskId) {
    try {
      await api.cancelTask(taskId);
      await this.loadTasks();
      this._notify('success', '任务已取消');
    } catch (error) {
      this._notify('error', `取消任务失败: ${error.message}`);
    }
  }

  /**
   * 重试任务
   * @param {string} taskId - 任务 ID
   */
  async retryTask(taskId) {
    try {
      await api.retryTask(taskId);
      await this.loadTasks();
      this._notify('success', '任务已重试');
    } catch (error) {
      this._notify('error', `重试任务失败: ${error.message}`);
    }
  }

  /**
   * 删除任务
   * @param {string} taskId - 任务 ID
   */
  async deleteTask(taskId) {
    if (!confirm('确定要删除此任务吗？此操作不可撤销。')) {
      return;
    }

    try {
      await api.deleteTask(taskId);
      await this.loadTasks();
      this._notify('success', '任务已删除');
    } catch (error) {
      this._notify('error', `删除任务失败: ${error.message}`);
    }
  }

  /**
   * 查看任务详情
   * @param {object} task - 任务对象
   */
  viewTaskDetail(task) {
    this.selectedTask = task;
    this.showDetailDrawer = true;
  }

  /**
   * 关闭详情抽屉
   */
  closeDetailDrawer() {
    this.showDetailDrawer = false;
    this.selectedTask = null;
  }

  /**
   * 设置过滤条件
   * @param {string} filter - 过滤条件
   */
  setFilter(filter) {
    this.filter = filter;
    this.loadTasks(true);
  }

  /**
   * 设置页码
   * @param {number} page - 页码
   */
  setPage(page) {
    if (page < 1 || page > this.totalPages) return;
    this.page = page;
    this.loadTasks();
  }

  /**
   * 解析多行 ID/链接输入
   */
  getParsedItemCount() {
    if (!this.createForm.rawItems) return 0;
    return this.createForm.rawItems
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0).length;
  }

  /**
   * 验证创建表单
   */
  validateCreateForm() {
    const form = this.createForm;
    const errors = [];

    // 验证源频道
    if ((form.taskType === 'download' || form.taskType === 'forward') && !form.sourceChat) {
      errors.push('请输入源频道');
    }

    // 验证目标频道
    if ((form.taskType === 'forward' || form.taskType === 'upload') && !form.targetChat) {
      errors.push('请输入目标频道');
    }

    // 验证消息范围
    if (form.taskType !== 'upload') {
      if (form.messageRangeMode === 'date_range') {
        if (!form.startDate || !form.endDate) {
          errors.push('请选择日期范围');
        } else if (new Date(form.startDate) > new Date(form.endDate)) {
          errors.push('开始日期不能晚于结束日期');
        }
      } else if (form.messageRangeMode === 'id_range') {
        const minId = parseInt(form.minId);
        const maxId = parseInt(form.maxId);
        if (!minId || !maxId) {
          errors.push('请输入消息 ID 范围');
        } else if (minId > maxId) {
          errors.push('最小 ID 不能大于最大 ID');
        } else if (minId < 1 || maxId < 1) {
          errors.push('消息 ID 必须为正整数');
        }
      } else if (form.messageRangeMode === 'id_list') {
        const count = this.getParsedItemCount();
        if (count === 0) {
          errors.push('请输入至少一个消息 ID 或链接');
        }
      }
    }

    // 验证上传文件
    if (form.taskType === 'upload' && (!form.selectedFiles || form.selectedFiles.length === 0)) {
      errors.push('请选择至少一个文件');
    }

    return errors;
  }

  /**
   * 启动 WebSocket 连接用于任务状态更新
   */
  connectWebSocket() {
    // 防重入：如果已有连接正在建立或已连接，先不重复创建
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      console.log('[WS] 跳过重复连接，当前状态:', this.ws.readyState);
      return;
    }
    // 关闭旧连接（CLOSED 或 CLOSING 状态）
    if (this.ws) {
      console.log('[WS] 关闭旧连接，状态:', this.ws.readyState);
      this.ws.close();
    }
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }

    const token = api.token;
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/tasks?token=${token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('任务 WebSocket 连接已建立');
      // 发送初始心跳，触发后端进入消息循环
      this.ws.send(JSON.stringify({ type: 'ping' }));
      // 启动定时心跳，每 25 秒发送一次保持连接活跃
      this._heartbeatTimer = setInterval(() => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 25000);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // 处理服务器心跳
        if (data.type === 'ping') {
          this.ws.send(JSON.stringify({ type: 'pong' }));
          return;
        }
        
        // 处理服务器心跳响应
        if (data.type === 'pong') {
          return;
        }
        
        // 处理连接成功消息
        if (data.type === 'connected') {
          console.log('WebSocket 连接已确认:', data.payload?.client_id);
          return;
        }
        
        // 处理任务状态更新
        this._handleTaskUpdate(data);
      } catch (error) {
        console.error('处理 WebSocket 消息失败:', error);
      }
    };

    this.ws.onclose = (event) => {
      console.log('[WS] 连接关闭: code=' + event.code + ', reason="' + event.reason + '", wasClean=' + event.wasClean);
      if (this._heartbeatTimer) {
        clearInterval(this._heartbeatTimer);
        this._heartbeatTimer = null;
      }
      setTimeout(() => this.connectWebSocket(), 3000);
    };

    this.ws.onerror = (error) => {
      console.error('[WS] 错误事件:', error);
    };
  }

  /**
   * 处理任务状态更新
   * @param {object} data - WebSocket 数据
   */
  _handleTaskUpdate(data) {
    // 服务端消息嵌套在 payload 中
    const payload = data.payload || data;
    const { task_id, status, progress, speed, eta, message } = payload;

    // 在任务列表中找到对应任务并更新
    const taskIndex = this.tasks.findIndex(t => t.id === task_id);
    if (taskIndex !== -1) {
      const task = this.tasks[taskIndex];
      task.status = status;
      task.progress = progress || task.progress;
      task.speed = speed || task.speed;
      task.eta = eta || task.eta;
      task.message = message || task.message;
      task.updated_at = new Date().toISOString();

      // 触发 Alpine.js 响应式更新
      this.tasks = [...this.tasks];
    }

    // 如果详情抽屉打开的是这个任务，也更新
    if (this.selectedTask && this.selectedTask.id === task_id) {
      this.selectedTask = { ...this.selectedTask, ...payload };
    }
  }

  /**
   * 显示通知
   * @param {string} type - 通知类型
   * @param {string} message - 通知内容
   */
  _notify(type, message) {
    // 使用全局通知系统（如果存在）
    if (window.showNotification) {
      window.showNotification(type, message);
    } else {
      console.log(`[${type}] ${message}`);
    }
  }

  /**
   * 关闭创建弹窗
   */
  closeCreateModal() {
    this.showCreateModal = false;
    this.createForm = this._resetCreateForm();
  }

  /**
   * 获取状态对应的 CSS 类
   * @param {string} status - 任务状态
   */
  getStatusBadgeClass(status) {
    const classMap = {
      pending: 'badge-pending',
      queued: 'badge-queued',
      running: 'badge-running',
      completed: 'badge-completed',
      failed: 'badge-failed',
      cancelled: 'badge-cancelled',
    };
    return classMap[status] || 'badge-pending';
  }

  /**
   * 获取状态对应的中文文本
   * @param {string} status - 任务状态
   */
  getStatusText(status) {
    const textMap = {
      pending: '等待中',
      queued: '排队中',
      running: '执行中',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消',
    };
    return textMap[status] || status;
  }

  /**
   * 获取任务类型对应的中文文本
   * @param {string} type - 任务类型
   */
  getTypeText(type) {
    const textMap = {
      download: '下载',
      forward: '转发',
      upload: '上传',
    };
    return textMap[type] || type;
  }

  /**
   * 格式化文件大小
   * @param {number} bytes - 字节数
   */
  formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  }

  /**
   * 格式化速度
   * @param {number} bytesPerSecond - 每秒字节数
   */
  formatSpeed(bytesPerSecond) {
    if (!bytesPerSecond) return '0 B/s';
    return this.formatFileSize(bytesPerSecond) + '/s';
  }

  /**
   * 格式化时间
   * @param {string} isoString - ISO 时间字符串
   */
  formatTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  /**
   * 格式化 ETA（预计剩余时间）
   * @param {number} seconds - 秒数
   */
  formatETA(seconds) {
    if (!seconds) return '-';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}小时${minutes}分钟`;
    } else if (minutes > 0) {
      return `${minutes}分钟${secs}秒`;
    } else {
      return `${secs}秒`;
    }
  }
}

// 创建单例实例
const taskManager = new TaskManager();

// 导出供 Alpine.js 使用
window.taskManager = taskManager;
