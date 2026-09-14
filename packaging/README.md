# 交付与部署（packaging）

同一份代码有四种运行方式，**源码运行是基准**，本目录只提供把它打包/部署出去所需的脚本：

| 方式 | 入口 | 适用场景 |
| --- | --- | --- |
| 源码运行 | `python hub/server.py` | 开发、Linux/macOS 日常使用 |
| Windows 单文件 exe | `packaging/windows/` | 分发给没有 Python 的 Windows 同事 |
| Docker 镜像 | `packaging/docker/` | 服务器 / NAS / VPS，无桌面环境 |
| Linux 桌面快捷方式 | `packaging/linux/` | 本机双击启动（conda 环境 + 桌面图标） |

```
packaging/
├── windows/
│   ├── toolbox.spec        PyInstaller 单文件配置（产物 dist/Toolbox.exe）
│   └── build_windows.bat   一键构建（自动装依赖 + 打包）
├── docker/
│   └── Dockerfile          运行镜像（python:3.12-slim + 二维码依赖 + 种子数据）
└── linux/
    ├── install.sh          一键安装：conda 环境 self_ag + 桌面图标 + 应用菜单
    ├── 启动.sh              一键启动（桌面图标指向它）
    ├── environment.yml     conda 环境定义
    └── icon.svg            桌面图标
```

> `.dockerignore` 例外：它必须放在**仓库根目录**（Docker 只读取构建上下文根下的
> `.dockerignore`），所以不在本目录里。

## 数据目录（三种方式共用同一套约定）

```
<数据根>/
├── qrcode/{input,output,qrcodes}/     二维码的输入、输出与图片缓存
└── treasury/{raw,treasury_yields.csv,meta.json}   美债缓存与 FRED 原始存档
```

数据根按优先级确定（见 `core/paths.py`）：

1. 环境变量 `TOOLBOX_DATA_ROOT`；
2. `TOOLBOX_ROOT`（默认：exe 所在目录，或仓库根）下的 `data/`；
3. 源码运行时即 `<仓库根>/data/`。

代码目录只读、数据目录可写 —— 单文件 exe 会把自己解包到只读临时目录，
因此数据必须落在 exe 旁边，退出后才不会丢。

## Windows：单文件 exe

```bat
:: 在仓库根目录双击，或命令行执行
packaging\windows\build_windows.bat
:: 等价于：pyinstaller --clean --noconfirm packaging\windows\toolbox.spec
```

产物 `dist\Toolbox.exe`：拷到任意 Windows 10/11 机器双击即可运行（自带 Python 运行时）。
首次运行会在 exe 旁生成 `data\` 目录。

> **改了代码一定要重新打包**：exe 把前端、后端与依赖都烘进去了，
> 已经打好的 exe 不会读取你后来修改的源码；源码运行与 Docker 不受影响。

## Docker

```bash
# 构建（必须在仓库根目录，构建上下文就是仓库根）
docker build -f packaging/docker/Dockerfile -t toolbox .

# 运行（数据卷持久化；首次创建时会把镜像里的种子数据灌进卷）
docker run -d --name toolbox -p 8080:8080 -v toolbox_data:/app/data toolbox

# 日常
docker logs -f toolbox
docker restart toolbox
docker rm -f toolbox          # 数据卷保留，重新 run 即恢复
```

访问 `http://<主机IP>:8080`。容器内没有浏览器，“自动打开浏览器”会被忽略。

## Linux / macOS：桌面快捷方式

```bash
bash packaging/linux/install.sh     # 创建 conda 环境 self_ag + 安装桌面图标
bash packaging/linux/启动.sh         # 启动（桌面图标也是调用它）
PORT=8081 bash packaging/linux/启动.sh
```

没有 conda 也能跑：`启动.sh` 会退回系统 `python3`（只有二维码生成需要 `qrcode/pillow/openpyxl`，
工具台本体与美债看板是纯标准库）。

## 各工具单独部署

只想跑其中一个工具时，不必用工具台：

```bash
python apps/treasury/standalone.py   # 只有美债看板（默认 5000）
python apps/qrcode/standalone.py     # 只有二维码生成（默认 5001）
python apps/qrcode/cli.py            # 不开网页，命令行批量生成二维码
```

它们与工具台共用同一份 `core/` 与同一份前端面板代码，接口路径完全一致
（`/api/treasury/**`、`/api/qrcode/**`）。
