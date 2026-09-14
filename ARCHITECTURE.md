# Toolbox 架构说明

> 这份文档回答一个问题：**“某个功能到底在哪儿？”**
> 结论永远是一句话：业务在 `apps/<工具>/`，公共能力在 `core/`，工具台外壳在 `hub/`。

## 一、为什么重构

这个仓库原本是**两个互不相干的独立项目**（QRcode 批量生成器、美债收益率看板）被强行合并进来的：

* 两个工具各自带着自己的 `server.py` 与整套静态前端；
* 合并时又写了第三个全栈项目 `hub`（自己的服务端 + 自己的 Vue 前端），
  它把两个工具的后端用 `importlib` 动态加载进来，**又把两个工具的前端重写了一遍**；
* 于是同一个功能存在 2~3 份实现：改一处必须记得改另一处，`hub` 到底是“工具”还是“集成层”也说不清。

重构后只保留**一条主线**：

```
core/（公共内核） ← apps/（每个工具：前端 + 后端） ← hub/（外壳：聚合与托管）
```

## 二、目录职责

```
toolbox/
├── core/                  公共内核：不含任何业务逻辑，被 apps 与 hub 复用
│   ├── paths.py           运行时路径：代码根 / 数据根（源码 / exe / Docker 三种场景）
│   ├── http.py            极简 HTTP 框架：路由、静态挂载、请求响应封装（纯标准库）
│   ├── tasks.py           后台任务管理 + 全局任务互斥锁
│   ├── registry.py        应用发现与装配（apps/*/app.json → 路由 + 静态资源）
│   └── standalone.py      把单个应用当作独立站点运行
│
├── apps/                  业务：一个工具 = 一个目录 = 前端 + 后端（+ 可选独立入口）
│   ├── treasury/          美债收益率看板
│   │   ├── app.json         清单：名称/图标/排序/前端入口/后端模块
│   │   ├── backend/         后端：fred.py(网络) → store.py(存储) → service.py(业务) → api.py(接口)
│   │   ├── frontend/        前端：panel.js（Vue 面板组件）+ panel.css
│   │   ├── standalone.py    独立 Web 入口：只有美债看板的单工具站点
│   │   └── README.md        本工具的说明（含数据来源与抓取策略）
│   └── qrcode/            二维码批量生成
│       ├── backend/         generator.py(生成逻辑) + service.py(目录/上传/结果) + api.py(接口)
│       ├── frontend/        panel.js + panel.css
│       ├── cli.py           命令行入口（不启动网页也能批量生成）
│       └── README.md
│
├── hub/                   工具台外壳：只做“聚合与托管”，不含业务逻辑
│   ├── server.py            统一 Web 服务入口（扫描 apps/、挂路由、挂静态资源）
│   ├── hub.json             外壳配置（应用名 / 副标题）
│   └── static/              外壳前端（单页应用壳 + 宿主 SDK + 本地依赖库）
│
├── data/                  运行时数据（与代码分离，可直接挂数据卷 / 放在 exe 旁边）
│   ├── treasury/            美债缓存与 FRED 原始 CSV 存档（种子数据随仓库提交）
│   └── qrcode/              二维码 input / output / qrcodes
│
├── packaging/             交付：Windows 单文件 exe、Docker 镜像、Linux 桌面安装
├── tests/smoke_test.py    冒烟测试：一条命令跑通宿主 + 两个工具的核心链路
└── README.md              使用说明（安装、运行、部署、FAQ）
```

## 三、依赖方向（不可反向）

```
apps/<工具>  ──依赖──▶  core
hub          ──依赖──▶  core + apps/<工具>（只通过 app.json 与 api.register 契约）
core         ──不依赖──▶ 任何业务代码
```

* 每个工具的应用代码只依赖 `core`，**不依赖 `hub`**，因此可以脱离工具台单独运行；
* `hub` 不 import 任何 `apps.*` 的具体模块，只按清单动态装配 —— 删掉一个工具目录，
  工具台照样启动（少一个按钮而已）。

## 四、统一约定

### 4.1 URL 约定

| URL | 含义 |
| --- | --- |
| `/` | 工具台单页应用（宿主外壳） |
| `/static/**` | 外壳前端资源 + 宿主 SDK + 本地依赖库（Vue / ECharts） |
| `/apps/<id>/**` | 该工具自己的前端资源（`apps/<id>/frontend/`） |
| `/api/apps` | 应用清单（外壳据此生成左侧功能按钮） |
| `/api/health` | 健康检查（启动脚本用它判断服务是否已在运行） |
| `/api/<id>/**` | 该工具的后端接口（`apps/<id>/backend/api.py`） |

接口前缀**处处一致**：工具台内是 `/api/treasury/data`，单独运行美债站点时也是
`/api/treasury/data`，所以同一份前端面板两边都能用。

### 4.2 后端契约（`app.json` 的 `backend` 指向的模块）

```python
def register(router, ctx):   # 必填：router 已绑定 /api/<id> 前缀
    router.get('/data', handler)

def on_startup(ctx):         # 可选：服务可访问之后执行的后台初始化（如首次拉数据）
    ...
```

处理函数签名为 `handler(req: core.http.Request) -> None`，
`req.params` 取路径参数、`req.query_one()` 取查询参数、`req.send_json()/send_file()` 回响应。

### 4.3 前端契约（`app.json` 的 `frontend.entry` 指向的文件）

```js
export default {
  template: `<section class="panel" v-show="isActive">…</section>`,
  props: { active: String },        // 宿主传入当前激活的工具 id
  setup(props) { /* 通过 /static/sdk/* 使用宿主能力 */ },
};
```

宿主 SDK（`hub/static/sdk/`）向前端面板提供：Vue 与 ECharts 引用、`api()` 请求封装、
`store`（全局状态）、`toast()` / 弹窗组件、图标常量。

### 4.4 数据目录

* 数据根 = `TOOLBOX_DATA_ROOT` ▸ 否则 `exe 所在目录/data`（打包）▸ 否则 `<仓库根>/data`；
* 每个工具一个子目录：`<数据根>/<工具 id>/`；
* 代码目录只读、数据目录可写 —— 打包成单文件 exe 后代码解包在只读临时目录里，
  数据必须落在 exe 旁边才不会丢。

## 五、新增一个工具

1. 建目录 `apps/<id>/`，写 `app.json`（`id` / `name` / `icon` / `backend` / `frontend`）；
2. 写后端 `backend/api.py`，实现 `register(router, ctx)`；
3. 写前端 `frontend/panel.js`（`export default` 一个 Vue 组件）与 `panel.css`；
4. 重启工具台 —— 按钮、面板、接口全部自动出现。

不需要改 `hub` 里的任何文件（重构前需要同时改 `features.json`、`index.html`、`app.js`）。

## 六、重构进度

| 模块 | 内容 | 状态 |
| --- | --- | --- |
| `core/` | 路径 / HTTP / 任务 / 注册表内核 | ✅ 完成 |
| `apps/treasury/backend` | 美债后端四层拆分 | ✅ 完成 |
| `apps/qrcode/backend` | 二维码生成逻辑与接口拆分 | ✅ 完成 |
| `hub/server.py` | 宿主化：扫描 `apps/` 装配路由 | ✅ 完成 |
| `apps/*/frontend` | 前端面板从 hub 抽回各自应用 | ⏳ 进行中 |
| `hub/static` | 外壳 + 宿主 SDK（替换单体 app.js） | ⏳ 进行中 |
| `data/` | 数据目录与应用代码分离 | ⏳ 待办 |
| `apps/*/standalone.py`、`cli.py` | 各工具独立运行入口 | ⏳ 待办 |
| `packaging/` | exe / Docker / Linux 安装脚本归位 | ⏳ 待办 |

## 七、验证

```bash
# 冒烟测试：临时数据目录里跑通宿主 + 两个工具（零第三方依赖，除二维码生成需要 openpyxl）
python tests/smoke_test.py
```

> 该脚本不访问网络、不污染仓库数据，退出码 0 表示全部通过。
