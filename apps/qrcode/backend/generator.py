#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二维码批量生成 —— 纯生成逻辑
================================

输入：Excel 文件的 ``二维码编号`` 列（若该表设置了自动筛选，只处理筛选后可见的行）
输出：

* ``<data_root>/qrcodes/<编号>.png``        单张二维码（300×300，纠错等级 H）
* ``<data_root>/output/YYYY-MM-DD_qrcodes.html``   网页表格（每行 3 个）
* ``<data_root>/output/YYYY-MM-DD_qrcodes.xlsx``   Excel 表格（图片嵌入单元格）

每次运行前自动清理上次生成的旧文件，因此输出目录永远只有本次结果。

本模块不依赖任何 Web 框架，命令行（``cli.py``）与网页接口（``api.py``）共用同一份逻辑。
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import qrcode
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter, range_boundaries
from PIL import Image

__all__ = ['Dirs', 'GeneratorError', 'resolve_dirs', 'run', 'clean_outputs',
           'find_input_excel', 'read_codes', 'generate_images', 'write_html', 'write_excel',
           'QR_SIZE', 'PER_ROW']

QR_SIZE = 300          # 二维码图片像素尺寸（正方形）
PER_ROW = 3            # 每行二维码数量
HTML_CELL_W = 320      # HTML 单元格宽度 px
HTML_CELL_H = 380      # HTML 单元格高度 px（含下方编号标签）
HEADER = '二维码编号'   # Excel 中约定的编号列名


class GeneratorError(Exception):
    """业务错误（输入文件缺失、列名不对、没有有效编号等），消息直接展示给用户。"""


class Dirs(NamedTuple):
    """一次运行用到的三个数据目录（与代码目录分离，便于打包与挂载数据卷）。"""

    root: Path
    input: Path
    output: Path
    images: Path


def resolve_dirs(data_root) -> Dirs:
    """由数据根目录推导 input / output / qrcodes 三个子目录。"""
    root = Path(data_root).resolve()
    return Dirs(root=root, input=root / 'input', output=root / 'output',
                images=root / 'qrcodes')


# --------------------------------------------------------------------------
# 各步骤
# --------------------------------------------------------------------------

def clean_outputs(dirs: Dirs, log=print) -> int:
    """运行前清理：删除上次生成的 HTML / Excel 输出与二维码 PNG 缓存。"""
    removed = 0
    for path in dirs.images.glob('*.png'):
        path.unlink()
        removed += 1
    for pattern in ('*.html', '*.xlsx'):
        for path in dirs.output.glob(pattern):
            path.unlink()
            removed += 1
    if removed:
        log('  已清理 %d 个旧文件（html / excel / 二维码缓存）' % removed)
    else:
        log('  没有需要清理的旧文件')
    return removed


def find_input_excel(dirs: Dirs) -> Path:
    """在 ``input/`` 下找到待处理的 Excel（约定目录里只保留一份）。"""
    files = sorted(dirs.input.glob('*.xlsx')) + sorted(dirs.input.glob('*.xls'))
    if not files:
        raise GeneratorError('input/ 目录下没有找到 Excel 文件（.xlsx / .xls），'
                             '请先上传：%s' % dirs.input)
    return files[0]


def read_codes(excel_path: Path, log=print) -> list[str]:
    """读取 ``二维码编号`` 列的所有编号（只读自动筛选后可见的行）。"""
    workbook = load_workbook(excel_path, data_only=True)
    sheet = workbook.active

    header_col = None
    for col_idx in range(1, sheet.max_column + 1):
        value = sheet.cell(row=1, column=col_idx).value
        if value and str(value).strip() == HEADER:
            header_col = col_idx
            break
    if header_col is None:
        raise GeneratorError('未找到列名为「%s」的列，请检查 Excel 表头' % HEADER)

    col_filters = _auto_filters(sheet)
    if col_filters:
        log('  检测到自动筛选：' + '; '.join(
            '列%d(%d个值)' % (col, len(vals)) for col, vals in col_filters.items()))

    codes = []
    hidden = 0
    for row_idx in range(2, sheet.max_row + 1):
        if col_filters and not _row_visible(sheet, row_idx, col_filters):
            hidden += 1
            continue
        value = sheet.cell(row=row_idx, column=header_col).value
        if value is not None:
            code = str(value).strip()
            if code:
                codes.append(code)

    if not codes:
        raise GeneratorError('没有找到任何有效编号（%s 列从第二行起为空？）' % HEADER)

    message = '读取到 %d 个编号' % len(codes)
    if col_filters:
        message += '（已应用自动筛选，隐藏 %d 行）' % hidden
    log(message)
    return codes


def _auto_filters(sheet) -> dict[int, set[str]]:
    """解析自动筛选规则，返回 ``{实际列号(1 起): 可见值集合}``。"""
    filters: dict[int, set[str]] = {}
    auto_filter = sheet.auto_filter
    if not (auto_filter and auto_filter.ref and auto_filter.filterColumn):
        return filters
    min_col = range_boundaries(auto_filter.ref)[0]
    for column in auto_filter.filterColumn:
        if column.filters and column.filters.filter:
            filters[min_col + column.colId] = {str(v) for v in column.filters.filter}
    return filters


def _row_visible(sheet, row_idx: int, col_filters: dict[int, set[str]]) -> bool:
    """该行是否在所有筛选列上都命中可见值。"""
    for filter_col, visible in col_filters.items():
        value = sheet.cell(row=row_idx, column=filter_col).value
        text = str(value).strip() if value is not None else ''
        if text not in visible:
            return False
    return True


def image_name(code: str) -> str:
    """编号 → 安全的 PNG 文件名。"""
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in code) + '.png'


def generate_images(codes: list[str], dirs: Dirs) -> dict[str, Path]:
    """为每个编号生成二维码 PNG，返回 ``{编号: 图片路径}``。"""
    dirs.images.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=10, border=2)
    for code in codes:
        qr.clear()
        qr.add_data(code)
        qr.make(fit=True)
        image = qr.make_image(fill_color='black', back_color='white').convert('RGB')
        image = image.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
        out_path = dirs.images / image_name(code)
        image.save(out_path, 'PNG')
        result[code] = out_path
    return result


def write_html(codes: list[str], qr_map: dict[str, Path], output_path: Path,
               per_row: int = PER_ROW) -> None:
    """生成 HTML 表格页面（每行 ``per_row`` 个二维码）。"""
    rows_html = []
    for start in range(0, len(codes), per_row):
        cells = []
        for code in codes[start:start + per_row]:
            # 用标准 file URI（file:///…，正斜杠跨平台）引用图片，浏览器可直接打开
            cells.append(
                '        <td style="width:%dpx; height:%dpx; text-align:center; '
                'vertical-align:bottom; border:1px solid #ddd; padding:10px;">\n'
                '          <img src="%s" width="%d" height="%d" alt="%s" '
                'style="display:block; margin:0 auto;">\n'
                '          <div style="margin-top:6px; font-size:13px; '
                'font-family:monospace; word-break:break-all;">%s</div>\n'
                '        </td>'
                % (HTML_CELL_W, HTML_CELL_H, qr_map[code].as_uri(), QR_SIZE, QR_SIZE,
                   _escape(code), _escape(code)))
        rows_html.append('      <tr>\n' + '\n'.join(cells) + '\n      </tr>')

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>二维码列表</title>
<style>
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; padding: 20px; background: #f5f5f5; }
h1 { font-size: 20px; margin-bottom: 16px; }
table { border-collapse: collapse; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
td { border: 1px solid #ddd; }
</style>
</head>
<body>
<h1>批量二维码</h1>
<p>共 %d 个编号，每行 %d 个</p>
<table>
%s
</table>
</body>
</html>""" % (len(codes), per_row, '\n'.join(rows_html))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')


def _escape(text: str) -> str:
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def write_excel(codes: list[str], qr_map: dict[str, Path], output_path: Path,
                per_row: int = PER_ROW) -> None:
    """生成 Excel 文件：图片嵌入单元格，图片下方一行为编号。"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = '二维码列表'

    for col in range(1, per_row * 2 + 1):
        sheet.column_dimensions[get_column_letter(col)].width = 18

    for index, code in enumerate(codes):
        col_idx = (index % per_row) * 2 + 1     # 每列图片
        row_idx = (index // per_row) * 2 + 1    # 每两行一组（图片 + 编号）

        image = XlImage(str(qr_map[code]))
        image.width = 120
        image.height = 120
        sheet.add_image(image, '%s%d' % (get_column_letter(col_idx), row_idx))
        sheet.row_dimensions[row_idx].height = 90

        label = sheet.cell(row=row_idx + 1, column=col_idx)
        label.value = code
        label.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)
        sheet.row_dimensions[row_idx + 1].height = 30

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(str(output_path))


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def run(data_root=None, log=print, excel_path=None) -> dict:
    """按指定数据根执行一次完整生成流程。

    ``data_root`` 决定 input / output / qrcodes 三个目录的位置，默认取本文件的上一级
    目录（即 ``apps/qrcode/``，与命令行独立运行一致）；被工具台调用时传入
    ``<数据根>/qrcode``，与代码目录分离。

    ``excel_path`` 指定时直接读取该文件，不再扫描 ``input/`` 目录（命令行 ``--excel`` 用）。

    返回本次运行的结果摘要；业务错误抛 :class:`GeneratorError`。
    """
    dirs = resolve_dirs(data_root if data_root is not None else Path(__file__).resolve().parents[1])
    date_tag = datetime.now().strftime('%Y-%m-%d')

    log('=' * 50)
    log('  二维码批量生成器')
    log('=' * 50)

    log('\n[1/5] 清理上次运行的旧文件...')
    clean_outputs(dirs, log=log)

    if excel_path is not None:
        excel_path = Path(excel_path).resolve()
        if not excel_path.is_file():
            raise GeneratorError('指定的 Excel 不存在：%s' % excel_path)
    else:
        excel_path = find_input_excel(dirs)
    log('\n[2/5] 读取输入文件: %s' % excel_path.name)

    codes = read_codes(excel_path, log=log)

    log('[3/5] 生成二维码图片...')
    qr_map = generate_images(codes, dirs)
    log('      已生成 %d 个二维码 -> %s' % (len(qr_map), dirs.images))

    html_path = dirs.output / ('%s_qrcodes.html' % date_tag)
    xlsx_path = dirs.output / ('%s_qrcodes.xlsx' % date_tag)

    log('[4/5] 生成 HTML 页面...')
    write_html(codes, qr_map, html_path)
    log('      HTML 已生成: %s' % html_path)

    log('[5/5] 生成 Excel 文件...')
    write_excel(codes, qr_map, xlsx_path)
    log('      Excel 已生成: %s' % xlsx_path)

    log('\n' + '=' * 50)
    log('  全部完成！')
    log('  HTML:  %s' % html_path)
    log('  Excel: %s' % xlsx_path)
    log('  二维码缓存: %s' % dirs.images)
    log('  Excel 输入目录: %s' % dirs.input)
    log('=' * 50)

    return {'count': len(codes), 'html': str(html_path), 'xlsx': str(xlsx_path),
            'images': str(dirs.images)}


def main(argv=None) -> int:      # 兼容旧版直接执行本模块的用法
    try:
        run(log=print)
    except GeneratorError as exc:
        print('错误: %s' % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
