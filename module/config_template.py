# coding=UTF-8
"""配置模板。

从 module/__init__.py 提取的 README 配置模板。
"""

README = r"""
```yaml
api_hash: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # 申请的api_hash。
api_id: 'xxxxxxxx' # 申请的api_id。
# bot_token（选填）如果不填，就不能使用机器人功能。可前往https://t.me/BotFather免费申请。
bot_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
download_type: # 需要下载的类型。支持的参数:video,photo,document,audio,voice,animation。
- video # 视频。
- photo # 图片。
- document # 文档。
- audio # 音频。
- voice # 语音。
- animation # GIF。
- video_note # 视频笔记。
is_shutdown: true # 下载完成后是否自动关机。支持的参数：true,false。
links: D:\path\where\your\link\files\save\content.txt # 链接地址写法如下:
# 新建txt文本，一个链接为一行，将路径填入即可请不要加引号，在软件运行前就准备好。
# D:\path\where\your\link\txt\save\content.txt 一个链接一行。
max_retries:
  download: 5 # 最大的下载任务的重试次数。
  upload: 3 # 最大的上传任务的重试次数。
max_tasks:
  download: 5 # 最大同时下载的任务数。
  upload: 3 # 最大同时上传的任务数。
proxy: # 代理部分，如不使用请全部填null注意冒号后面有空格，否则不生效导致报错。
  enable_proxy: true # 是否开启代理。支持的参数：true,false。
  hostname: 127.0.0.1 # 代理的ip地址。
  scheme: socks5 # 代理的类型。支持的参数：http,socks4,socks5。
  port: 10808 # 代理ip的端口。支持的参数：0~65535。
  username: null # 代理的账号，没有就填null。
  password: null # 代理的密码，没有就填null。
save_directory: F:\directory\media\where\you\save # 下载的媒体保存的目录（支持通配符）。
session_directory: F:\directory\session\where\you\save # 会话的保存目录（支持通配符）。
temp_directory: F:\directory\temp\where\you\save # 缓存保存的目录（支持通配符）。
```
"""
