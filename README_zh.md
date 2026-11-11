# Toolbox — 多功能工具台

> English version: [README.md](README.md) · 架构详解：[ARCHITECTURE.md](ARCHITECTURE.md)

**Toolbox** 把若干个小工具装进**同一个本地网页**：左侧点按钮切换功能，不跳转页面、不用记命令行。
Agora 在工具台内保留原有研讨界面。

| 工具 | 说明 | 代码位置 |
| --- | --- | --- |
| 📈 美债收益率 | 2 / 10 / 30 年期美国国债收益率曲线（FRED 权威数据），按需联网增量更新 | [`apps/treasury/`](apps/treasury/README.md) |
| ▦ 二维码批量生成 | 读取 Excel「二维码编号」列，批量生成二维码并输出 HTML / Excel | [`apps/qrcode/`](apps/qrcode/README.md) |
| 💬 共识 Agora | 多 Agent 文档研讨、实时对话与 Markdown 报告 | [`apps/agora/`](apps/agora/README.md) |

## 一、快速开始

### Windows：单文件 exe（推荐给没装 Python 的机器）

1. 安装 Python 3.11+ 和 Node.js 22 后，运行构建脚本：
   ```bat
   packaging\windows\build_windows.bat
   ```
2. 产物 `dist\Toolbox.exe` 拷到任意 Windows 10/11 机器，**双击即用**（自带 Python 运行时）；
3. 浏览器自动打开 <http://127.0.0.1:8080>，按 `Ctrl+C` 停止。

> ⚠️ 改了代码必须**重新打包**才会在 exe 里生效：前端、后端与依赖都被烘进了 exe。
> 源码运行与 Docker 不受影响，读的永远是最新代码。

### 源码运行（Python 3.11+ 与 Node.js 22）

```bash
python -m pip install -r requirements.txt
npm --prefix apps/agora/web ci
npm --prefix apps/agora/web run build

python hub/server.py          # 打开 http://127.0.0.1:8080
PORT=8081 python hub/server.py   # 换端口
```

### Docker（服务器 / NAS / 无桌面环境）

```bash
docker build -f packaging/docker/Dockerfile -t toolbox .
docker run -d --name toolbox -p 127.0.0.1:8080:8080 -v toolbox_data:/app/data toolbox
# 访问 http://127.0.0.1:8080
```

### Linux / macOS 桌面快捷方式

```bash
bash packaging/linux/install.sh   # 创建 conda 环境 + 桌面图标 + 应用菜单
bash packaging/linux/启动.sh       # 启动（双击桌面图标等价）
```

> 三种方式的完整说明（含迁移、备份、数据卷）见 [packaging/README.md](packaging/README.md)。

## 二、独立运行入口

美债和二维码工具保留独立启动命令。Agora 的独立版本见 [Tokooy/agora](https://github.com/Tokooy/agora)。

```bash
python apps/treasury/standalone.py   # 只有美债看板       → http://127.0.0.1:5000
python apps/qrcode/standalone.py     # 只有二维码生成     → http://127.0.0.1:5001
python apps/qrcode/cli.py            # 不开网页，命令行批量生成二维码
```

## 三、数据放在哪里

代码只读、数据可写，两者分离（打包成 exe / 挂数据卷时尤其重要）：

```
data/
├── treasury/   美债缓存 + FRED 原始 CSV 存档（随仓库提交，离线开箱即用）
├── qrcode/     二维码 input（上传的 Excel）/ output（生成结果）/ qrcodes（PNG 缓存）
└── agora/      文档提取正文、研讨历史、角色与 API Key 设置
```

数据根按优先级确定：`TOOLBOX_DATA_ROOT` 环境变量 ▸ exe 所在目录（打包运行）▸ 仓库根目录。
所以 exe 放到哪，`data/` 就在哪，换台机器拷过去即可继续用。

## 四、目录结构

```
toolbox/
├── core/          公共内核：路径解析 / HTTP 框架 / 任务与互斥 / 应用注册表（零业务逻辑）
├── apps/          业务：一个工具 = 一个目录 = 后端 + 前端（+ 可选独立运行入口）
│   ├── treasury/    美债收益率看板
│   ├── qrcode/      二维码批量生成
│   └── agora/       多 Agent 文档研讨
├── hub/           工具台外壳：扫描 apps/ 装配路由、托管单页应用（不含业务逻辑）
├── data/          运行时数据（见上）
├── packaging/     交付：Windows exe / Docker / Linux 桌面安装
├── tests/         冒烟测试
└── ARCHITECTURE.md  架构说明（目录职责、依赖方向、接口与前端契约、如何新增工具）
```

## 五、验证

```bash
python tests/smoke_test.py
```

先完成源码运行的安装和构建步骤。测试使用临时数据目录验证外壳、三个工具，以及美债和二维码的独立入口。

## 六、常见问题

**Q：端口被占用？**
A：换端口启动即可：`PORT=8081 python hub/server.py`（Windows PowerShell：`$env:PORT=8081; python hub/server.py`）。
   启动时若端口冲突会直接给出提示。

**Q：美债数据抓取失败？**
A：内置自动代理探测（环境变量 + 常见本地代理端口 7890 / 7897 / 1080 等）。
   仍失败时显式指定后重启：`export HTTPS_PROXY=http://127.0.0.1:7890`。
   抓取失败**不影响**已缓存数据的展示。

**Q：改了代码，exe 里还是旧界面？**
A：重新执行 `packaging\windows\build_windows.bat`（覆盖前先退出正在运行的旧 exe）。

**Q：页面看起来还是旧版本？**
A：服务端对所有响应都带 `Cache-Control: no-store`，正常不会缓存；必要时 `Ctrl+F5` 强制刷新一次。

**Q：杀毒软件报毒？**
A：PyInstaller 单文件 exe 偶尔会被误报，可在 [VirusTotal](https://www.virustotal.com/) 核对，
   或改用源码运行 / Docker 方式。

## 七、技术栈与设计取向

- **后端**使用 Uvicorn 同时运行 Toolbox 路由与 Agora 的 FastAPI 工作台。业务代码位于各工具的 `backend/`。
- **前端**使用本地托管的 Vue 3 和 ECharts。Agora 的 React 前端由 Vite 构建，点击侧栏后按需加载。
- **任务互斥**由 Toolbox 原有工具和 Agora 各自管理。
- **可扩展**：新增工具 = 新增一个 `apps/<id>/` 目录（清单 + 后端 + 前端），
  不需要改 `hub` 里的任何文件 —— 详见 [ARCHITECTURE.md](ARCHITECTURE.md#五新增一个工具)。
