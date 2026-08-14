#!/usr/bin/env python3
"""
二维码批量生成器
读取 input/ 目录下的 Excel 文件（第一列列名为"二维码编号"），
为每个编号生成二维码，输出到：
  - output/YYYY-MM-DD_qrcodes.html  (网页表格)
  - output/YYYY-MM-DD_qrcodes.xlsx  (Excel表格)
每次运行前自动清理上次生成的旧文件（html / xlsx / 二维码缓存）。
"""

import os
import sys
import glob
from datetime import datetime
from pathlib import Path

import qrcode
from PIL import Image
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.utils import get_column_letter

# ── 路径 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QR_DIR = BASE_DIR / "qrcodes"

QR_SIZE = 300          # 二维码图片像素尺寸（正方形）
PER_ROW = 3            # 每行二维码数量
HTML_CELL_W = 320      # html 单元格宽度 px
HTML_CELL_H = 380      # html 单元格高度 px (包含下方标签)


def clean_outputs() -> int:
    """运行前清理：删除上次生成的 HTML / Excel 输出与二维码 PNG 缓存"""
    removed = 0
    for f in QR_DIR.glob("*.png"):
        f.unlink()
        removed += 1
    for pattern in ("*.html", "*.xlsx"):
        for f in OUTPUT_DIR.glob(pattern):
            f.unlink()
            removed += 1
    if removed:
        print(f"  已清理 {removed} 个旧文件（html / excel / 二维码缓存）")
    else:
        print("  没有需要清理的旧文件")
    return removed

# ── 辅助函数 ──────────────────────────────────────────

def find_input_excel() -> Path:
    """在 input/ 目录下找第一个 .xlsx 文件"""
    files = list(INPUT_DIR.glob("*.xlsx")) + list(INPUT_DIR.glob("*.xls"))
    if not files:
        print("错误: input/ 目录下没有找到 Excel 文件 (.xlsx / .xls)")
        print(f"请把你需要处理的 Excel 放到: {INPUT_DIR}")
        sys.exit(1)
    return files[0]


def read_qr_codes(excel_path: Path) -> list[str]:
    """读取 Excel 第一列 '二维码编号' 下的所有行（只读筛选后可见的行）"""
    import openpyxl
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active

    # 找第一列表头
    header_col = None
    for col_idx in range(1, ws.max_column + 1):
        val = ws.cell(row=1, column=col_idx).value
        if val and str(val).strip() == "二维码编号":
            header_col = col_idx
            break

    if header_col is None:
        print("错误: 未找到列名为 '二维码编号' 的列")
        print("请确保 Excel 第一列列名为 '二维码编号'")
        sys.exit(1)

    # ── 解析自动筛选规则 ──────────────────────────────
    # 构建 {实际列号(1-indexed): 可见值的集合}
    from openpyxl.utils import range_boundaries

    col_filters: dict[int, set[str]] = {}
    af = ws.auto_filter

    if af and af.ref and af.filterColumn:
        min_col, _, _, _ = range_boundaries(af.ref)
        for fc in af.filterColumn:
            actual_col = min_col + fc.colId
            if fc.filters and fc.filters.filter:
                visible_vals = set(str(v) for v in fc.filters.filter)
                col_filters[actual_col] = visible_vals

        if col_filters:
            filter_desc = "; ".join(
                f"列{col}({len(vals)}个值)" for col, vals in col_filters.items()
            )
            print(f"  检测到自动筛选：{filter_desc}")

    # ── 逐行判断可见性 ──────────────────────────────
    codes = []
    hidden_count = 0

    for row_idx in range(2, ws.max_row + 1):
        # 如果存在筛选，检查该行是否在所有筛选列上都可见
        if col_filters:
            row_visible = True
            for filter_col, visible_vals in col_filters.items():
                cell_val = ws.cell(row=row_idx, column=filter_col).value
                cell_str = str(cell_val).strip() if cell_val is not None else ""
                if cell_str not in visible_vals:
                    row_visible = False
                    break
            if not row_visible:
                hidden_count += 1
                continue

        # 该行可见，取二维码编号
        val = ws.cell(row=row_idx, column=header_col).value
        if val is not None:
            code = str(val).strip()
            if code:
                codes.append(code)

    if not codes:
        print("错误: 没有找到任何有效编号")
        sys.exit(1)

    msg = f"读取到 {len(codes)} 个编号"
    if col_filters:
        msg += f"（已应用自动筛选，隐藏 {hidden_count} 行）"
    print(msg)
    return codes


def generate_qr_images(codes: list[str]) -> dict[str, Path]:
    """为每个编号生成二维码 PNG 图片，返回 {编号: 图片路径}"""
    QR_DIR.mkdir(parents=True, exist_ok=True)

    result = {}
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )

    for code in codes:
        qr.clear()
        qr.add_data(code)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in code)
        out_path = QR_DIR / f"{safe_name}.png"
        img.save(out_path, "PNG")
        result[code] = out_path

    return result


def generate_html(codes: list[str], qr_map: dict[str, Path], output_path: Path):
    """生成 HTML 表格页面，每行 5 个二维码"""
    rows_html = []
    for i in range(0, len(codes), PER_ROW):
        chunk = codes[i : i + PER_ROW]
        cells = []
        for code in chunk:
            img_path = qr_map[code]
            # HTML 中使用相对路径或 base64 嵌入？用 data URI 更好——自包含
            cells.append(f"""\
        <td style="width:{HTML_CELL_W}px; height:{HTML_CELL_H}px; text-align:center; vertical-align:bottom; border:1px solid #ddd; padding:10px;">
          <img src="file:///{img_path}" width="{QR_SIZE}" height="{QR_SIZE}" alt="{code}" style="display:block; margin:0 auto;">
          <div style="margin-top:6px; font-size:13px; font-family:monospace; word-break:break-all;">{code}</div>
        </td>""")
        rows_html.append("      <tr>\n" + "\n".join(cells) + "\n      </tr>")

    html = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>二维码列表</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; padding: 20px; background: #f5f5f5; }}
h1 {{ font-size: 20px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
td {{ border: 1px solid #ddd; }}
</style>
</head>
<body>
<h1>批量二维码</h1>
<p>共 {len(codes)} 个编号，每行 {PER_ROW} 个</p>
<table>
{''.join(rows_html)}
</table>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"HTML 已生成: {output_path}")


def generate_excel(codes: list[str], qr_map: dict[str, Path], output_path: Path):
    """生成 Excel 文件，每行 5 个二维码图片"""
    wb = Workbook()
    ws = wb.active
    ws.title = "二维码列表"

    # 列宽
    col_width = 18
    for c in range(1, PER_ROW * 2 + 1):
        ws.column_dimensions[get_column_letter(c)].width = col_width

    # 行高
    row_height = 90

    for i, code in enumerate(codes):
        col_idx = (i % PER_ROW) * 2 + 1   # 每列图片
        row_idx = (i // PER_ROW) * 2 + 1  # 每两行一组(图片+标签)

        # 插入图片
        img_path = qr_map[code]
        img = XlImage(str(img_path))
        img.width = 120
        img.height = 120
        cell_ref = f"{get_column_letter(col_idx)}{row_idx}"
        ws.add_image(img, cell_ref)
        ws.row_dimensions[row_idx].height = row_height

        # 在图片下方写编号
        label_row = row_idx + 1
        label_cell = ws.cell(row=label_row, column=col_idx)
        label_cell.value = code
        label_cell.alignment = __import__('openpyxl').styles.Alignment(
            horizontal='center', vertical='top', wrap_text=True
        )
        ws.row_dimensions[label_row].height = 30

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    print(f"Excel 已生成: {output_path}")


# ── 主流程 ──────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  二维码批量生成器")
    print("=" * 50)

    date_tag = datetime.now().strftime("%Y-%m-%d")

    # 1. 清理上次运行生成的旧文件（html / excel / 二维码缓存）
    print("\n[1/5] 清理上次运行的旧文件...")
    clean_outputs()

    # 2. 找输入文件
    excel_path = find_input_excel()
    print(f"\n[2/5] 读取输入文件: {excel_path.name}")

    # 3. 读取编号
    codes = read_qr_codes(excel_path)

    # 4. 生成二维码图片
    print("[3/5] 生成二维码图片...")
    qr_map = generate_qr_images(codes)
    print(f"      已生成 {len(qr_map)} 个二维码 -> {QR_DIR}")

    # 5. 输出 HTML / Excel
    html_path = OUTPUT_DIR / f"{date_tag}_qrcodes.html"
    xlsx_path = OUTPUT_DIR / f"{date_tag}_qrcodes.xlsx"

    print("[4/5] 生成 HTML 页面...")
    generate_html(codes, qr_map, html_path)

    print("[5/5] 生成 Excel 文件...")
    generate_excel(codes, qr_map, xlsx_path)

    print("\n" + "=" * 50)
    print("  全部完成！")
    print(f"  HTML:  {html_path}")
    print(f"  Excel: {xlsx_path}")
    print(f"  二维码缓存: {QR_DIR}/")
    print(f"  Excel 输入目录: {INPUT_DIR}/")
    print("=" * 50)


if __name__ == "__main__":
    main()
