# 二维码批量生成 · Bulk QR-Code Generator

根据 Excel 表格里的编号批量生成二维码，同时输出 **HTML 网页** 和 **Excel 文件**。
本目录是该工具的**完整实现**（前后端分离，可独立运行，也可被工具台 `hub` 托管）。

## 一、目录结构

```
apps/qrcode/
├── app.json              应用清单（工具台据此生成侧栏按钮与接口路由）
├── backend/              后端
│   ├── generator.py        纯生成逻辑：Excel → 二维码 PNG → HTML / Excel
│   ├── service.py          数据目录、上传、结果扫描（面向网页的能力）
│   └── api.py              HTTP 接口：/api/qrcode/*
├── frontend/             前端
│   ├── panel.js            网页面板（Vue 组件，工具台与独立站点共用）
│   └── panel.css           面板样式
├── cli.py                命令行入口（不启动网页）
└── standalone.py         独立运行入口（只跑这一个工具的网页）
```

## 二、三种使用方式

### 1. 工具台里点按钮（日常推荐）

```bash
python hub/server.py      # 打开 http://127.0.0.1:8080 → 左侧「二维码批量生成」
```

上传 Excel → 点「开始生成二维码」→ 页面里分组预览并下载 HTML / Excel。

### 2. 只启动这一个工具的网页

```bash
python apps/qrcode/standalone.py        # http://127.0.0.1:5001
PORT=9000 python apps/qrcode/standalone.py
```

接口路径与工具台内完全一致（`/api/qrcode/*`），页面里没有其它工具。

### 3. 命令行（不启动网页）

```bash
python apps/qrcode/cli.py                              # 处理 <数据根>/qrcode/input/ 下的 Excel
python apps/qrcode/cli.py --excel ~/Desktop/表格.xlsx   # 直接指定文件
python apps/qrcode/cli.py --data-root D:\qrcode-data    # 换数据根目录
```

## 三、数据目录

数据和代码分开存放，默认数据根是仓库下的 `data/`（可用环境变量 `TOOLBOX_DATA_ROOT` 覆盖）：

```
data/qrcode/
├── input/     放入待处理的 Excel（网页上传的文件也落在这里）
├── output/    生成的 HTML / Excel（文件名带当天日期前缀）
└── qrcodes/   单张二维码 PNG 缓存（编号.png）
```

**每次运行前会自动清理**上次生成的 HTML / Excel 与 PNG 缓存，所以输出目录里永远是本次结果；
上传新 Excel 时，`input/` 里旧的 Excel 会被移到 `input/_旧文件备份_时间戳/`，不会直接删除。

## 四、Excel 格式要求

- 表头里有列名为 **`二维码编号`** 的列（不要求必须是第一列）；
- 从第二行开始，每行一个编号；
- **支持自动筛选**：如果你在 Excel 里对该列做了筛选，程序只处理筛选后可见的行，
  隐藏行自动跳过；筛选做在别的列上时同样生效（多列筛选取交集）。

## 五、输出说明

| 文件 | 说明 |
| --- | --- |
| `output/YYYY-MM-DD_qrcodes.html` | 网页表格，每行 3 个二维码，下方标注编号 |
| `output/YYYY-MM-DD_qrcodes.xlsx` | 图片嵌入单元格，图片下方一行为编号 |
| `qrcodes/<编号>.png` | 单张二维码，300×300 像素，纠错等级 H（最高） |

二维码的编码内容就是编号文本本身。

## 六、依赖

```bash
pip install "qrcode[pil]" pillow openpyxl
```

只有本工具需要第三方库；工具台外壳与美债看板都是纯 Python 标准库。

## 七、常见问题

**Q：提示「input/ 目录下没有找到 Excel 文件」？**
A：把 Excel 放进数据目录的 `input/`（见上），或在网页上传，或命令行用 `--excel` 指定文件。

**Q：提示「未找到列名为「二维码编号」的列」？**
A：检查表头文字是否完全一致（不能有多余空格或换行）。

**Q：生成结果里少了若干行？**
A：多半是 Excel 里开了自动筛选，隐藏行被有意跳过 —— 取消筛选后重新生成即可。

**Q：网页上预览的二维码和下载的 HTML 不一致？**
A：两者同源：预览就是把生成的 HTML 里的图片地址改写成接口地址后的结果，内容完全一致。
