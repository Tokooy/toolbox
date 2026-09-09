# Toolbox — 多功能工具台

> English version: [README.md](README.md)

**Toolbox** 是一个**多功能工具集合**：把多个独立的小工具整合进**一个本地网页应用**。
每个工具保持原始代码不动，由统一的 `hub` 整合层把它们汇入同一个单页面板——
点哪个功能按钮就运行哪个功能，不跳转页面，任务互斥（同一时刻只运行一个）。

本项目**跨平台**：Linux / macOS 可直接用 Python 运行；**Windows 支持一键打包成单文件
`Toolbox.exe`**，双击即用、无需安装 Python（自带运行环境）。

## 已包含的工具

| 工具 | 说明 | 独立仓库 |
| --- | --- | --- |
| 📈 美债收益率 | 美国 2 / 10 / 30 年期国债收益率走势（FRED 圣路易斯联储权威数据），支持增量更新、自动代理 | [Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields) |
| ▦ 二维码批量生成 | 读取 Excel「二维码编号」列批量生成二维码，输出 HTML / Excel | [Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work) |

> 随时可以添加新工具——每个工具放在自己的子目录里，并在 `hub/features.json` 中注册即可
> （详见 [hub/README_zh.md](hub/README_zh.md)）。

## 🪟 Windows 快速开始

### 方式 A：使用打包好的 Toolbox.exe（推荐，无需安装 Python）

1. 将 **`Toolbox.exe`**（见 Release 或按下方「构建 exe」自行打包）放到任意目录；
2. **双击运行**，控制台窗口显示启动信息后，浏览器自动打开 <http://127.0.0.1:8080>；
3. 停止服务：在 exe 的控制台窗口按 **Ctrl+C**。

exe 会**自动管理数据目录**（建在 exe 同目录下）：

```
Toolbox.exe 所在目录/
├── QRcode/
│   ├── input/    ← 把待生成的 Excel 放这里（或在网页里直接上传）
│   ├── output/   ← 生成的 HTML / Excel
│   └── qrcodes/  ← 二维码图片缓存
└── us-treasury-yields/
    └── data/     ← 美债数据本地缓存（首次联网获取后离线可用）
```

> 💡 若把 `Toolbox.exe` 放到**本仓库根目录旁**（旁边已有 `QRcode/`、
> `us-treasury-yields/` 文件夹），exe 会直接复用仓库内的数据目录，与源码数据互通。

### 方式 B：源码运行（开发模式）

```bat
:: 1) 安装依赖（只需一次）
python -m pip install "qrcode[pil]" pillow openpyxl

:: 2) 启动（需保持该窗口开启）
cd hub
python server.py
```

浏览器自动打开 <http://127.0.0.1:8080>。依赖说明：美债看板为纯标准库实现，
无需任何第三方包；二维码生成需要 `qrcode[pil] / pillow / openpyxl`。

## 🛠 构建 Windows exe

仓库已内置打包配置（PyInstaller 单文件）：

```bat
:: 双击运行，或命令行执行
build_windows.bat
```

等价手动步骤：

```bat
python -m pip install pyinstaller "qrcode[pil]" pillow openpyxl
pyinstaller --clean --noconfirm toolbox.spec
:: 产物：dist\Toolbox.exe
```

- 需要 **Python 3.8+**（建议 conda / miniconda 环境）与联网（首次安装依赖）；
- 产物为单文件 **`dist\Toolbox.exe`**，可拷到任意 Windows 10/11 机器直接运行；
- 打包细节见 [`toolbox.spec`](toolbox.spec)：二维码依赖内嵌、前端与脚本资源内置，
  数据目录在运行时外置到 exe 旁（避免写入 exe 临时解包目录导致数据丢失）。

## 🐧 Linux / macOS 运行（原方案，仍可用）

```bash
# 1) 安装（只需一次：创建 conda 环境 + 桌面快捷方式）
cd hub
bash install.sh

# 2) 启动（桌面图标 / 应用菜单 / 命令行 任选）
bash 启动.sh
```

> Windows 与 Linux 使用同一份源码：Windows 把二维码生成改为进程内调用（不依赖
> conda 环境），Linux/macOS 的 `install.sh` + `启动.sh` 流程保持不变。

## 目录结构

```
toolbox/
├── QRcode/                 # 工具一：二维码批量生成（原项目，数据根可配置）
├── us-treasury-yields/     # 工具二：美债收益率看板（原项目，仅改进数据获取）
├── hub/                    # 整合层：统一服务端 + 前端
│   ├── server.py           # 统一 Web 服务（纯 Python 标准库，兼容 exe 打包）
│   ├── static/             # 单页前端
│   ├── features.json       # 功能注册表（动态增删工具）
│   ├── install.sh / 启动.sh  # Linux/macOS 安装与启动脚本
├── toolbox.spec            # PyInstaller 打包配置（Windows 单文件 exe）
├── build_windows.bat       # Windows 一键构建脚本
└── README.md / README_zh.md
```

## GitHub 仓库关系

三个仓库共享同一份代码，这是有意为之：

- **[Tokooy/toolbox](https://github.com/Tokooy/toolbox)** —— **主仓库（Monorepo）**：整合后的
  完整项目（全部工具 + `hub` 整合层 + Windows 打包配置）。从这里开始。
- **[Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields)** —— 工具一的
  独立仓库（美债看板本体，可单独使用）。
- **[Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work)** —— 工具二的
  独立仓库（二维码生成器本体，可单独使用）。

独立仓库与 `toolbox/` 内的副本保持同步，不存在过时的重复副本。
`toolbox/` 是整合发布版，独立仓库是各项目的独立入口。

## 常见问题

**端口被占用？**
关闭旧实例，或换端口重启：

```powershell
# PowerShell
$env:PORT=8088; python server.py
```
```bat
:: CMD
set PORT=8088 && python server.py
```

**美债数据获取失败 / 请求超时？**
本工具已内置自动代理探测（Clash/v2ray 常见端口）。若仍失败，请确认本机网络可访问
FRED，或设置代理环境变量后重启服务：

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
```

**杀毒软件误报？**
单文件 exe 由 PyInstaller 打包，部分杀软会误报；如不放心可改用「方式 B」源码运行，
或在 [VirusTotal](https://www.virustotal.com/) 核查后添加信任。

## 特点

- **一个页面，多种工具**：左侧功能列表切换，全程不刷新跳转；
- **按需运行、互斥执行**：点哪个按钮运行哪个工具，任务不重叠（全局锁）；
- **离线友好**：ECharts 本地托管（无 CDN 依赖）；美债数据本地缓存，增量更新，
  并针对国内网络做了自动代理探测；
- **可动态扩展**：新工具只需放入子目录 + 在 `features.json` 注册。
