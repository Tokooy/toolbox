#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务能力：数据目录、上传与结果扫描
=====================================

数据全部落在 ``<DATA_ROOT>/qrcode/``（与代码目录分离，方便打包 exe / 挂载数据卷）：

.. code-block:: text

    data/qrcode/
    ├── input/      # 待处理的 Excel（上传后旧文件自动移入 _旧文件备份_时间戳/）
    ├── output/     # 生成的 HTML / Excel
    └── qrcodes/    # 单张二维码 PNG 缓存

网页上看到的二维码预览，是把生成好的 HTML 里的 ``file://`` 图片地址改写成
``/api/qrcode/image/<文件名>`` 后得到的，因此预览与原 HTML 完全一致。
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

from core import paths

from . import generator

__all__ = ['LEGACY_DIR', 'data_root', 'dirs', 'ensure_dirs', 'input_files',
           'build_result', 'save_upload', 'safe_name', 'image_path', 'output_path',
           'MAX_UPLOAD']

# 旧版（重构前）本应用的数据目录：QRcode/{input,output,qrcodes}
LEGACY_DIR = 'QRcode'
MAX_UPLOAD = 50 * 1024 * 1024          # 上传大小上限 50MB
ALLOWED_SUFFIX = ('.xlsx', '.xls')

_SAFE_NAME_RE = re.compile(r'[^0-9A-Za-z._\-\u4e00-\u9fff（）()【】\[\] ]')

_PREVIEW_CSS = (
    '<style>'
    'body{margin:0;padding:18px;background:#f2f4f8;'
    'font-family:-apple-system,"Microsoft YaHei",sans-serif;}'
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

# 按容器宽度动态计算每行数量（侧栏收起/展开、窗口缩放时自动重排）
_PREVIEW_JS = (
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


# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------

def data_root() -> Path:
    return paths.app_data_dir('qrcode', legacy=LEGACY_DIR)


def dirs() -> generator.Dirs:
    return generator.resolve_dirs(data_root())


def ensure_dirs() -> generator.Dirs:
    resolved = dirs()
    for directory in (resolved.input, resolved.output, resolved.images):
        directory.mkdir(parents=True, exist_ok=True)
    return resolved


def safe_name(name: str) -> str:
    """保留中文与常见符号，去除路径分隔符等危险字符。"""
    return _SAFE_NAME_RE.sub('_', Path(name).name)


def image_path(name: str) -> Path | None:
    return _inside(dirs().images, name)


def output_path(name: str) -> Path | None:
    return _inside(dirs().output, name)


def _inside(directory: Path, name: str) -> Path | None:
    """把用户传入的文件名安全地解析到目录内（防目录穿越）。"""
    target = (directory / safe_name(name)).resolve()
    root = directory.resolve()
    return target if target.parent == root and target.is_file() else None


# --------------------------------------------------------------------------
# 输入目录
# --------------------------------------------------------------------------

def input_files() -> list[dict]:
    result = []
    for path in sorted(dirs().input.glob('*.xlsx')) + sorted(dirs().input.glob('*.xls')):
        stat = path.stat()
        result.append({
            'name': path.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
        })
    return result


def save_upload(filename: str, body: bytes) -> str:
    """保存上传的 Excel；目录里只保留这一份，旧文件移入备份子目录而不是删除。"""
    filename = safe_name(filename)
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIX:
        raise ValueError('仅支持 .xlsx / .xls 文件')
    if not body:
        raise ValueError('文件内容为空')
    if len(body) > MAX_UPLOAD:
        raise ValueError('文件超过 %dMB 限制' % (MAX_UPLOAD // 1024 // 1024))

    resolved = ensure_dirs()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for path in list(resolved.input.glob('*.xlsx')) + list(resolved.input.glob('*.xls')):
        if path.name == filename:
            continue
        backup = resolved.input / ('_旧文件备份_%s' % stamp)
        backup.mkdir(exist_ok=True)
        shutil.move(str(path), str(backup / path.name))

    (resolved.input / filename).write_bytes(body)
    return filename


# --------------------------------------------------------------------------
# 结果
# --------------------------------------------------------------------------

def _latest(pattern: str) -> Path | None:
    directory = dirs().output
    files = sorted(directory.glob(pattern)) if directory.is_dir() else []
    return files[-1] if files else None


def result_summary() -> dict:
    """轻量概要（不读取 HTML 内容）：前端轮询状态时用。"""
    html_path = _latest('*_qrcodes.html')
    xlsx_path = _latest('*_qrcodes.xlsx')
    return {
        'has_result': bool(html_path),
        'html_name': html_path.name if html_path else None,
        'xlsx_name': xlsx_path.name if xlsx_path else None,
    }


def build_result(prefix: str) -> dict:
    """最近一次生成的结果：可嵌入的预览 HTML + 输出文件列表 + 结构化条目。

    ``prefix`` 是本应用的接口前缀（如 ``/api/qrcode``），用于把预览里的图片地址
    改写成当前服务可访问的 URL——独立运行与工具台内运行因此共用同一份代码。
    """
    html_path = _latest('*_qrcodes.html')
    xlsx_path = _latest('*_qrcodes.xlsx')

    html = None
    if html_path is not None:
        html = html_path.read_text(encoding='utf-8')
        html = re.sub(r'src="file://[^"]*/([^/"]+)"', r'src="%s/image/\1"' % prefix, html)
        html = re.sub(r'<title>[^<]*</title>', '<title>批量二维码预览</title>', html)
        html = html.replace('</head>', _PREVIEW_CSS + '</head>')
        html = html.replace('</body>', _PREVIEW_JS + '</body>')
        # 每行数量已由脚本动态计算，去掉原「每行 N 个」的固定说明
        html = re.sub(r'，每行 \d+ 个', '', html)

    outputs = []
    for path in (html_path, xlsx_path):
        if path is not None:
            outputs.append({
                'name': path.name,
                'kind': 'html' if path.suffix == '.html' else 'xlsx',
                'url': '%s/download?file=%s' % (prefix, path.name),
            })

    items = []
    if html:
        pattern = re.compile(r'src="(%s/image/[^"]+)"[^>]*alt="([^"]*)"' % re.escape(prefix))
        items = [{'image': m.group(1), 'code': m.group(2)} for m in pattern.finditer(html)]

    return {
        'has_result': bool(html_path),
        'html': html,
        'outputs': outputs,
        'items': items,
        'count': len(items),
        'html_name': html_path.name if html_path else None,
        'xlsx_name': xlsx_path.name if xlsx_path else None,
    }
