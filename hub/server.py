#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Toolbox 工具台 · 统一 Web 服务
================================
把两个独立功能整合进同一个网页（单页应用，点按钮切换，不跳转页面）：

  1. 美债收益率看板（us-treasury-yields）—— 纯标准库，动态加载原模块复用全部核心逻辑
  2. 二维码批量生成（QRcode）—— 用系统当前 Python（conda 环境 self_ag）运行原脚本，
     网页内实时显示运行日志并预览生成的二维码

设计要点：
  * 任务互斥：二维码生成与美债数据刷新共用一把全局锁，同一时刻只运行一个任务；
  * 按需运行：平时服务零开销，点哪个按钮才触发哪个功能；
  * 核心功能零改动：两个原始项目目录保持原样，这里只是调用与展示。

运行：python server.py  →  http://127.0.0.1:8080
"""

import importlib.util
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

# --------------------------------------------------------------------------
# 路径与常量
# --------------------------------------------------------------------------
HUB_DIR = Path(__file__).parent.resolve()
SELF_AG_DIR = HUB_DIR.parent
STATIC_DIR = HUB_DIR / 'static'
FEATURES_PATH = HUB_DIR / 'features.json'

QRCODE_DIR = SELF_AG_DIR / 'QRcode'
QR_SCRIPT = QRCODE_DIR / 'generate_qrcodes.py'
QR_INPUT_DIR = QRCODE_DIR / 'input'
QR_OUTPUT_DIR = QRCODE_DIR / 'output'
QR_IMG_DIR = QRCODE_DIR / 'qrcodes'

TREASURY_DIR = SELF_AG_DIR / 'us-treasury-yields'
TREASURY_SERVER = TREASURY_DIR / 'server.py'

PORT = int(os.environ.get('PORT', '8080'))

# --------------------------------------------------------------------------
# 加载美债模块（原 server.py 只定义数据逻辑与 HTTP Handler，main 不会执行）
# --------------------------------------------------------------------------
def _load_treasury():
    spec = importlib.util.spec_from_file_location('treasury_app', str(TREASURY_SERVER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

treasury = _load_treasury()

# --------------------------------------------------------------------------
# 全局任务互斥锁：二维码生成 / 美债刷新 共用，保证同一时刻只有一个任务运行
# --------------------------------------------------------------------------
_global_task_lock = threading.Lock()

# --------------------------------------------------------------------------
# 二维码任务管理（后台线程运行脚本，前端轮询实时日志）
# --------------------------------------------------------------------------
_tasks = {}
_tasks_lock = threading.Lock()
_task_seq = 0

_SAFE_NAME_RE = re.compile(r'[^0-9A-Za-z._\-\u4e00-\u9fff（）()【】\[\] ]')


def _safe_basename(name: str) -> str:
    """保留中文与常见符号，去除路径分隔符等危险字符"""
    return _SAFE_NAME_RE.sub('_', Path(name).name)


def new_task_id() -> str:
    """生成任务 ID。注意：必须在调用方持有 _tasks_lock 时调用（锁不可重入）。"""
    global _task_seq
    _task_seq += 1
    return f'task-{_task_seq}'


def create_qrcode_task():
    """创建一个二维码生成任务；若已有任务在运行则返回 None"""
    with _tasks_lock:
        if any(t['status'] == 'running' for t in _tasks.values()):
            return None
        task_id = new_task_id()
        task = {
            'id': task_id,
            'status': 'running',
            'log': [],
            'error': None,
            'result': None,
            'created_at': datetime.now().strftime('%H:%M:%S'),
        }
        _tasks[task_id] = task
    threading.Thread(target=_qrcode_worker, args=(task_id,), daemon=True).start()
    return task_id


def _qrcode_worker(task_id: str):
    task = _tasks[task_id]
    proc = None
    try:
        # 加全局锁运行，保证不与美债刷新并发
        with _global_task_lock:
            proc = subprocess.Popen(
                [sys.executable, str(QR_SCRIPT)],
                cwd=str(QRCODE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip('\n')
                task['log'].append(line)
            proc.wait()
        if proc.returncode == 0:
            task['result'] = get_qrcode_result()
            task['status'] = 'done'
        else:
            task['status'] = 'error'
            task['error'] = f'脚本退出码 {proc.returncode}'
    except Exception as exc:  # noqa: BLE001
        task['status'] = 'error'
        task['error'] = str(exc)
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def _latest_output(pattern: str):
    files = sorted(QR_OUTPUT_DIR.glob(pattern)) if QR_OUTPUT_DIR.exists() else []
    return files[-1] if files else None


def get_qrcode_result():
    """最近一次生成的结果：HTML 预览（file:// 图片转 HTTP）+ 输出文件列表"""
    html_path = _latest_output('*_qrcodes.html')
    xlsx_path = _latest_output('*_qrcodes.xlsx')

    html = None
    if html_path is not None:
        html = html_path.read_text(encoding='utf-8')
        # 把 file:/// 绝对路径的图片替换为可访问的 HTTP 路径
        html = re.sub(
            r'src="file://[^"]*/([^/"]+)"',
            r'src="/api/qrcode/image/\1"',
            html,
        )
        html = re.sub(
            r'<title>[^<]*</title>',
            '<title>批量二维码预览</title>',
            html,
        )
        # 注入自适应样式：每行二维码数量随窗口宽度动态变化（flex 自动换行）并整体居中
        adaptive_css = (
            '<style>'
            'body{margin:0;padding:18px;background:#f2f4f8;font-family:-apple-system,"Microsoft YaHei",sans-serif;}'
            'h1{text-align:center;font-size:18px;color:#1f2937;}'
            'p{text-align:center;color:#6b7280;}'
            'table{border-collapse:separate;display:block;}'
            'table,tbody{width:100%;}'
            'tr{display:flex;flex-wrap:wrap;justify-content:center;gap:14px;margin-bottom:14px;width:100%;}'
            'td{width:auto !important;height:auto !important;border:1px solid #e5e7eb !important;'
            'border-radius:12px;padding:12px !important;background:#fff;'
            'box-shadow:0 2px 8px rgba(0,0,0,.06);}'
            'img{display:block;margin:0 auto;}'
            '</style>'
        )
        html = html.replace('</head>', adaptive_css + '</head>')
        # 注入重排脚本：按容器宽度动态计算每行数量（侧栏收起/展开、窗口缩放时自动重排）
        relayout_js = (
            '<script>'
            '(function(){'
            'function relayout(){'
            'var table=document.querySelector("table");'
            'if(!table)return;'
            'var tds=Array.prototype.slice.call(table.querySelectorAll("td"));'
            'if(!tds.length)return;'
            'var w=table.getBoundingClientRect().width;'
            'var per=Math.max(1,Math.floor((w+14)/340));'
            'var frag=document.createDocumentFragment();'
            'for(var i=0;i<tds.length;i+=per){'
            'var tr=document.createElement("tr");'
            'tds.slice(i,i+per).forEach(function(td){tr.appendChild(td);});'
            'frag.appendChild(tr);'
            '}'
            'table.innerHTML="";'
            'table.appendChild(frag);'
            '}'
            'window.addEventListener("load",relayout);'
            'window.addEventListener("resize",relayout);'
            'relayout();'
            '})();'
            '</script>'
        )
        html = html.replace('</body>', relayout_js + '</body>')
        # 每行数量已动态化，去掉原「每行 N 个」的固定说明
        html = re.sub(r'，每行 \d+ 个', '', html)

    outputs = []
    for p in (html_path, xlsx_path):
        if p is not None:
            outputs.append({
                'name': p.name,
                'kind': 'html' if p.suffix == '.html' else 'xlsx',
                'url': f'/api/qrcode/download?file={p.name}',
            })

    return {
        'has_result': bool(html_path),
        'html': html,
        'outputs': outputs,
        'html_name': html_path.name if html_path else None,
        'xlsx_name': xlsx_path.name if xlsx_path else None,
    }


def get_qrcode_status():
    """input 目录状态 + 最近一次生成结果概要"""
    input_files = []
    if QR_INPUT_DIR.exists():
        for p in sorted(QR_INPUT_DIR.glob('*.xlsx')) + sorted(QR_INPUT_DIR.glob('*.xls')):
            input_files.append({
                'name': p.name,
                'size': p.stat().st_size,
                'modified': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
            })
    result = get_qrcode_result()
    return {
        'input_files': input_files,
        'has_result': result['has_result'],
        'html_name': result['html_name'],
        'xlsx_name': result['xlsx_name'],
        'running': any(t['status'] == 'running' for t in _tasks.values()),
    }


def save_uploaded_excel(filename: str, body: bytes):
    """保存上传的 Excel 到 input/ 根目录（保证目录下只有一份输入文件，旧文件移入备份子目录）"""
    filename = _safe_basename(filename)
    ext = Path(filename).suffix.lower()
    if ext not in ('.xlsx', '.xls'):
        raise ValueError('仅支持 .xlsx / .xls 文件')
    if not body:
        raise ValueError('文件内容为空')
    if len(body) > 50 * 1024 * 1024:
        raise ValueError('文件超过 50MB 限制')

    QR_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    # 把根目录下已有的其他 Excel 移入备份目录，保证 glob 只命中当前上传的这一份
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in list(QR_INPUT_DIR.glob('*.xlsx')) + list(QR_INPUT_DIR.glob('*.xls')):
        if p.name == filename:
            continue
        backup_dir = QR_INPUT_DIR / f'_旧文件备份_{stamp}'
        backup_dir.mkdir(exist_ok=True)
        shutil.move(str(p), str(backup_dir / p.name))

    target = QR_INPUT_DIR / filename
    target.write_bytes(body)
    return filename


# --------------------------------------------------------------------------
# HTTP 服务
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'ToolboxHub/1.0'

    def log_message(self, fmt, *args):
        sys.stderr.write('[%s] %s\n' % (datetime.now().strftime('%H:%M:%S'), fmt % args))

    # ---------- 基础响应 ----------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_error(self, status, message):
        self._send_json({'error': message}, status)

    def _send_bytes(self, body, ctype, status=200, extra_headers=None, filename=None):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if filename:
            self.send_header('Content-Disposition',
                             f"attachment; filename*=UTF-8''{quote(filename)}")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, path):
        rel = path[len('/static/'):]
        full = (STATIC_DIR / rel).resolve()
        if not str(full).startswith(str(STATIC_DIR)) or not full.is_file():
            self._send_error(404, 'Not Found')
            return
        body = full.read_bytes()
        ctype, _ = mimetypes.guess_type(str(full))
        self.send_response(200)
        self.send_header('Content-Type', ctype or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---------- 二维码接口 ----------
    def _api_qrcode_status(self):
        self._send_json(get_qrcode_status())

    def _api_qrcode_run(self):
        task_id = create_qrcode_task()
        if task_id is None:
            self._send_error(409, '已有任务正在运行，请稍候')
            return
        self._send_json({'task_id': task_id})

    def _api_qrcode_task(self, task_id):
        task = _tasks.get(task_id)
        if task is None:
            self._send_error(404, '任务不存在')
            return
        self._send_json({
            'id': task['id'],
            'status': task['status'],
            'log': task['log'],
            'error': task['error'],
            'result': task['result'],
            'created_at': task['created_at'],
        })

    def _api_qrcode_image(self, name):
        name = _safe_basename(name)
        img = (QR_IMG_DIR / name).resolve()
        if not str(img).startswith(str(QR_IMG_DIR.resolve())) or not img.is_file():
            self._send_error(404, 'Not Found')
            return
        self._send_bytes(img.read_bytes(), 'image/png',
                         extra_headers={'Cache-Control': 'no-cache'})

    def _api_qrcode_download(self, name):
        name = _safe_basename(name)
        f = (QR_OUTPUT_DIR / name).resolve()
        if not str(f).startswith(str(QR_OUTPUT_DIR.resolve())) or not f.is_file():
            self._send_error(404, 'Not Found')
            return
        ctype = ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                 if f.suffix == '.xlsx' else 'text/html; charset=utf-8')
        self._send_bytes(f.read_bytes(), ctype, filename=f.name)

    def _api_qrcode_upload(self):
        query = parse_qs(urlparse(self.path).query)
        filename = (query.get('filename') or ['未命名.xlsx'])[0]
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0:
            self._send_error(400, '空文件')
            return
        body = self.rfile.read(length)
        try:
            saved = save_uploaded_excel(filename, body)
        except ValueError as exc:
            self._send_error(400, str(exc))
            return
        self._send_json({'ok': True, 'filename': saved})

    # ---------- 美债接口 ----------
    def _api_treasury_data(self):
        try:
            self._send_json(treasury.load_data())
        except Exception as exc:  # noqa: BLE001
            self._send_error(500, f'读取数据失败: {exc}')

    def _api_treasury_refresh(self):
        try:
            # 与二维码生成共用全局锁：同一时刻只允许一个任务运行
            with _global_task_lock:
                meta = treasury.refresh_data()
                payload = treasury.load_data()
            payload['refreshed'] = True
            payload['refresh_meta'] = meta
            self._send_json(payload)
        except Exception as exc:  # noqa: BLE001
            self._send_error(502, f'从 FRED 获取数据失败: {exc}')

    # ---------- 路由 ----------
    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/':
            self._serve_static('/static/index.html')
        elif path == '/api/apps':
            self._send_json(json.loads(FEATURES_PATH.read_text(encoding='utf-8')))
        elif path == '/api/health':
            self._send_json({'ok': True, 'ts': datetime.now().isoformat()})
        elif path == '/api/qrcode/status':
            self._api_qrcode_status()
        elif path.startswith('/api/qrcode/task/'):
            self._api_qrcode_task(path.rsplit('/', 1)[-1])
        elif path.startswith('/api/qrcode/image/'):
            self._api_qrcode_image(path.rsplit('/', 1)[-1])
        elif path.startswith('/api/qrcode/download'):
            name = (parse_qs(urlparse(self.path).query).get('file') or [''])[0]
            self._api_qrcode_download(name)
        elif path == '/api/qrcode/result':
            self._send_json(get_qrcode_result())
        elif path == '/api/treasury/data':
            self._api_treasury_data()
        elif path.startswith('/static/'):
            self._serve_static(path)
        else:
            self._send_error(404, 'Not Found')

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/api/qrcode/run':
            self._api_qrcode_run()
        elif path == '/api/qrcode/upload':
            self._api_qrcode_upload()
        elif path == '/api/treasury/refresh':
            self._api_treasury_refresh()
        else:
            self._send_error(404, 'Not Found')


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def main():
    for d in (QR_INPUT_DIR, QR_OUTPUT_DIR, QR_IMG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as exc:
        print(f'\n✗ 启动失败：端口 {PORT} 已被占用（{exc}）')
        print('  可能已有实例在运行。请先关闭旧实例，或换端口启动：')
        print(f'    PORT={PORT + 100} python server.py')
        sys.exit(1)

    url = f'http://127.0.0.1:{PORT}'
    print()
    print('  ═══════════════════════════════════════════════')
    print('   Toolbox 工具台 已启动')
    print(f'    ➜ {url}')
    print('   ⚡ 点哪个按钮运行哪个功能，同一时刻只运行一个任务')
    print('   ⏹ 按 Ctrl+C 停止服务')
    print('  ═══════════════════════════════════════════════')
    print()
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止。')


if __name__ == '__main__':
    main()
