#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用注册表
============

Toolbox 的每个工具都是 ``apps/<id>/`` 下一个自洽的「前端 + 后端」小应用：

.. code-block:: text

    apps/qrcode/
    ├── app.json            # 清单：名称/图标/排序/前端入口/后端模块
    ├── backend/            # 后端：纯 Python 逻辑 + HTTP 接口（register(router, ctx)）
    ├── frontend/           # 前端：Vue 面板组件 + 样式（由宿主壳动态加载）
    ├── cli.py              # 独立命令行入口（可选）
    └── standalone.py       # 独立 Web 入口（可选，见 core.standalone）

**新增一个工具 = 新增一个目录**：宿主扫描 ``apps/*/app.json`` 自动发现，
不需要再改 hub 里的任何文件（旧版需要同时改 features.json + index.html + app.js）。

后端契约（``backend`` 指向的模块）：

* ``register(router, ctx)``  必填：把本应用的接口注册到已绑好 ``/api/<id>`` 前缀的子路由；
* ``on_startup(ctx)``        可选：宿主启动后的后台初始化（如首次拉取数据）。
"""

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

__all__ = ['App', 'AppContext', 'discover', 'find', 'load_backend',
           'mount_api', 'startup', 'public_view', 'frontend_urls']

MANIFEST_NAME = 'app.json'


@dataclass
class App:
    """一个工具应用的清单信息。"""

    id: str
    name: str
    dir: Path
    desc: str = ''
    icon: str = 'plus'
    order: int = 100
    backend: str = 'backend.api'
    frontend_entry: str = 'panel.js'
    frontend_style: str = 'panel.css'
    manifest: dict = field(default_factory=dict)

    # ---------------- 路径 ----------------

    @property
    def frontend_dir(self) -> Path:
        return self.dir / 'frontend'

    @property
    def api_prefix(self) -> str:
        """统一的接口前缀：``/api/<id>/``（独立运行与工具台内运行完全一致）。"""
        return '/api/%s/' % self.id

    # ---------------- 展示 ----------------

    def public(self) -> dict:
        """给前端壳的应用摘要（``GET /api/apps`` 的每一项）。"""
        entry, style = frontend_urls(self)
        return {
            'id': self.id,
            'name': self.name,
            'desc': self.desc,
            'icon': self.icon,
            'order': self.order,
            'panel': entry,
            'style': style,
        }


@dataclass
class AppContext:
    """传给应用后端的上下文：应用清单 + 自身接口前缀。"""

    app: App
    prefix: str


def _load_manifest(path: Path) -> dict:
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def discover(apps_dir=None, only: str | None = None) -> list[App]:
    """扫描 ``apps/*/app.json``，按 ``order`` 排序返回已启用的应用。"""
    root = Path(apps_dir or paths.APPS_DIR)
    apps: list[App] = []
    if not root.is_dir():
        return apps
    for child in sorted(root.iterdir()):
        manifest_path = child / MANIFEST_NAME
        if not child.is_dir() or not manifest_path.is_file():
            continue
        data = _load_manifest(manifest_path)
        if not data.get('enabled', True):
            continue
        app = App(
            id=data.get('id') or child.name,
            name=data.get('name') or child.name,
            dir=child,
            desc=data.get('desc', ''),
            icon=data.get('icon', 'plus'),
            order=int(data.get('order', 100)),
            backend=data.get('backend', 'backend.api'),
            frontend_entry=data.get('frontend', {}).get('entry', 'panel.js'),
            frontend_style=data.get('frontend', {}).get('style', 'panel.css'),
            manifest=data,
        )
        if only and app.id != only:
            continue
        apps.append(app)
    apps.sort(key=lambda item: (item.order, item.id))
    return apps


def find(app_id: str, apps_dir=None) -> App | None:
    for app in discover(apps_dir):
        if app.id == app_id:
            return app
    return None


def load_backend(app: App):
    """导入应用后端模块（``apps.<id>.<backend>``，需先 ``paths.bootstrap()``）。"""
    return importlib.import_module('apps.%s.%s' % (app.id, app.backend))


def mount_api(router, app: App) -> App | None:
    """把应用后端注册到宿主路由的 ``/api/<id>`` 子路由上。"""
    module = load_backend(app)
    register = getattr(module, 'register', None)
    if register is None:
        raise RuntimeError('应用 %s 的后端缺少 register(router, ctx)' % app.id)
    register(router.bind('/api/%s' % app.id), AppContext(app=app, prefix='/api/%s' % app.id))
    return app


def startup(app: App):
    """调用应用的可选启动钩子；返回钩子是否被执行。"""
    module = load_backend(app)
    hook = getattr(module, 'on_startup', None)
    if hook is None:
        return False
    hook(AppContext(app=app, prefix='/api/%s' % app.id))
    return True


def frontend_urls(app: App):
    """应用前端资源的 URL（由宿主按 ``/apps/<id>/`` 挂载其 frontend 目录）。"""
    return '/apps/%s/%s' % (app.id, app.frontend_entry), '/apps/%s/%s' % (app.id, app.frontend_style)


def public_view(apps, config: dict | None = None) -> dict:
    """``GET /api/apps`` 的响应体：壳配置 + 应用清单。"""
    config = config or {}
    return {
        'app_name': config.get('app_name', 'Toolbox 工具台'),
        'app_subtitle': config.get('app_subtitle', ''),
        'apps': [app.public() for app in apps],
    }
