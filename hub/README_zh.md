# Toolbox Hub — 工具台外壳

> English version: [README.md](README.md)

`hub` 是工具台的**宿主外壳**：它自己**不含任何业务逻辑**，只做四件事：

1. 扫描 `apps/*/app.json` 发现所有工具；
2. 把每个工具的后端挂到 `/api/<工具 id>/`（见 `core/registry.py`）；
3. 托管外壳前端（`hub/static/`）与各工具自己的前端资源（`apps/<id>/frontend/`）；
4. 启动 HTTP 服务、打印地址、按需打开浏览器。

业务能力在 `apps/`，公共能力在 `core/` —— 想知道「某个功能在哪」，答案永远是 `apps/<工具>/`。

## 目录内容

```
hub/
├── server.py     统一 Web 服务入口（装配路由与静态资源，唯一启动入口）
├── hub.json      外壳配置（应用名 / 副标题）
├── __init__.py   包标记（便于测试与工具直接 import hub.server）
└── static/       外壳前端（无 CDN、无构建步骤）
    ├── index.html    单页应用入口：只加载本地 Vue / ECharts + shell.js
    ├── shell.js      外壳：读 /api/apps 生成侧栏，按需 import('/apps/<id>/panel.js')
    ├── shell.css     设计系统与布局（主题变量、顶栏、侧栏、按钮、卡片、弹窗、Toast）
    ├── sdk/          宿主 SDK（外壳与所有面板共用）
    │   ├── runtime.js   Vue / ECharts 引用
    │   ├── api.js       统一 JSON 请求封装 + sleep
    │   ├── ui.js        全局 store、toast、弹窗组件
    │   └── icons.js     内联 SVG 图标常量
    └── vendor/       本地依赖库：vue.global.prod.js、echarts.min.js
```

## 运行

```bash
python hub/server.py          # http://127.0.0.1:8080
PORT=8081 python hub/server.py
TOOLBOX_NO_BROWSER=1 python hub/server.py   # 不自动打开浏览器（服务器 / CI）
```

## HTTP 约定

| 路径 | 含义 |
| --- | --- |
| `/` | 工具台单页应用（外壳） |
| `/static/**` | 外壳资源 + 宿主 SDK + 本地依赖库 |
| `/apps/<id>/**` | 该工具自己的前端资源（`apps/<id>/frontend/`） |
| `/api/apps` | 应用清单（外壳据此生成左侧按钮） |
| `/api/health` | 健康检查（启动脚本用它判断服务是否已在运行） |
| `/api/<id>/**` | 该工具的后端接口 |

所有响应都带 `Cache-Control: no-store`，前端资源随代码更新即时生效，不会出现「改了代码页面还是旧的」。

## 新增一个工具

新增 `apps/<id>/` 目录（`app.json` + `backend/api.py` + `frontend/panel.js`）后重启即可，
按钮、面板、接口全部自动出现 —— **不需要修改 `hub` 里的任何文件**。

完整契约（后端 `register(router, ctx)` / 前端 `export default` 组件 / 宿主 SDK 用法）见
[../ARCHITECTURE.md](../ARCHITECTURE.md) 第四节，示例可直接参照 `apps/treasury/` 与 `apps/qrcode/`。

## 说明

* 打包成 Windows 单文件 exe 时，`hub/static`、`hub.json`、`core/`、`apps/` 与种子数据会作为资源打进包内，
  运行期从只读的 `_MEIPASS` 目录读取；可变数据则写到 exe 旁边（见 `core/paths.py`）。
* 任务互斥（同一时刻只跑一个重任务）由 `core/tasks.py` 提供，外壳顶栏的状态点显示它的忙闲。
