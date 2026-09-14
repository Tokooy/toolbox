#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toolbox 工具台 · 统一 Web 服务（多工具宿主）
================================================

`hub` 是工具台的**宿主外壳**：它自己不含任何业务逻辑，只做三件事：

1. 扫描 ``apps/*/app.json`` 发现所有工具，把它们的后端挂到 ``/api/<工具 id>/``；
2. 托管外壳前端（``hub/static/``，单页应用）与各工具的前端资源（``apps/<id>/frontend/``）；
3. 启动 HTTP 服务、打印地址、按需打开浏览器。

业务能力全部在 ``apps/`` 里，公共能力在 ``core/`` 里 —— 想知道“某个功能在哪”，
答案永远是 ``apps/<工具>/``。

运行（源码）  ：python hub/server.py  →  http://127.0.0.1:8080
运行（Windows）：双击打包好的 Toolbox.exe（PyInstaller 单文件，自带运行环境）
运行（Docker） ：见 packaging/docker/Dockerfile
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# 路径引导：让 `import core.* / apps.*` 在源码与打包 exe 两种方式下都成立
#   * 源码模式：仓库根目录 = hub/ 的上一级
#   * 打包模式：代码资源被解包到只读的 _MEIPASS 目录（PyInstaller 单文件 exe）
# --------------------------------------------------------------------------
if getattr(sys, 'frozen', False):                        # pragma: no cover - 打包产物
    _CODE_ROOT = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)).resolve()
else:
    _CODE_ROOT = Path(__file__).resolve().parent.parent
if str(_CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT))

from core import http, paths, registry                    # noqa: E402

PORT = int(os.environ.get('PORT', '8080'))
# 监听地址：默认仅本机回环；Docker 部署时设 HOST=0.0.0.0 以便端口映射到外部
HOST = os.environ.get('HOST', '127.0.0.1')
SERVER_VERSION = 'ToolboxHub/2.0'


def load_config() -> dict:
    """外壳配置（应用名 / 副标题），缺省时用内置文案。"""
    path = paths.HUB_DIR / 'hub.json'
    if not path.is_file():
        return {}
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def build_router(apps, config) -> http.Router:
    """核心接口 + 各应用接口：``/api/health``、``/api/apps``、``/api/<app>/*``。"""
    router = http.Router()
    api = router.bind('/api')

    def health(req):
        req.send_json({'ok': True, 'ts': datetime.now().isoformat()})

    def apps_index(req):
        req.send_json(registry.public_view(apps, config))

    api.get('/health', health)
    api.get('/apps', apps_index)
    for app in apps:
        registry.mount_api(router, app)
    return router


def static_mounts(apps):
    """``/static/`` → 外壳资源；``/apps/<id>/`` → 该工具自己的前端目录。"""
    mounts = [http.StaticMount('/static', paths.STATIC_DIR)]
    for app in apps:
        mounts.append(http.StaticMount('/apps/%s' % app.id, app.frontend_dir))
    return mounts


def check_frontends(apps) -> list[str]:
    """开发期体检：清单里声明的前端入口是否真的存在。"""
    missing = []
    for app in apps:
        if not (app.frontend_dir / app.frontend_entry).is_file():
            missing.append('%s -> %s' % (app.id, app.frontend_dir / app.frontend_entry))
    return missing


def main():
    paths.bootstrap()
    config = load_config()
    apps = registry.discover()

    router = build_router(apps, config)
    router.get('/', lambda req: req.send_file(paths.STATIC_DIR / 'index.html'))

    for line in check_frontends(apps):
        print('  ⚠ 前端入口缺失（面板将无法加载）：%s' % line)
    if not apps:
        print('  ⚠ apps/ 下没有发现任何已启用的工具（检查 apps/*/app.json）')

    try:
        server = http.make_server(HOST, PORT, router, static_mounts(apps), SERVER_VERSION)
    except OSError as exc:
        print(http.port_error_hint(PORT, exc))
        sys.exit(1)

    url = 'http://127.0.0.1:%d' % PORT
    banner = [
        '  ═══════════════════════════════════════════════',
        '   Toolbox 工具台 已启动（%d 个工具）' % len(apps),
        '    ➜ %s' % url,
        '   ⚡ 点哪个按钮运行哪个功能，同一时刻只运行一个任务',
        '   ⏹ 按 Ctrl+C 停止服务',
        '  ═══════════════════════════════════════════════',
    ]
    http.serve_forever(server, url, banner, before_serve=lambda: _run_startup(apps))


def _run_startup(apps) -> None:
    """在服务可访问之后执行各应用的启动钩子（慢网络不阻塞页面打开）。"""
    for app in apps:
        try:
            registry.startup(app)
        except Exception as exc:                          # noqa: BLE001 - 应用启动失败不该拖垮工具台
            print('  ⚠ 应用 %s 启动钩子失败：%s' % (app.id, exc))


if __name__ == '__main__':
    main()
