# 二维码批量生成器

根据 Excel 表格中的编号，批量生成二维码，同时输出 HTML 网页和 Excel 文件。

## 环境准备

需要 Python 3.8+，先安装依赖：

```bash
pip install qrcode[pil] Pillow openpyxl
```

## 使用方法

### 1. 放入 Excel 文件

把你的 Excel 文件（`.xlsx` 或 `.xls`）放到 `input/` 目录下。

**Excel 格式要求：**
- 第一行列名为 **`二维码编号`**
- 从第二行开始，每行一个编号

**支持自动筛选：** 如果你在 Excel 里对"二维码编号"列做了筛选（点了列头的下拉箭头勾选特定项），程序只会处理筛选后可见的行，隐藏的行自动跳过。如果筛选在其他列上，则全部行都会被处理。

### 2. 运行程序

进入项目目录后运行：

```bash
cd ~/Desktop/QRcode      # 换成你的项目实际路径
python generate_qrcodes.py
```

运行过程（程序自动完成，无需手动清理）：

1. **自动清理**上次生成的旧文件（`output/` 下的 HTML、Excel，以及 `qrcodes/` 里的二维码缓存）
2. 读取 `input/` 下的 Excel
3. 生成二维码 PNG（缓存到 `qrcodes/`）
4. 输出 HTML 页面和 Excel 文件（文件名带当天日期前缀）

### 3. 查看输出

| 文件 | 路径 | 说明 |
|------|------|------|
| HTML | `output/YYYY-MM-DD_qrcodes.html` | 浏览器打开，每行 3 个二维码 |
| Excel | `output/YYYY-MM-DD_qrcodes.xlsx` | 图片嵌入单元格，每行 3 个 |

例如 2025 年 6 月 1 日运行，会生成：
- `output/2025-06-01_qrcodes.html`
- `output/2025-06-01_qrcodes.xlsx`

`qrcodes/` 下的 PNG 缓存保持 `编号.png` 命名（不带日期前缀），每次运行前会被自动清空。

## 输出说明

- 二维码尺寸：300×300 像素
- 纠错等级：H（最高）
- 排列方式：每行 3 个，下方标注编号
- 二维码编码内容：编号文本本身

## 目录结构

```
~/Desktop/QRcode/
├── generate_qrcodes.py      # 主程序
├── README.md                # 本文件
├── input/                   # 放入 Excel 文件
├── output/                  # 生成结果（每次运行前程序自动清空旧文件）
│   ├── YYYY-MM-DD_qrcodes.html
│   └── YYYY-MM-DD_qrcodes.xlsx
└── qrcodes/                 # 单张二维码 PNG 缓存（每次运行前程序自动清空）
```

## 依赖

- `qrcode` — 生成二维码
- `Pillow` — 图片处理
- `openpyxl` — 读写 Excel
