/**
 * 文件管理逻辑模块
 * 
 * 处理文件浏览、选择、上传准备等功能
 */

class FileManager {
  constructor() {
    this.currentPath = '/';
    this.files = [];
    this.selectedFiles = [];
    this.loading = false;
    this.error = null;
    this.showUploadModal = false;
    this.mediaGroupSize = 10; // Telegram 媒体组上限
    this.viewMode = 'list'; // list, grid
    this.sortBy = 'name'; // name, size, date
    this.sortOrder = 'asc'; // asc, desc
  }

  /**
   * 加载文件列表
   * @param {string} path - 目录路径
   */
  async loadFiles(path = null) {
    if (path !== null) {
      this.currentPath = path;
    }

    this.loading = true;
    this.error = null;

    try {
      const response = await api.getFiles(this.currentPath);
      this.files = response.files || [];
      this._sortFiles();
    } catch (error) {
      this.error = error.message;
      console.error('加载文件列表失败:', error);
    } finally {
      this.loading = false;
    }
  }

  /**
   * 进入子目录
   * @param {string} dirName - 目录名
   */
  enterDirectory(dirName) {
    const newPath = this.currentPath === '/' 
      ? `/${dirName}` 
      : `${this.currentPath}/${dirName}`;
    this.loadFiles(newPath);
  }

  /**
   * 返回父目录
   */
  goToParentDirectory() {
    if (this.currentPath === '/') return;
    
    const parts = this.currentPath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = '/' + parts.join('/');
    this.loadFiles(parentPath || '/');
  }

  /**
   * 切换文件选择状态
   * @param {object} file - 文件对象
   */
  toggleFileSelection(file) {
    if (file.is_directory) return; // 目录不可选

    const index = this.selectedFiles.findIndex(f => f.path === file.path);
    if (index === -1) {
      this.selectedFiles.push(file);
    } else {
      this.selectedFiles.splice(index, 1);
    }
  }

  /**
   * 全选当前目录下的所有文件
   */
  selectAllFiles() {
    this.selectedFiles = this.files
      .filter(f => !f.is_directory)
      .map(f => ({ ...f }));
  }

  /**
   * 清空选择
   */
  clearSelection() {
    this.selectedFiles = [];
  }

  /**
   * 获取已选文件总大小
   */
  getTotalSelectedSize() {
    return this.selectedFiles.reduce((total, file) => total + (file.size || 0), 0);
  }

  /**
   * 打开上传配置弹窗
   */
  openUploadModal() {
    if (this.selectedFiles.length === 0) {
      this._notify('warning', '请先选择要上传的文件');
      return;
    }
    this.showUploadModal = true;
  }

  /**
   * 关闭上传配置弹窗
   */
  closeUploadModal() {
    this.showUploadModal = false;
  }

  /**
   * 创建上传任务
   * @param {string} targetChat - 目标频道
   * @param {boolean} sendAsMediaGroup - 是否发送为媒体组
   * @param {boolean} deleteAfterUpload - 上传后是否删除本地文件
   */
  async createUploadTask(targetChat, sendAsMediaGroup, deleteAfterUpload) {
    if (!targetChat) {
      this._notify('error', '请输入目标频道');
      return;
    }

    try {
      // 如果启用媒体组，按组拆分文件
      const fileGroups = sendAsMediaGroup 
        ? this._splitIntoMediaGroups(this.selectedFiles)
        : [this.selectedFiles];

      // 为每个组创建上传任务
      for (const fileGroup of fileGroups) {
        const payload = {
          type: 'upload',
          name: `上传_${new Date().toLocaleString('zh-CN').replace(/[/:]/g, '')}`,
          target_chat: targetChat,
          files: fileGroup.map(f => f.path),
          send_as_media_group: sendAsMediaGroup && fileGroup.length > 1,
          delete_after_upload: deleteAfterUpload,
        };

        await api.createTask(payload);
      }

      this.closeUploadModal();
      this.clearSelection();
      this._notify('success', `已创建 ${fileGroups.length} 个上传任务`);
    } catch (error) {
      this._notify('error', `创建上传任务失败: ${error.message}`);
      throw error;
    }
  }

  /**
   * 将文件列表拆分为媒体组
   * @param {Array} files - 文件列表
   * @returns {Array<Array>} 分组后的文件列表
   */
  _splitIntoMediaGroups(files) {
    const groups = [];
    for (let i = 0; i < files.length; i += this.mediaGroupSize) {
      groups.push(files.slice(i, i + this.mediaGroupSize));
    }
    return groups;
  }

  /**
   * 排序文件列表
   */
  _sortFiles() {
    this.files.sort((a, b) => {
      // 目录始终排在文件前面
      if (a.is_directory !== b.is_directory) {
        return a.is_directory ? -1 : 1;
      }

      let comparison = 0;
      switch (this.sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'size':
          comparison = (a.size || 0) - (b.size || 0);
          break;
        case 'date':
          comparison = new Date(a.modified_at || 0) - new Date(b.modified_at || 0);
          break;
      }

      return this.sortOrder === 'asc' ? comparison : -comparison;
    });
  }

  /**
   * 切换排序
   * @param {string} sortBy - 排序字段
   */
  toggleSort(sortBy) {
    if (this.sortBy === sortBy) {
      this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortBy = sortBy;
      this.sortOrder = 'asc';
    }
    this._sortFiles();
  }

  /**
   * 获取文件图标
   * @param {object} file - 文件对象
   */
  getFileIcon(file) {
    if (file.is_directory) {
      return '📁';
    }

    const ext = file.name.split('.').pop().toLowerCase();
    const iconMap = {
      // 视频
      mp4: '🎬', mkv: '🎬', avi: '🎬', mov: '🎬', webm: '🎬',
      // 图片
      jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', webp: '🖼️', bmp: '🖼️',
      // 音频
      mp3: '🎵', wav: '🎵', flac: '🎵', aac: '🎵', ogg: '🎵',
      // 文档
      pdf: '📄', doc: '📄', docx: '📄', txt: '📄', md: '📄',
      // 压缩文件
      zip: '📦', rar: '📦', '7z': '📦', tar: '📦', gz: '📦',
    };

    return iconMap[ext] || '📄';
  }

  /**
   * 判断文件是否为媒体文件
   * @param {object} file - 文件对象
   */
  isMediaFile(file) {
    if (file.is_directory) return false;
    
    const ext = file.name.split('.').pop().toLowerCase();
    const mediaExts = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'mp3', 'wav', 'flac', 'aac', 'ogg'];
    return mediaExts.includes(ext);
  }

  /**
   * 获取文件类型的 CSS 类
   * @param {string} ext - 文件扩展名
   */
  getFileTypeClass(ext) {
    const classMap = {
      mp4: 'text-blue-400',
      mkv: 'text-blue-400',
      jpg: 'text-green-400',
      png: 'text-green-400',
      mp3: 'text-purple-400',
      pdf: 'text-red-400',
      zip: 'text-yellow-400',
    };
    return classMap[ext] || 'text-gray-400';
  }

  /**
   * 获取面包屑路径数组
   */
  getBreadcrumbs() {
    if (this.currentPath === '/') {
      return [{ name: '根目录', path: '/' }];
    }

    const parts = this.currentPath.split('/').filter(Boolean);
    const breadcrumbs = [{ name: '根目录', path: '/' }];
    
    let currentPath = '';
    for (const part of parts) {
      currentPath += `/${part}`;
      breadcrumbs.push({
        name: part,
        path: currentPath,
      });
    }

    return breadcrumbs;
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
   * 格式化时间
   * @param {string} isoString - ISO 时间字符串
   */
  formatTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  /**
   * 显示通知
   * @param {string} type - 通知类型
   * @param {string} message - 通知内容
   */
  _notify(type, message) {
    if (window.showNotification) {
      window.showNotification(type, message);
    } else {
      console.log(`[${type}] ${message}`);
    }
  }

  /**
   * 刷新文件列表
   */
  refresh() {
    this.loadFiles(this.currentPath);
  }
}

// 创建单例实例
const fileManager = new FileManager();

// 导出供 Alpine.js 使用
window.fileManager = fileManager;
