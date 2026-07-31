/**
 * 认证逻辑模块
 * 
 * 处理用户认证状态管理、Token 验证、登录跳转等
 */

class AuthManager {
  constructor() {
    this.isAuthenticated = false;
    this.user = null;
    this.loading = false;
    this.error = null;
  }

  /**
   * 验证 Token 并获取用户信息
   * @returns {Promise<boolean>} 是否认证成功
   */
  async verifyToken() {
    this.loading = true;
    this.error = null;

    try {
      const user = await api.getMe();
      this.isAuthenticated = true;
      this.user = user;
      return true;
    } catch (error) {
      this.isAuthenticated = false;
      this.user = null;
      this.error = error.message;
      
      // 如果 Token 无效，跳转到登录页
      if (error.message.includes('401') || error.message.includes('认证')) {
        api.clearToken();
        const currentPath = window.location.pathname;
        if (currentPath !== '/web/login.html') {
          window.location.href = `/web/login.html?redirect=${encodeURIComponent(currentPath)}`;
        }
      }
      
      return false;
    } finally {
      this.loading = false;
    }
  }

  /**
   * 登录处理
   * @param {string} token - 用户输入的 Token
   * @param {string} redirectUrl - 登录成功后跳转的 URL
   * @returns {Promise<boolean>} 是否登录成功
   */
  async login(token, redirectUrl = '/web/index.html') {
    this.loading = true;
    this.error = null;

    try {
      // 设置 Token
      api.setToken(token, true);

      // 验证 Token
      const user = await api.getMe();
      this.isAuthenticated = true;
      this.user = user;

      // 跳转到目标页面
      window.location.href = redirectUrl;
      return true;
    } catch (error) {
      this.isAuthenticated = false;
      this.user = null;
      this.error = error.message;
      api.clearToken();
      return false;
    } finally {
      this.loading = false;
    }
  }

  /**
   * 登出处理
   */
  logout() {
    api.clearToken();
    this.isAuthenticated = false;
    this.user = null;
    window.location.href = '/web/login.html';
  }

  /**
   * 检查认证状态
   * 页面加载时调用，确保已认证
   */
  async ensureAuthenticated() {
    if (!api.token) {
      window.location.href = '/web/login.html?redirect=' + encodeURIComponent(window.location.pathname);
      return false;
    }

    return await this.verifyToken();
  }

  /**
   * 获取用户显示名称
   */
  getDisplayName() {
    if (!this.user) return '未知用户';
    return this.user.name || this.user.username || '用户';
  }

  /**
   * 获取 Token 过期时间
   */
  getTokenExpiry() {
    if (!this.user || !this.user.expires_at) return null;
    return new Date(this.user.expires_at);
  }

  /**
   * 检查 Token 是否即将过期（少于 5 分钟）
   */
  isTokenExpiringSoon() {
    const expiry = this.getTokenExpiry();
    if (!expiry) return false;
    
    const now = new Date();
    const diffMinutes = (expiry - now) / (1000 * 60);
    return diffMinutes < 5;
  }
}

// 创建单例实例
const authManager = new AuthManager();

// 导出供 Alpine.js 使用
window.authManager = authManager;

// 页面加载完成后自动验证认证状态
document.addEventListener('DOMContentLoaded', async () => {
  // 仅在需要认证的页面执行
  const publicPages = ['/login.html', '/web/login.html', '/error.html', '/web/error.html'];
  const currentPath = window.location.pathname;
  
  if (!publicPages.includes(currentPath) && !currentPath.startsWith('/error')) {
    await authManager.ensureAuthenticated();
  }
});
