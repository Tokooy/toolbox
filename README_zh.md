# Toolbox — 多功能工具台

> English version: [README.md](README.md) · 架构详解：[ARCHITECTURE.md](ARCHITECTURE.md)

**Toolbox** 把若干个小工具装进**同一个本地网页**：左侧点按钮切换功能，不跳转页面、不用记命令行。
所有工具共用一套外壳与后端内核，每个工具也可以**脱离工具台单独运行**。

| 工具 | 说明 | 代码位置 |
| --- | --- | --- |
| 📈 美债收益率 | 2 / 10 / 30 年期美国国债收益率曲线（FRED 权威数据），按需联网增量更新 | [`apps/treasury/`](apps/treasury/README.md) |
| ▦ 二维码批量生成 | 读取 Excel「二维码编号」列，批量生成二维码并输出 HTML / Excel | [`apps/qrcode/`](apps/qrcode/README.md) |

## 一、快速开始

### Windows：单文件 exe（推荐给没装 Python 的机器）

1. 构建（在仓库根目录双击，或命令行执行）：
   ```bat
   packaging\windows\build_windows.bat
   ```
2. 产物 `dist\Toolbox.exe` 拷到任意 Windows 10/11 机器，**双击即用**（自带 Python 运行时）；
3. 浏览器自动打开 <http://127.0.0.1:8080>，按 `Ctrl+C` 停止。

> ⚠️ 改了代码必须**重新打包**才会在 exe 里生效：前端、后端与依赖都被烘进了 exe。
> 源码运行与 Docker 不受影响，读的永远是最新代码。

### 源码运行（任意平台，开发首选）

```bash
# 只有二维码生成需要第三方库；工具台本体与美债看板是纯标准库
python -m pip install "qrcode[pil]" pillow openpyxl

python hub/server.py          # 打开 http://127.0.0.1:8080
PORT=8081 python hub/server.py   # 换端口
```

### Docker（服务器 / NAS / 无桌面环境）

```bash
docker build -f packaging/docker/Dockerfile -t toolbox .
docker run -d --name toolbox -p 8080:8080 -v toolbox_data:/app/data toolbox
# 访问 http://<主机IP>:8080
```

### Linux / macOS 桌面快捷方式

```bash
bash packaging/linux/install.sh   # 创建 conda 环境 + 桌面图标 + 应用菜单
bash packaging/linux/启动.sh       # 启动（双击桌面图标等价）
```

> 三种方式的完整说明（含迁移、备份、数据卷）见 [packaging/README.md](packaging/README.md)。

## 二、每个工具都能单独运行

不想用工具台时，直接跑单个工具即可（接口与前端面板和工具台内**完全一致**）：

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
└── qrcode/     二维码 input（上传的 Excel）/ output（生成结果）/ qrcodes（PNG 缓存）
```

数据根按优先级确定：`TOOLBOX_DATA_ROOT` 环境变量 ▸ exe 所在目录（打包运行）▸ 仓库根目录。
所以 exe 放到哪，`data/` 就在哪，换台机器拷过去即可继续用。

## 四、目录结构

```
toolbox/
├── core/          公共内核：路径解析 / HTTP 框架 / 任务与互斥 / 应用注册表（零业务逻辑）
├── apps/          业务：一个工具 = 一个目录 = 后端 + 前端（+ 可选独立运行入口）
│   ├── treasury/    美债收益率看板
│   └── qrcode/      二维码批量生成
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

零第三方依赖（除二维码生成需要 `openpyxl`），在临时数据目录里跑通
「外壳 + 两个工具 + 各自独立运行」的全部核心链路，退出码 0 表示通过，可直接接 CI。

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

- **后端**：纯 Python 标准库（`http.server` / `urllib` / `csv`），零第三方依赖；
  公共能力集中在 `core/`，业务在各 `apps/<工具>/backend/`，工具台外壳只做装配；
- **前端**：Vue 3 + ECharts 5，**本地托管、无 CDN、无构建步骤**；
  外壳（`hub/static`）负责导航与通知，各工具的面板（`apps/<工具>/frontend/panel.js`）按需加载；
- **任务互斥**：所有重任务共用一把全局锁，同一时刻只运行一个，避免抢网络 / 磁盘；
- **可扩展**：新增工具 = 新增一个 `apps/<id>/` 目录（清单 + 后端 + 前端），
  不需要改 `hub` 里的任何文件 —— 详见 [ARCHITECTURE.md](ARCHITECTURE.md#五新增一个工具)。
