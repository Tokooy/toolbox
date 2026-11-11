#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toolbox 工具台 · 统一 Web 服务（多工具宿主）
================================================

`hub` 是工具台的**宿主外壳**：它自己不含任何业务逻辑，只做三件事：

1. 扫描 ``apps/*/app.json``，装配工具的 API 或 ASGI 工作台；
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
import socket
import sys
import threading
import webbrowser
from contextlib import AsyncExitStack, asynccontextmanager
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
from hub.asgi import ToolboxRoutes                        # noqa: E402
from starlette.applications import Starlette              # noqa: E402
from starlette.routing import Mount                       # noqa: E402
import uvicorn                                            # noqa: E402

PORT = int(os.environ.get('PORT', '8080'))
# 监听地址：默认仅本机回环；Docker 部署时设 HOST=0.0.0.0 以便端口映射到外部
HOST = os.environ.get('HOST', '127.0.0.1')


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


def create_app(apps=None, *, startup=True, browser_url=None):
    paths.bootstrap()
    if apps is None:
        apps = registry.discover()
    router = build_router(apps, load_config())
    router.get('/', lambda req: req.send_file(paths.STATIC_DIR / 'index.html'))

    workspaces = [
        (app.id, registry.load_backend(app).app) for app in apps if app.asgi
    ]
    routes = []
    for app_id, workspace in workspaces:
        prefix = '/apps/%s/workspace' % app_id
        routes.append(Mount(prefix, app=workspace))
        router.get(prefix, lambda req, location=prefix + '/': req.redirect(location))
    routes.append(Mount('/', app=ToolboxRoutes(router, static_mounts(apps))))

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for _, workspace in workspaces:
                await stack.enter_async_context(workspace.router.lifespan_context(workspace))
            if startup:
                threading.Thread(target=_run_startup, args=(apps,), daemon=True).start()
            if browser_url:
                threading.Thread(target=webbrowser.open, args=(browser_url,), daemon=True).start()
            yield

    return Starlette(routes=routes, lifespan=lifespan)


def main():
    http.configure_console()
    apps = registry.discover()
    for line in check_frontends(apps):
        print('  ⚠ 前端入口缺失（面板将无法加载）：%s' % line)
    if not apps:
        print('  ⚠ apps/ 下没有发现任何已启用的工具（检查 apps/*/app.json）')

    try:
        family = socket.AF_INET6 if ':' in HOST else socket.AF_INET
        listener = socket.create_server((HOST, PORT), family=family)
    except OSError as exc:
        print(http.port_error_hint(PORT, exc))
        sys.exit(1)

    url = 'http://127.0.0.1:%d' % listener.getsockname()[1]
    banner = [
        '  ═══════════════════════════════════════════════',
        '   Toolbox 工具台 已启动（%d 个工具）' % len(apps),
        '    ➜ %s' % url,
        '   ⚡ 点击侧栏切换工具',
        '   ⏹ 按 Ctrl+C 停止服务',
        '  ═══════════════════════════════════════════════',
    ]
    print('\n'.join(banner), flush=True)
    browser_url = url if not os.environ.get('TOOLBOX_NO_BROWSER') else None
    with listener:
        config = uvicorn.Config(create_app(apps, browser_url=browser_url), loop='asyncio',
                                http='h11', ws='none', timeout_graceful_shutdown=3)
        uvicorn.Server(config).run(sockets=[listener])


def _run_startup(apps) -> None:
    """在服务可访问之后执行各应用的启动钩子（慢网络不阻塞页面打开）。"""
    for app in apps:
        try:
            registry.startup(app)
        except Exception as exc:                          # noqa: BLE001 - 应用启动失败不该拖垮工具台
            print('  ⚠ 应用 %s 启动钩子失败：%s' % (app.id, exc))


if __name__ == '__main__':
    main()
