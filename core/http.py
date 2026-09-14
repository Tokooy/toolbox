#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 HTTP 框架（纯 Python 标准库）
====================================

Toolbox 里所有 Web 服务（多工具宿主 ``hub`` 与单工具 ``standalone``）都建立在这三个东西上：

* :class:`Router`      —— 方法 + 路径模式（``/task/<task_id>``）到处理函数的映射，
  支持 ``bind(prefix)`` 生成子路由，因此每个应用只需关心自己那一段相对路径；
* :class:`StaticMount` —— URL 前缀到磁盘目录的静态资源映射（防目录穿越）；
* :class:`Request`     —— 把 ``BaseHTTPRequestHandler`` 包装成好用的请求/响应对象，
  处理函数统一写成 ``def handle(req: Request) -> None``。

约定：所有响应都带 ``Cache-Control: no-store``，前端资源随代码更新即时生效，
不需要手动刷缓存（打包 exe / Docker 场景同样受益）。
"""

import json
import mimetypes
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

__all__ = [
    'Router', 'StaticMount', 'Request', 'make_handler', 'make_server',
    'serve_forever', 'port_error_hint', 'configure_console', 'content_type_for',
]

_PARAM_RE = re.compile(r'<(?:(?P<kind>\w+):)?(?P<name>\w+)>')

# Web 资源类型写死：Windows 上 mimetypes 会读注册表，个别机器会把 .js 认成 text/plain，
# 而浏览器对 ES module 的 MIME 类型是严格校验的（text/plain 直接拒绝执行）。
_WEB_TYPES = {
    '.js': 'text/javascript',
    '.mjs': 'text/javascript',
    '.css': 'text/css',
    '.html': 'text/html; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.map': 'application/json; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.csv': 'text/csv; charset=utf-8',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


def content_type_for(path) -> str:
    """按扩展名给出响应类型：优先内置表，其次系统 mimetypes。"""
    suffix = Path(path).suffix.lower()
    if suffix in _WEB_TYPES:
        return _WEB_TYPES[suffix]
    return mimetypes.guess_type(str(path))[0] or 'application/octet-stream'


def _compile(pattern: str):
    """把 ``/task/<task_id>`` 编译成正则；``<path:name>`` 允许匹配多段路径。"""
    params = []

    def repl(match):
        kind = match.group('kind') or 'str'
        name = match.group('name')
        params.append(name)
        return r'(?P<%s>%s)' % (name, '.+' if kind == 'path' else '[^/]+')

    regex = _PARAM_RE.sub(repl, pattern)
    return re.compile('^' + regex + '$'), tuple(params)


class Router:
    """方法 + 路径 → 处理函数。``bind('/api')`` 得到带前缀的子路由。

    子路由与父路由**共享同一张路由表**，因此应用可以注册到 ``bind()`` 出来的子路由上，
    最终仍由根路由统一分发（宿主只需把根路由交给 :func:`make_server`）。
    """

    def __init__(self, prefix: str = '', routes: list | None = None):
        self.prefix = prefix.rstrip('/')
        self._routes = routes if routes is not None else []

    def bind(self, prefix: str) -> 'Router':
        return Router(self.prefix + '/' + prefix.strip('/'), self._routes)

    def add(self, method: str, pattern: str, handler):
        regex, params = _compile(self.prefix + pattern)
        self._routes.append((method.upper(), regex, params, handler))
        return handler

    def get(self, pattern: str, handler):
        return self.add('GET', pattern, handler)

    def post(self, pattern: str, handler):
        return self.add('POST', pattern, handler)

    def resolve(self, method: str, path: str):
        """返回 ``(handler, params)``；未命中返回 ``None``。"""
        for route_method, regex, params, handler in self._routes:
            if route_method != method.upper():
                continue
            match = regex.match(path)
            if match:
                return handler, {k: unquote(v) for k, v in match.groupdict().items()}
        return None


class StaticMount:
    """把 ``/static/`` 这样的 URL 前缀映射到磁盘目录（只读、防目录穿越）。"""

    def __init__(self, url_prefix: str, directory):
        self.url_prefix = '/' + url_prefix.strip('/') + '/'
        self.directory = Path(directory).resolve()

    def resolve(self, path: str):
        """命中返回磁盘文件路径，否则返回 ``None``。"""
        if not path.startswith(self.url_prefix):
            return None
        rel = unquote(path[len(self.url_prefix):])
        candidate = (self.directory / rel).resolve()
        if candidate != self.directory and self.directory not in candidate.parents:
            return None                      # 目录穿越（../../etc/passwd）直接拒绝
        return candidate if candidate.is_file() else None


class Request:
    """一次请求：读参数/请求体 + 写响应。处理函数只依赖这个对象。"""

    def __init__(self, handler: BaseHTTPRequestHandler, params: dict):
        self._h = handler
        self.params = params
        self.method = handler.command
        self.responded = False          # 已发出响应则不再补发 500，避免写坏 HTTP 流
        parsed = urlparse(handler.path)
        self.path = parsed.path
        self.query = parse_qs(parsed.query)

    # ---------------- 读 ----------------

    def query_one(self, name: str, default=None):
        values = self.query.get(name)
        return values[0] if values else default

    def body(self) -> bytes:
        length = int(self._h.headers.get('Content-Length') or 0)
        return self._h.rfile.read(length) if length > 0 else b''

    def json_body(self) -> dict:
        raw = self.body()
        return json.loads(raw.decode('utf-8')) if raw else {}

    # ---------------- 写 ----------------

    def send_json(self, obj, status: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_bytes(body, 'application/json; charset=utf-8', status)

    def send_error(self, status: int, message: str):
        self.send_json({'error': message}, status)

    def send_html(self, html: str, status: int = 200):
        self.send_bytes(html.encode('utf-8'), 'text/html; charset=utf-8', status)

    def send_bytes(self, body: bytes, content_type: str, status: int = 200,
                   filename: str | None = None, extra_headers: dict | None = None):
        handler = self._h
        self.responded = True
        handler.send_response(status)
        handler.send_header('Content-Type', content_type)
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        if filename:
            handler.send_header('Content-Disposition',
                                "attachment; filename*=UTF-8''" + quote(filename))
        for key, value in (extra_headers or {}).items():
            handler.send_header(key, value)
        handler.end_headers()
        try:
            handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass                             # 客户端已断开，忽略

    def send_file(self, path, content_type: str | None = None, filename: str | None = None):
        path = Path(path)
        if not path.is_file():
            self.send_error(404, 'Not Found')
            return
        self.send_bytes(path.read_bytes(), content_type or content_type_for(path),
                        filename=filename)

    def redirect(self, location: str, status: int = 302):
        handler = self._h
        self.responded = True
        handler.send_response(status)
        handler.send_header('Location', location)
        handler.send_header('Content-Length', '0')
        handler.end_headers()


def make_handler(router: Router, mounts=(), server_version: str = 'Toolbox/1.0'):
    """把路由表与静态挂载点组装成 ``BaseHTTPRequestHandler`` 子类。"""
    mounts = list(mounts)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):        # noqa: A003 - 覆盖标准库同名钩子
            sys.stderr.write('[%s] %s\n' % (self.log_date_time_string(), fmt % args))

        def _dispatch(self):
            path = urlparse(self.path).path
            hit = router.resolve(self.command, path)
            if hit is not None:
                handler, params = hit
                request = Request(self, params)
                try:
                    handler(request)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as exc:          # noqa: BLE001 - 业务异常不该拖垮整个服务
                    sys.stderr.write('[error] %s %s -> %r\n' % (self.command, path, exc))
                    if not request.responded:
                        try:
                            request.send_error(500, str(exc))
                        except Exception:         # noqa: BLE001 - 连接已断则忽略
                            pass
                return
            for mount in mounts:
                target = mount.resolve(path)
                if target is not None:
                    Request(self, {}).send_file(target)
                    return
            Request(self, {}).send_error(404, 'Not Found')

        def do_GET(self):                          # noqa: N802 - 标准库要求的命名
            self._dispatch()

        def do_POST(self):                         # noqa: N802
            self._dispatch()

        def do_HEAD(self):                         # noqa: N802
            self._dispatch()

    Handler.server_version = server_version
    return Handler


def make_server(host: str, port: int, router: Router, mounts=(), server_version='Toolbox/1.0'):
    """创建（未启动的）多线程 HTTP 服务；端口占用会抛 ``OSError``。"""
    handler = make_handler(router, mounts, server_version)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def configure_console():
    """Windows 控制台默认 GBK；统一切到 UTF-8，避免打印装饰字符时崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (ValueError, OSError):
                pass


def port_error_hint(port: int, exc: Exception) -> str:
    """端口被占用时的友好提示（各入口共用，避免文案各写一份）。"""
    return (
        f'\n✗ 启动失败：端口 {port} 已被占用（{exc}）\n'
        f'  可能已有实例在运行。请先关闭旧实例，或换端口后重启：\n'
        f'    PowerShell : $env:PORT={port + 8}; python hub/server.py\n'
        f'    CMD        : set PORT={port + 8} && python hub/server.py\n'
        f'    Linux/macOS: PORT={port + 8} python3 hub/server.py\n'
    )


def serve_forever(server, url: str, banner=(), open_browser: bool = True,
                  before_serve=None, open_path: str = ''):
    """启动服务：打印横幅 → 可选打开浏览器 → 执行启动钩子 → 阻塞服务。

    ``before_serve`` 用于应用自己的启动逻辑（例如首次运行后台拉取数据），
    放在服务可响应之后执行，保证慢网络不会阻塞页面打开。

    设 ``TOOLBOX_NO_BROWSER=1`` 可禁止自动打开浏览器（服务器 / CI / 容器里有用）。
    """
    configure_console()
    print()
    for line in banner:
        print(line)
    print()

    if before_serve is not None:
        threading.Thread(target=before_serve, daemon=True).start()

    if open_browser and not os.environ.get('TOOLBOX_NO_BROWSER'):
        try:
            webbrowser.open(url + open_path)
        except Exception:                          # noqa: BLE001 - 无桌面环境时忽略
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止。')
    finally:
        server.server_close()
