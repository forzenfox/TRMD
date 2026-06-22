/**
 * API 封装模块
 * 
 * 统一的 REST API 请求处理，包含：
 * - Token 自动注入
 * - 错误处理（401 自动跳转）
 * - 统一响应解析
 */

class ApiClient {
  constructor() {
    this.baseUrl = '';
    this.token = null;
    this.tokenSource = null; // 'url' | 'cookie' | 'storage'
    
    // 初始化 Token
    this._initToken();
  }

  /**
   * 初始化 Token
   * 优先级: URL 参数 > Cookie > localStorage
   */
  _initToken() {
    // 1. 检查 URL 参数
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');
    
    if (urlToken) {
      this.token = urlToken;
      this.tokenSource = 'url';
      // 保存 token 到全局变量，供 Alpine.js 组件读取
      window.__urlToken = urlToken;
      // 首次验证成功后清理 URL 中的 token 参数
      this._cleanUrlToken();
      return;
    }

    // 2. 检查 localStorage（备用方案）
    const storedToken = localStorage.getItem('trmd_token');
    if (storedToken) {
      this.token = storedToken;
      this.tokenSource = 'storage';
    }
  }

  /**
   * 清理 URL 中的 token 参数，防止链接泄露
   */
  _cleanUrlToken() {
    const url = new URL(window.location.href);
    url.searchParams.delete('token');
    window.history.replaceState({}, document.title, url.toString());
  }

  /**
   * 设置 Token
   * @param {string} token - 认证 Token
   * @param {boolean} persist - 是否持久化到 localStorage
   */
  setToken(token, persist = false) {
    this.token = token;
    this.tokenSource = 'storage';
    
    if (persist) {
      localStorage.setItem('trmd_token', token);
    }
  }

  /**
   * 清除 Token
   */
  clearToken() {
    this.token = null;
    this.tokenSource = null;
    localStorage.removeItem('trmd_token');
  }

  /**
   * 获取 Authorization Header
   */
  _getAuthHeaders() {
    const headers = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  /**
   * 统一请求方法
   * @param {string} method - HTTP 方法
   * @param {string} path - API 路径
   * @param {object|null} body - 请求体
   * @returns {Promise<any>}
   */
  async request(method, path, body = null) {
    const headers = {
      'Content-Type': 'application/json',
      ...this._getAuthHeaders(),
    };

    const options = {
      method,
      headers,
    };

    if (body && method !== 'GET' && method !== 'HEAD') {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${this.baseUrl}${path}`, options);

      // 处理 401 未授权
      if (response.status === 401) {
        this.clearToken();
        window.location.href = '/web/login.html?redirect=' + encodeURIComponent(window.location.pathname);
        return null;
      }

      // 处理 403 禁止访问
      if (response.status === 403) {
        window.location.href = '/web/error.html?code=403';
        return null;
      }

      // 处理 5xx 服务器错误
      if (response.status >= 500) {
        const errorText = await response.text();
        throw new Error(`服务器错误 (${response.status}): ${errorText}`);
      }

      // 处理 204 无内容
      if (response.status === 204) {
        return null;
      }

      // 解析 JSON 响应
      const data = await response.json();
      
      // 检查后端返回的业务错误
      if (data.code && data.code !== 0) {
        throw new Error(data.message || `请求失败 (code: ${data.code})`);
      }

      return data.data !== undefined ? data.data : data;
    } catch (error) {
      // 网络错误
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('网络连接失败，请检查后端服务是否运行');
      }
      throw error;
    }
  }

  // ==================== 认证相关 API ====================

  /**
   * 获取当前用户信息（验证 Token）
   */
  async getMe() {
    return this.request('GET', '/api/auth/me');
  }

  // ==================== 任务相关 API ====================

  /**
   * 获取任务列表
   * @param {object} params - 查询参数
   * @param {number} params.page - 页码
   * @param {number} params.pageSize - 每页数量
   * @param {string} params.status - 状态过滤
   */
  async getTasks(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.page) queryParams.set('page', params.page);
    if (params.pageSize) queryParams.set('pageSize', params.pageSize);
    if (params.status) queryParams.set('status', params.status);
    
    const query = queryParams.toString();
    return this.request('GET', `/api/tasks${query ? '?' + query : ''}`);
  }

  /**
   * 创建新任务
   * @param {object} payload - 任务数据
   */
  async createTask(payload) {
    return this.request('POST', '/api/tasks', payload);
  }

  /**
   * 启动任务
   * @param {string} taskId - 任务 ID
   */
  async startTask(taskId) {
    return this.request('POST', `/api/tasks/${taskId}/start`);
  }

  /**
   * 取消任务
   * @param {string} taskId - 任务 ID
   */
  async cancelTask(taskId) {
    return this.request('POST', `/api/tasks/${taskId}/cancel`);
  }

  /**
   * 重试任务
   * @param {string} taskId - 任务 ID
   */
  async retryTask(taskId) {
    return this.request('POST', `/api/tasks/${taskId}/retry`);
  }

  /**
   * 删除任务
   * @param {string} taskId - 任务 ID
   */
  async deleteTask(taskId) {
    return this.request('DELETE', `/api/tasks/${taskId}`);
  }

  /**
   * 获取任务详情
   * @param {string} taskId - 任务 ID
   */
  async getTask(taskId) {
    return this.request('GET', `/api/tasks/${taskId}`);
  }

  // ==================== 文件相关 API ====================

  /**
   * 获取文件列表
   * @param {string} path - 目录路径
   */
  async getFiles(path = '') {
    const query = path ? `?path=${encodeURIComponent(path)}` : '';
    return this.request('GET', `/api/files${query}`);
  }

  /**
   * 获取文件详情
   * @param {string} filePath - 文件路径
   */
  async getFileInfo(filePath) {
    return this.request('GET', `/api/files/info?path=${encodeURIComponent(filePath)}`);
  }

  // ==================== 频道相关 API ====================

  /**
   * 获取频道列表
   */
  async getChats() {
    return this.request('GET', '/api/chats');
  }

  /**
   * 估算消息数量
   * @param {string} chatId - 频道 ID
   * @param {object} payload - 估算参数
   */
  async estimateMessages(chatId, payload) {
    return this.request('POST', `/api/chats/${chatId}/messages/estimate`, payload);
  }

  // ==================== 配置相关 API ====================

  /**
   * 获取配置
   */
  async getConfig() {
    return this.request('GET', '/api/config');
  }

  /**
   * 更新配置
   * @param {object} config - 配置数据
   */
  async updateConfig(config) {
    return this.request('PUT', '/api/config', config);
  }

  // ==================== 资源状态 API ====================

  /**
   * 获取资源状态
   */
  async getResourceStatus() {
    return this.request('GET', '/api/resource/status');
  }
}

// 创建单例实例
const api = new ApiClient();

// 导出供 Alpine.js 使用
window.api = api;
