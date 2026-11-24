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

下载的 HTML 内嵌二维码图片，网页预览通过 ``/api/qrcode/image/<文件名>`` 加载相同图片。
"""

import re
import shutil
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import unquote

from core import paths

from . import generator

__all__ = ['LEGACY_DIR', 'data_root', 'dirs', 'ensure_dirs', 'input_files',
           'build_result', 'html_download', 'save_upload', 'safe_name', 'image_path',
           'output_path', 'MAX_UPLOAD']

# 旧版（重构前）本应用的数据目录：QRcode/{input,output,qrcodes}
LEGACY_DIR = 'QRcode'
MAX_UPLOAD = 50 * 1024 * 1024          # 上传大小上限 50MB
ALLOWED_SUFFIX = ('.xlsx', '.xls')

_SAFE_NAME_RE = re.compile(r'[^0-9A-Za-z._\-\u4e00-\u9fff（）()【】\[\] ]')

# 兼容以绝对文件 URL 引用 PNG 的旧版导出。
_RESULT_IMAGE_RE = re.compile(
    r'<img src="(?:file://[^"]*/(?P<legacy>[^/"]+)|'
    r'data:image/png;base64,[^"]+" data-filename="(?P<filename>[^"]+))"'
    r'[^>]* alt="(?P<code>[^"]*)"'
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
    # 生成的文件名可含任意 Unicode 字母和数字。
    if generator.image_name(Path(name).stem) != name:
        return None
    return _inside(dirs().images, name)


def output_path(name: str) -> Path | None:
    return _inside(dirs().output, safe_name(name))


def _inside(directory: Path, name: str) -> Path | None:
    """把已校验的文件名安全地解析到目录内（防目录穿越）。"""
    target = (directory / name).resolve()
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


def _result_images(html: str) -> list[tuple[str, str]]:
    return [
        (unescape(match['code']), match['filename'] or match['legacy'])
        for match in _RESULT_IMAGE_RE.finditer(html)
    ]


def html_download(path: Path) -> bytes:
    """直接返回新导出，或者用缓存图片将旧导出转换为离线 HTML。"""
    content = path.read_bytes()
    if b'<img src="file://' not in content:
        return content

    html = content.decode('utf-8')
    codes = []
    qr_map = {}
    for code, filename in _result_images(html):
        image = image_path(unquote(filename))
        if image is None:
            return content
        codes.append(code)
        qr_map[code] = image
    if not codes:
        return content

    columns = re.search(r'，每行 (\d+) 个', html)
    per_row = int(columns[1]) if columns else generator.PER_ROW
    try:
        return generator.export_html(codes, qr_map, per_row).encode('utf-8')
    except FileNotFoundError:  # 生成新结果时可能正在清理旧缓存
        return content


def build_result(prefix: str) -> dict:
    """最近一次生成的预览 HTML、下载链接和二维码条目。"""
    html_path = _latest('*_qrcodes.html')
    xlsx_path = _latest('*_qrcodes.xlsx')

    html = None
    items = []
    if html_path is not None:
        images = _result_images(html_path.read_text(encoding='utf-8'))
        items = [{'image': f'{prefix}/image/{name}', 'code': code} for code, name in images]
        html = generator.render_html(
            [generator.HtmlImage(item['code'], item['image']) for item in items],
            per_row=None,
            title='批量二维码预览',
        )

    outputs = []
    for path in (html_path, xlsx_path):
        if path is not None:
            outputs.append({
                'name': path.name,
                'kind': 'html' if path.suffix == '.html' else 'xlsx',
                'url': '%s/download?file=%s' % (prefix, path.name),
            })

    return {
        'has_result': bool(html_path),
        'html': html,
        'outputs': outputs,
        'items': items,
        'count': len(items),
        'html_name': html_path.name if html_path else None,
        'xlsx_name': xlsx_path.name if xlsx_path else None,
    }
