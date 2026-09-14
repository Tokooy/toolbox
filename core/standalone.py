#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把单个应用当作独立站点运行
==============================

工具台（``hub``）是把所有工具装进同一个页面；这里提供的是**反过来**的能力：
只启动某一个工具，页面里只有它一个人 —— 用途有两个：

1. 每个工具仍可像重构前那样“单独运行、单独部署”，不必拖家带口；
2. 开发某个工具时不必关心其它工具的状态。

实现方式与工具台完全一致（同一套 ``core.http`` 路由 + 同一份前端面板代码），
只是应用清单里只放这一个应用：

* 页面：``/``                       单工具页面（无侧栏）
* 接口：``/api/<id>/**``            与工具台内完全相同的路径
* 资源：``/static/**``（外壳 SDK 与依赖）、``/apps/<id>/**``（本工具前端）

用法::

    python apps/treasury/standalone.py      # 只有美债看板
    python apps/qrcode/standalone.py        # 只有二维码生成
    PORT=9000 python apps/treasury/standalone.py
"""

import json
import os

from . import http, paths, registry

__all__ = ['page_html', 'build_router', 'serve_app']

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__</title>
<link rel="stylesheet" href="/static/shell.css" />
<link rel="stylesheet" href="__STYLE__" />
</head>
<body>
<div id="app"></div>

<script>window.__TOOLBOX_STANDALONE__ = __CONFIG__;</script>
<script src="/static/vendor/vue.global.prod.js"></script>
<script src="/static/vendor/echarts.min.js"></script>
<script type="module">
  import { Vue } from '/static/sdk/runtime.js';
  import { ModalBox, ToastBox } from '/static/sdk/ui.js';

  const cfg = window.__TOOLBOX_STANDALONE__;
  const panel = (await import(cfg.panel)).default;

  const Root = {
    components: { Panel: panel, ModalBox, ToastBox },
    template: `
      <div>
        <div class="bg-glow" aria-hidden="true"></div>
        <header class="topbar">
          <div class="brand">
            <div class="logo" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1"
                   stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>
                <rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 14h7v7h-7z" fill="currentColor" stroke="none" opacity="0.9"/>
              </svg>
            </div>
            <div class="brand-text">
              <h1>{{ name }}</h1>
              <p>{{ desc }}</p>
            </div>
          </div>
          <div class="topbar-right">
            <div class="task-indicator">独立运行模式 · 只有本工具</div>
          </div>
        </header>
        <div class="layout layout-single">
          <main class="main"><panel :active="id"></panel></main>
        </div>
        <modal-box></modal-box>
        <toast-box></toast-box>
      </div>`,
    setup() {
      return { id: cfg.id, name: cfg.name, desc: cfg.desc };
    },
  };
  Vue.createApp(Root).mount('#app');
</script>
</body>
</html>
"""


def page_html(app) -> str:
    """单工具页面：复用外壳样式与宿主 SDK，只挂载这一个应用的面板。"""
    entry, style = registry.frontend_urls(app)
    config = json.dumps({'id': app.id, 'name': app.name, 'desc': app.desc, 'panel': entry},
                        ensure_ascii=False)
    return (_PAGE
            .replace('__TITLE__', '%s · Toolbox' % app.name)
            .replace('__STYLE__', style)
            .replace('__CONFIG__', config))


def build_router(app) -> http.Router:
    router = http.Router()
    api = router.bind('/api')

    def health(req):
        from datetime import datetime
        req.send_json({'ok': True, 'app': app.id, 'ts': datetime.now().isoformat()})

    def apps_index(req):
        req.send_json(registry.public_view([app], {'app_name': app.name,
                                                   'app_subtitle': app.desc}))

    api.get('/health', health)
    api.get('/apps', apps_index)
    registry.mount_api(router, app)

    # 首页与静态资源：路径与工具台内完全一致，前端面板代码无需任何改动
    router.get('/', lambda req: req.send_html(page_html(app)))
    return router


def serve_app(app_id: str, host: str | None = None, port: int | None = None,
              open_browser: bool = True) -> None:
    """启动单应用站点（阻塞）。端口优先级：参数 > ``PORT`` 环境变量 > app.json 的 standalonePort。"""
    paths.bootstrap()
    app = registry.find(app_id)
    if app is None:
        raise SystemExit('✗ 找不到应用 %r（检查 apps/%s/app.json）' % (app_id, app_id))

    host = host or os.environ.get('HOST', '127.0.0.1')
    port = int(port or os.environ.get('PORT') or app.manifest.get('standalonePort', 8080))

    mounts = [http.StaticMount('/static', paths.STATIC_DIR),
              http.StaticMount('/apps/%s' % app.id, app.frontend_dir)]
    try:
        server = http.make_server(host, port, build_router(app), mounts,
                                  'ToolboxStandalone/2.0')
    except OSError as exc:
        print(http.port_error_hint(port, exc))
        raise SystemExit(1) from exc

    url = 'http://127.0.0.1:%d' % port
    banner = [
        '  ═══════════════════════════════════════════════',
        '   %s 已启动（独立运行模式）' % app.name,
        '    ➜ %s' % url,
        '   ⏹ 按 Ctrl+C 停止服务',
        '  ═══════════════════════════════════════════════',
    ]

    def startup():
        try:
            registry.startup(app)
        except Exception as exc:                      # noqa: BLE001 - 启动钩子失败不该拖垮站点
            print('  ⚠ 启动钩子失败：%s' % exc)

    http.serve_forever(server, url, banner, open_browser, before_serve=startup)
