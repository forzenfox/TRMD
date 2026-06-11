<p align="center">
  <img width="15%" align="center" src="https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/logo.png" alt="logo">
</p>
<h1 align="center">Telegram_Restricted_Media_Downloader</h1>
<p align="center">
  A telegram downloader on windows and linux platform based on Python.
</p>
<p align="center">
  <a style="text-decoration:none">
    <img src="https://img.shields.io/badge/Python-3.13.2-blue.svg?color=00B16A" alt="Python 3.13.2"/>
  </a>
  <a style="text-decoration:none">
    <img src="https://img.shields.io/badge/pyrogram@kurigram-2.2.19-blue.svg?color=00B16A" alt="pyrogram@kurigram 2.2.19"/>
  </a>
  <a style="text-decoration:none">
    <img src="https://img.shields.io/badge/Platform-Windows & Linux%20-blue?color=00B16A" alt="Platform Windows & Linux"/>
  </a>
</p>

---

**本项目是 [Gentlesprite/Telegram_Restricted_Media_Downloader](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader) 的 fork。**  
详细文档、使用方法、常见问题等请参考原项目。

---

# 免责声明

本项目以 `MIT` 协议开源发布，仅限于合法、合规的用途。严禁使用本软件从事任何违反法律法规、侵犯他人合法权益或干扰平台正常运营的行为。

**所有使用本软件的行为及其后果均由使用者自行承担全部法律责任**，开发者不对任何使用行为及其后果负责。

---

# 快速开始

## 1. 申请 Telegram API

1. 前往 [https://my.telegram.org/auth](https://my.telegram.org/auth)
2. 填写绑定的手机号并登录
3. 点击 `API development tools` 创建应用
4. 保存得到的 `api_hash` 和 `api_id`

## 2. 运行方式

### 方式一：Python 运行（推荐 Python 3.13.2）

```shell
git clone https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader.git
cd Telegram_Restricted_Media_Downloader
pip install -r requirements.txt
python main.py
```

### 方式二：Docker 运行

```bash
git clone https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader.git
cd Telegram_Restricted_Media_Downloader
docker-compose run --rm trmd    # 首次运行配置
docker-compose up -d            # 后续启动
```

### 方式三：使用预编译二进制文件

从 [Releases](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases) 下载对应平台的二进制文件直接运行。

## 3. 配置文件

软件首次运行时会自动在目录下生成 `config.yaml`，按提示填入 `api_id`、`api_hash` 等参数即可。详细配置说明请查看原项目文档。

---

# 相关链接

| 说明 | 链接 |
|:---:|:----:|
| 原项目 | [Gentlesprite/Telegram_Restricted_Media_Downloader](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader) |
| 发布页 | [Releases](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases) |
| Telegram 交流群 | [点击加入](https://t.me/+6KKA-buFaixmNTE1) |

---

*本项目按"原样"提供，不附带任何明示或暗示的保证。*