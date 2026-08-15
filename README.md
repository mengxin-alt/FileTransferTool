# 📂 FileTransferTool 局域网文件传输工具

> 基于 Flask + Tkinter 的双进程桌面文件传输服务，让电脑与手机/其他设备之间通过浏览器轻松互传文件。
>
> **版本**：v1.0.1 ｜ **联系**：3438978674@qq.com

---

## 📖 目录

- [一、项目简介](#一项目简介)
- [二、功能特性](#二功能特性)
- [三、技术栈](#三技术栈)
- [四、架构设计](#四架构设计)
- [五、快速开始](#五快速开始)
- [六、项目结构](#六项目结构)
- [七、核心模块说明](#七核心模块说明)
- [八、API 接口文档](#八api-接口文档)
- [九、配置说明](#九配置说明)
- [十、日志系统](#十日志系统)
- [十一、打包发布](#十一打包发布)
- [十二、常见问题](#十二常见问题)
- [十三、已知限制与安全提示](#十三已知限制与安全提示)

---

## 一、项目简介

`FileTransferTool` 是一个面向办公场景、家庭场景的**免配置局域网文件中转站**，用于替代 U 盘跨设备传文件。它由两部分组成：

1. **桌面 GUI 控制面板**（Tkinter）：用户可视化地启动/停止服务、查看二维码、配置参数、查看日志。
2. **Flask Web 服务器**：手机或其他电脑通过浏览器访问即可上传/下载/删除文件。

两者通过 `subprocess` 子进程方式解耦：GUI 不阻塞，Flask 崩溃可独立重启，可打包为单文件 exe 分发。

---

## 二、功能特性

### 🖥️ 桌面控制面板
- ✅ 一键启停服务（端口可视化输入）
- ✅ 启动后自动生成**访问二维码**（qrcode + Pillow），手机扫码直达
- ✅ 显示本机所有 IP + 复制访问地址到剪贴板
- ✅ 5 套主题配色（default / dark / vibrant / minimal / pastel）
- ✅ 实时日志查看器：操作日志 + 访问日志双通道切换、级别过滤、时间范围过滤、关键词搜索高亮、自动刷新、一键导出
- ✅ 完整配置管理：端口、上传目录、文件大小限制、调试模式
- ✅ 「帮助 → 关于」打开服务器监控仪表盘（含服务运行状态前置检查）

### 🌐 Web 传输页
- ✅ 拖拽 / 点击双通道上传
- ✅ XHR 流式进度条（百分比实时显示）
- ✅ 文件列表 + 文件名搜索（300ms 防抖）
- ✅ 图片模态预览
- ✅ 下载 / 删除操作
- ✅ UUID 前缀防重名

### 📊 服务器监控仪表盘
- ✅ CPU / 内存 / 磁盘使用率实时展示
- ✅ 文件总数统计
- ✅ 网络接口列表
- ✅ 每 5 秒自动刷新

### 🛡️ 可靠性设计
- ✅ **4 层防御式进程回收**：递归 terminate → wait → kill → 端口级全局扫描
- ✅ 多编码降级读取日志（UTF-8 → GBK → Latin-1）
- ✅ IP 获取三路兜底（psutil → socket → UDP connect）
- ✅ 特权端口管理员权限前置提醒
- ✅ dashboard 入口防御性检查（服务未启动时提示并引导，IP 为空时用 127.0.0.1 兜底）

---

## 三、技术栈

| 层级 | 技术 / 库 | 用途 |
|------|----------|------|
| GUI 桌面端 | Tkinter + ttk | 控制面板、配置、日志查看 |
| Web 框架 | Flask >= 2.3 | HTTP 服务 |
| 跨域 | Flask-CORS >= 4.0 | 允许跨设备访问 |
| 系统监控 | psutil >= 6.0 | CPU/内存/磁盘/进程管理 |
| 二维码 | qrcode >= 7.4 + Pillow >= 10.0 | 生成访问二维码 |
| 日志 | logging + RotatingFileHandler | 双日志轮转 |
| 进程管理 | subprocess + psutil | 双进程解耦 |
| 前端 | HTML + CSS 变量 + 原生 JS | 传输页 + 仪表盘 |
| 模板 | Jinja2 | 主题动态注入 |
| 打包 | PyInstaller | 单文件 exe 分发 |

依赖清单见 [requirements.txt](file:///e:/DeskTop/modify_ai/FileTransferTool/requirements.txt)。

---

## 四、架构设计

### 双模式运行架构

```
┌─────────────────────────────────────────────────────────────┐
│  python app.py                    python app.py --run-server│
│  ┌────────────────────────┐       ┌──────────────────────┐ │
│  │   GUI 主进程 (Tkinter) │       │  Flask 服务进程      │ │
│  │  ┌──────────────────┐  │       │                      │ │
│  │  │ 控制面板 / 配置  │  │       │  /upload /download   │ │
│  │  │ 日志 / 主题      │  │  ───> │  /files /delete      │ │
│  │  └──────────────────┘  │ Popen │  /status /dashboard  │ │
│  │  │ subprocess.Popen │─────────>│                      │ │
│  │  └──────────────────┘  │       │  host=0.0.0.0        │ │
│  │  │ psutil 进程回收   │  │       │  port=config['port'] │ │
│  │  └──────────────────┘  │       │                      │ │
│  └────────────────────────┘       └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 设计要点

1. **条件导入**：Flask 仅在 `--run-server` 模式下导入，GUI 模式启动更轻量。
2. **进程解耦**：GUI 崩溃不影响 Flask 服务；Flask 崩溃 GUI 可感知并重启。
3. **非侵入式日志埋点**：利用 Flask `before_request` / `after_request` 钩子。
4. **延迟绑定资源路径**：通过 `sys.frozen` 和 `sys._MEIPASS` 适配开发 / 打包两种环境。

---

## 五、快速开始

### 环境要求
- Python 3.8+
- Windows / macOS / Linux

### 安装与运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 GUI 控制面板（默认）
python app.py

# 3. 或直接以服务器模式运行（无 GUI）
python app.py --run-server
```

> ⚠️ **注意**：直接运行脚本即可（`python app.py`），**不要**使用 `python -m .\app` 这类带相对路径的 `-m` 写法，Python 会报 `Relative module names not supported`。

### 使用流程

1. 运行 `python app.py` 启动控制面板
2. 在「配置」标签页设置端口（默认 8000）和上传目录
3. 点击「启动服务」
4. 手机扫描二维码或浏览器访问显示的地址
5. 在 Web 页面上传 / 下载 / 删除文件
6. 需要查看监控：点「帮助 → 关于」打开 dashboard（需服务已启动）

---

## 六、项目结构

```
FileTransferTool/
├── app.py              # 主程序（GUI + Flask，~1700 行）
├── config.json         # 运行配置
├── requirements.txt    # 依赖清单
├── appicon.ico         # 应用图标
├── README.md           # 本文档
├── templates/          # Jinja2 模板
│   ├── index.html      # 文件传输主页
│   └── dashboard.html  # 服务器监控仪表盘
├── static/
│   └── css/
│       └── style.css   # 公共样式
├── logs/               # 运行日志（自动生成）
│   ├── file_transfer.log     # 操作日志
│   └── access.log            # 访问日志
└── output/             # 输出目录
```

---

## 七、核心模块说明

### 7.1 主入口 ([app.py:1689-1716](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L1689-L1716))

通过 `argparse` 区分两种运行模式：

| 命令 | 模式 | 行为 |
|------|------|------|
| `python app.py` | GUI 模式 | 启动 Tkinter 控制面板 |
| `python app.py --run-server` | 服务器模式 | 启动 Flask 监听 `0.0.0.0:port` |

### 7.2 Flask 路由层 ([app.py:147-488](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L147-L488))

包含文件 CRUD、配置管理、服务器状态、进程启停等接口。

### 7.3 桌面控制面板 `ServerGUI` ([app.py:490-1687](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L490-L1687))

三个标签页：
- **服务控制**：端口输入、启停按钮、状态显示、二维码、访问地址
- **配置**：端口 / 上传目录 / 文件大小 / 调试模式 + 5 套主题
- **日志**：操作日志 + 访问日志切换、过滤、搜索、导出

### 7.4 dashboard 入口 ([app.py:1100-1123](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L1100-L1123))

「帮助 → 关于」通过 `webbrowser.open` 打开 `/dashboard` 路由。该方法包含完整防御逻辑：

- **服务状态前置检查**：未启动服务时弹出提示并自动切换到「服务控制」标签页
- **IP 兜底**：`get_all_local_ips()` 返回空时用 `127.0.0.1` 兜底，避免变量未定义崩溃
- **异常捕获**：端口非法、浏览器打开失败等均给出友好提示并写日志

### 7.5 进程回收机制 ([app.py:1481-1663](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L1481-L1663))

停止服务的 4 层防御：

1. `psutil.Process(pid)` 存在性检查
2. 递归 `children(recursive=True).terminate()` + `wait_procs` + 强制 `kill`
3. 主进程 `terminate` + 超时 `kill`
4. 扫描所有监听该端口的进程并全局 `kill`（解决 Werkzeug reloader worker 泄漏）

### 7.6 二维码生成 ([app.py:1339-1366](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L1339-L1366))

使用 `qrcode.QRCode` 生成访问 URL 二维码，`box_size=5, border=1`，resize 到 120×120 后通过 `ImageTk.PhotoImage` 显示。

### 7.7 多策略 IP 获取 ([app.py:1368-1420](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L1368-L1420))

| 优先级 | 方法 | 优点 | 缺点 |
|--------|------|------|------|
| 1 | `psutil.net_if_addrs()` | 全面、列出所有网卡 | 需要权限 |
| 2 | `socket.getaddrinfo(hostname)` | 跨平台 | 可能返回 127.0.0.1 |
| 3 | UDP `connect(('8.8.8.8', 80))` | 拿到实际出口网卡 IP | 断网时失败 |

---

## 八、API 接口文档

| 路由 | 方法 | 功能 | 请求参数 / Body |
|------|------|------|----------------|
| `/` | GET | 文件传输主页 | - |
| `/dashboard` | GET | 服务器监控仪表盘 | - |
| `/files` | GET | 获取文件列表 | `?query=<关键词>`（可选，模糊搜索） |
| `/upload` | POST | 上传文件 | `multipart/form-data`，字段名 `file` |
| `/download/<filename>` | GET | 下载文件 | URL 路径参数 `filename` |
| `/delete/<filename>` | DELETE | 删除文件 | URL 路径参数 `filename` |
| `/status` | GET | 服务器系统状态 | - |
| `/api/config` | GET | 获取当前配置 | - |
| `/api/config` | POST | 保存配置 | JSON Body |
| `/api/server/start` | POST | 启动服务 | - |
| `/api/server/stop` | POST | 停止服务 | - |

### `/status` 响应示例

```json
{
  "cpu": { "percent": 23.5, "count": 8 },
  "memory": { "total": 17179869184, "used": 8589934592, "free": 8589934592, "percent": 50.0 },
  "disk": { "total": 512000000000, "used": 256000000000, "free": 256000000000, "percent": 50.0 },
  "storage": { "total_files": 42, "total_size": 1073741824 },
  "network": [
    { "name": "以太网", "ip": "192.168.1.100", "netmask": "255.255.255.0" }
  ]
}
```

---

## 九、配置说明

配置文件 [config.json](file:///e:/DeskTop/modify_ai/FileTransferTool/config.json)：

```json
{
  "port": 8000,
  "upload_folder": "D:/AAAstation",
  "max_content_length": 1000,
  "debug": false,
  "colors": {
    "primary": "#3498db",
    "secondary": "#95a5a6",
    "background": "#f5f7fa",
    "text": "#333",
    "card": "white"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `port` | int | 服务监听端口（1-65535） |
| `upload_folder` | string | 文件上传存储目录 |
| `max_content_length` | int | 单文件最大大小（MB） |
| `debug` | bool | Flask 调试模式 |
| `colors` | object | 主题配色（5 套预设可选） |

### 主题预设

| 主题名 | primary | background | 适用场景 |
|--------|---------|------------|----------|
| default | `#3498db` | `#f5f7fa` | 通用 |
| dark | `#2c3e50` | `#1a2530` | 夜间 |
| vibrant | `#e74c3c` | `#fef9e7` | 活力 |
| minimal | `#7f8c8d` | `#ecf0f1` | 极简 |
| pastel | `#b39ddb` | `#f3e5f5` | 柔和 |

---

## 十、日志系统

### 日志文件（位于 `logs/` 目录）

| 文件 | 记录内容 | 格式 |
|------|---------|------|
| `file_transfer.log` | 操作日志（启停、上传、下载、删除） | `时间 - 级别 - 消息` |
| `access.log` | 访问日志（每个 HTTP 请求） | `时间 - IP - 方法 - URL - 状态码 - 响应大小 - 响应时间ms` |

### 日志特性

- **轮转策略**：`RotatingFileHandler`，单文件 10MB，保留 5 个备份
- **编码兼容**：读取时自动尝试 UTF-8 → GBK → Latin-1
- **GUI 查看**：支持日志类型切换、级别过滤（INFO/WARNING/ERROR）、时间范围过滤、关键词搜索高亮、2 秒自动刷新、一键导出

---

## 十一、打包发布

### 使用 PyInstaller 打包为单文件 exe

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包（包含图标、模板、静态资源）
pyinstaller --onefile --windowed --name FileTransferTool ^
            --icon appicon.ico ^
            --add-data "templates;templates" ^
            --add-data "static;static" ^
            --add-data "config.json;." ^
            app.py
```

### 打包注意事项

- 代码已通过 `sys.frozen` 和 `sys._MEIPASS` 适配打包后的资源路径（见 [app.py:6-12](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L6-L12)）
- `sys.executable` 在打包后会指向 exe 本身，因此 `subprocess.Popen` 能正确拉起子进程
- `config.json` 需要打包到 exe 同级目录（运行时可写）

---

## 十二、常见问题

### Q1：启动服务后手机打不开页面？

排查清单：
1. ✅ 电脑和手机是否连接同一 Wi-Fi / 局由器
2. ✅ 电脑防火墙是否放行端口（Windows Defender 防火墙入站规则）
3. ✅ 服务是否绑定 `0.0.0.0` 而非 `127.0.0.1`（本项目默认 0.0.0.0）
4. ✅ 端口是否被其他程序占用
5. ✅ Wi-Fi 是否开启了 AP 隔离（路由器设置）
6. ✅ 手机是否开启了 VPN / 代理

### Q2：停止服务后端口仍被占用？

这是 Werkzeug reloader 的已知问题。本项目已通过「端口级全局扫描 kill」机制解决（见 [stop_server](file:///e:/DeskTop/modify_ai/FileTransferTool/app.py#L1571-L1581)）。若仍异常，可手动执行：

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Q3：上传大文件失败？

检查 `config.json` 中的 `max_content_length`（单位 MB），默认 1000MB。Flask 会在请求体超过该值时返回 413 错误。

### Q4：日志显示乱码？

GUI 日志查看器已内置 UTF-8 / GBK / Latin-1 三编码降级读取。若仍乱码，可能是日志文件被其他程序修改了编码，可用支持多编码的文本编辑器（如 VSCode）手动切换编码查看。

### Q5：多网卡环境下二维码扫不出来？

当前二维码仅生成第一个 IP。如果电脑同时连了有线和 Wi-Fi，但手机连的是 Wi-Fi，可能扫到的是有线 IP。临时解决：在「访问地址」区域手动复制正确的 IP。改进方向：二维码改为中转 HTML 页，列出所有 IP 供用户选择。

### Q6：点「帮助 → 关于」打不开 dashboard？

dashboard 由 Flask 的 `/dashboard` 路由提供，**必须先启动服务**。当前版本已加入前置检查：若服务未启动，会弹出提示并自动切换到「服务控制」标签页引导你启动。请先点「启动服务」，再点「帮助 → 关于」。

### Q7：运行报 `Relative module names not supported`？

使用了错误的 `-m` 写法（如 `python -m .\app`）。正确方式是直接运行脚本：`python app.py`，或用合法模块名：`python -m app`（不带路径前缀和 `.py` 后缀）。

---

## 十三、已知限制与安全提示

### ⚠️ 安全限制

本项目设计目标是**局域网内部使用**，存在以下安全限制，**不建议暴露到公网**：

1. **无身份认证**：所有路由（上传 / 下载 / 删除 / 配置修改）均无鉴权
2. **无 CSRF 保护**：DELETE / POST 接口可被跨站请求伪造
3. **上传文件类型未校验**：可上传任意类型文件（exe / php 等）
4. **路径安全**：虽然 `send_from_directory` 会做基本校验，但仍建议在生产环境加额外过滤
5. **配置接口公开**：`/api/config` 可被任意访问者读取和修改

### 改进建议

- 增加 Session / Token 认证中间件
- 上传文件 MIME 类型白名单
- 关键操作增加 CSRF Token
- `/api/config` 等管理接口增加独立密码保护
- 部署到公网时增加 HTTPS + 反向代理

### 其他限制

- `/status` 接口中 `psutil.disk_usage('/')` 在 Windows 下可能不指向期望盘符
- `/files` 接口每次全量扫描目录，文件数超过 10 万时可能卡顿
- 当前不支持断点续传 / 分片上传

---

## 📄 License

本项目仅供学习交流使用。

## 📬 联系方式

- 邮箱：3438978674@qq.com
- 版本：v1.0.1

---

> 📝 最后更新：2026-08-15
