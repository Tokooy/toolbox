# Toolbox — 多功能工具台

> English version: [README.md](README.md)

**Toolbox** 是一个**多功能工具集合**：把多个独立的小工具整合进**一个本地网页应用**。
每个工具保持原始代码不动，由统一的 `hub` 整合层把它们汇入同一个单页面板——
点哪个功能按钮就运行哪个功能，不跳转页面，任务互斥（同一时刻只运行一个）。

## 已包含的工具

| 工具 | 说明 | 独立仓库 |
| --- | --- | --- |
| 📈 美债收益率 | 美国 2 / 10 / 30 年期国债收益率走势（FRED 圣路易斯联储权威数据），支持增量更新、自动代理 | [Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields) |
| ▦ 二维码批量生成 | 读取 Excel「二维码编号」列批量生成二维码，输出 HTML / Excel | [Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work) |

> 随时可以添加新工具——每个工具放在自己的子目录里，并在 `hub/features.json` 中注册即可
> （详见 [hub/README_zh.md](hub/README_zh.md)）。

## 目录结构

```
toolbox/
├── QRcode/                 # 工具一：二维码批量生成（原项目，零改动）
├── us-treasury-yields/     # 工具二：美债收益率看板（原项目，仅改进数据获取）
└── hub/                    # 整合层：统一服务端 + 前端
    ├── server.py           # 统一 Web 服务（纯 Python 标准库）
    ├── static/             # 单页前端
    ├── features.json       # 功能注册表（动态增删工具）
    └── install.sh / 启动.sh  # 安装与启动
```

## GitHub 仓库关系

三个仓库共享同一份代码，这是有意为之：

- **[Tokooy/toolbox](https://github.com/Tokooy/toolbox)** —— **主仓库（Monorepo）**：整合后的
  完整项目（全部工具 + `hub` 整合层）。从这里开始。
- **[Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields)** —— 工具一的
  独立仓库（美债看板本体，可单独使用）。
- **[Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work)** —— 工具二的
  独立仓库（二维码生成器本体，可单独使用）。

独立仓库与 `toolbox/` 内的副本保持同步，不存在过时的重复副本。
`toolbox/` 是整合发布版，独立仓库是各项目的独立入口。

## 快速开始

```bash
# 1) 安装（只需一次：创建 conda 环境 + 桌面快捷方式）
cd ~/Desktop/toolbox/hub
bash install.sh

# 2) 启动（桌面图标 / 应用菜单 / 命令行 任选）
bash ~/Desktop/toolbox/hub/启动.sh
```

浏览器自动打开 http://127.0.0.1:8080。详细说明见 [hub/README_zh.md](hub/README_zh.md)。

## 特点

- **一个页面，多种工具**：左侧功能列表切换，全程不刷新跳转；
- **按需运行、互斥执行**：点哪个按钮运行哪个工具，任务不重叠（全局锁）；
- **离线友好**：ECharts 本地托管（无 CDN 依赖）；美债数据本地缓存，增量更新，
  并针对国内网络做了自动代理探测；
- **可动态扩展**：新工具只需放入子目录 + 在 `features.json` 注册。
