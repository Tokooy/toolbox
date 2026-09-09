# Toolbox 工具台

把桌面 `toolbox/` 下的两个独立功能整合进**同一个网页**：

| 功能 | 来源 | 说明 |
| --- | --- | --- |
| 📈 美债收益率 | `us-treasury-yields/` | 2 / 10 / 30 年期美国国债收益率走势（FRED 权威数据），核心功能与界面保留 |
| ▦ 二维码批量生成 | `QRcode/` | 读取 Excel「二维码编号」列批量生成二维码，输出 HTML / Excel，界面全新重写 |

- **单页应用**：点击左侧按钮切换功能，全程不跳转页面；
- **按需运行**：点哪个按钮运行哪个功能，平时服务零开销；
- **任务互斥**：二维码生成与美债数据刷新共用一把全局锁，**同一时刻只运行一个任务**；
- **动态扩展**：功能按钮由 `features.json` 生成，新增功能只需改配置 + 提供一个面板。

## 目录结构

```
toolbox/
├── QRcode/                 # 原二维码项目（数据根可配置，支持被 hub 内嵌调用）
├── us-treasury-yields/     # 原美债项目（数据目录支持环境变量覆盖）
└── hub/                    # 整合层（本应用）
    ├── server.py           # 统一 Web 服务（纯 Python 标准库）
    ├── static/             # 前端（index.html / style.css / app.js）
    ├── features.json       # 功能按钮配置（动态增删功能）
    ├── environment.yml     # conda 环境定义（Linux/macOS）
    ├── install.sh          # Linux/macOS 一键安装（建环境 + 装桌面图标）
    ├── 启动.sh             # Linux/macOS 一键启动
    └── Toolbox工具台.desktop
```

> 两个原始项目只做了**最小适配**（数据目录可配置）。`hub` 通过动态加载美债模块、
> **进程内调用**二维码脚本（`run(data_root=...)`）实现复用，核心逻辑未改动。
> Windows 可用 PyInstaller 把整个 `hub` 打包成单文件 `Toolbox.exe`（见仓库根 README）。

## 🪟 Windows 快速开始

Windows 无需 conda / bash，推荐直接使用打包好的单文件 **`Toolbox.exe`**：

1. 双击 `Toolbox.exe` 启动（或源码运行 `python hub/server.py`，需先
   `pip install "qrcode[pil]" pillow openpyxl`）；
2. 浏览器自动打开 http://127.0.0.1:8080；
3. exe 会自动在自身同目录建立 `QRcode/{input,output,qrcodes}` 与
   `us-treasury-yields/data` 数据目录（放在仓库根旁则直接复用仓库内数据）；
4. 停止：控制台窗口按 Ctrl+C。

自行打包：在仓库根执行 `build_windows.bat`（等价 `pyinstaller --clean --noconfirm toolbox.spec`），
产物为 `dist\Toolbox.exe`。

## 一、安装（只需一次，Linux/macOS）

```bash
cd ~/Desktop/toolbox/hub
bash install.sh
```

安装脚本会：
1. 用 conda 新建独立虚拟环境 **`self_ag`**（python 3.11 + qrcode / Pillow / openpyxl），
   不再依赖 base 环境；
2. 安装桌面快捷方式（桌面图标 + GNOME 应用菜单）。

## 二、运行（三种方式任选）

### 方式 1：双击桌面图标（最方便）
桌面出现 **「Toolbox 工具台」** 图标，双击即可启动（弹出终端窗口显示服务日志，`Ctrl+C` 停止）。

### 方式 2：应用菜单
GNOME 按 `Super` 键搜索「Toolbox」→ 点击启动。

### 方式 3：命令行
```bash
bash ~/Desktop/toolbox/hub/启动.sh
# 或
cd ~/Desktop/toolbox/hub && conda activate self_ag && python server.py
```

启动后浏览器自动打开 **http://127.0.0.1:8080**。

> 端口被占用时：`PORT=8081 bash 启动.sh`，然后访问 http://127.0.0.1:8081。

## 三、使用说明

### 美债收益率
- 页面自动展示 2020 年至今三条收益率曲线（滚轮缩放 / 拖拽平移 / 悬停看数值）；
- **平滑衔接**：非交易日（周末/节假日）FRED 无数据，曲线已剔除空值点、平滑连续不中断；
- **点击聚焦**：点击图例或任意一条曲线，只显示该曲线（其他隐藏），再点一次恢复全部显示；
- 点击 **「获取最新数据」** 才联网从 FRED 更新数据，平时完全离线读本地缓存；
- **增量更新**：已有本地数据时，只从最后一条数据日期开始获取缺失的那几天，
  不重复下载全量历史，失败时本地数据原样保留；
- **无缓存时**：页面立即打开并提示「暂无本地数据」，点按钮才联网获取，不会卡死；
- **自动代理**：服务启动时自动探测环境变量代理及常见本地代理端口
  （7890 / 7897 / 1080 等，兼容 Clash / v2ray），探测到即自动走代理获取，
  「开了全局代理但服务没走代理」的问题不再存在；
- **网络兼容**：已去掉浏览器 UA（FRED 边缘节点 Akamai 会黑洞「浏览器 UA + 非浏览器
  指纹」的组合请求，实测诚实默认 UA 直连/走代理均正常）；
- **时区说明**：FRED 数据日期为**美国交易日（美东时间）收盘值**，与北京时间存在
  约 12-13 小时时差，所以"今天"是否有新数据以 FRED 实际发布为准（页面会提示
  「已是最新数据 / FRED 尚未发布更新的交易日数据」）。

### 二维码批量生成
1. **上传 Excel**（点击或拖拽，支持 `.xlsx` / `.xls`），第一列列名须为「二维码编号」；
   - 支持 Excel 自动筛选：只生成筛选后可见的行；
   - 上传后旧输入文件会自动移入 `QRcode/input/_旧文件备份_时间戳/`，不删除。
2. 点击 **「开始生成二维码」** → 页面实时滚动显示运行日志；
3. 生成完成后在页面内直接预览二维码网格，可一键下载 **HTML** 与 **Excel** 输出。

输出文件位于 `QRcode/output/`（文件名带当天日期前缀），单张 PNG 缓存位于 `QRcode/qrcodes/`。

## 四、如何添加新功能（预留按钮动态调整）

1. 编辑 `hub/features.json`，在 `features` 数组里加一项：

```json
{
  "id": "myfeature",
  "name": "我的新功能",
  "desc": "一句话说明",
  "icon": "plus",
  "status": "ready"
}
```

2. 在 `hub/static/index.html` 中新增一个 `<section class="panel" id="panel-myfeature">…</section>`；
3. 在 `hub/static/app.js` 的 `switchFeature()` 中处理 `myfeature` 分支。

> `"status"` 非 `"ready"` 的条目不会出现在页面上（侧栏只显示已就绪功能）。
> 侧栏可整体收起/展开：侧栏右上角**同一个按钮**切换（展开时显示「<」、收起后
> 窄条上显示「>」）；收起后侧栏收成 48px 窄条图标，主内容区自动变宽，
> 二维码预览的每行数量也随之动态增加。
> 若新功能有独立运行任务，请通过 `TaskManager.acquire()` / `release()` 加入互斥，
> 服务端在 `server.py` 中统一走 `_global_task_lock`。

## 五、常见问题

**Q：双击桌面图标没反应？**
A：GNOME 首次需要信任文件：右键图标 →「允许启动」。若仍不行，运行一次
`gio set ~/Desktop/Toolbox工具台.desktop metadata::trusted true`。

**Q：提示找不到 conda 环境 self_ag？**
A：运行 `bash ~/Desktop/toolbox/hub/install.sh` 完成环境创建。

**Q：美债图表空白？**
A：图表库 ECharts 已**本地托管**（`hub/static/vendor/echarts.min.js`），完全不依赖外网 CDN，
离线也能正常显示图表。若仍空白，请刷新页面（Ctrl+Shift+R 强制刷新）清除旧缓存。

**Q：点击「获取最新数据」提示连接失败？**
A：FRED 服务器对国内网络直连常不稳定。请先确认网络，或为本机配置代理后重启服务：
`export HTTPS_PROXY=http://127.0.0.1:7890 && bash 启动.sh`。失败不影响已缓存数据的查看。

**Q：二维码生成为什么不能和美债刷新同时点？**
A：这是刻意设计——两个任务共用一把互斥锁，保证同一时刻只运行一个，性能不受损。

## 技术栈

- 后端：Python 标准库 `http.server`（零第三方依赖）；美债模块动态加载原 `server.py`
  （数据目录可用 `TOOLBOX_TREASURY_HOME` 覆盖）；二维码脚本**进程内加载**执行
  （`generate_qrcodes.run(data_root=...)`，Linux 下亦可沿用 `self_ag` conda 环境）；
- 前端：Vue 3（本地离线托管 `static/vendor/vue.global.prod.js`，无 CDN / 无需构建）+
  ECharts 5 本地托管；组件化单页应用，二维码结果支持**每 3 个一组左右翻页**扫码与
  任务进度条；
- 数据：FRED（圣路易斯联储）；二维码：`qrcode[pil]` + openpyxl；
- Windows exe：PyInstaller 单文件打包（`toolbox.spec`），运行环境与依赖全部内嵌。
