#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二维码批量生成 · 命令行入口
==============================

不启动网页，直接在终端里跑一次批量生成（等价于重构前的 ``python generate_qrcodes.py``）：

.. code-block:: bash

    # 处理 <数据根>/qrcode/input/ 下的 Excel（默认数据根 = <仓库根>/data）
    python apps/qrcode/cli.py

    # 直接指定要处理的 Excel（仍输出到默认的 output/ 与 qrcodes/）
    python apps/qrcode/cli.py --excel ~/Desktop/表格.xlsx

    # 换一个数据根目录（数据与代码分离，便于打包/迁移）
    python apps/qrcode/cli.py --data-root D:\\qrcode-data

数据目录布局：``<数据根>/input``、``<数据根>/output``、``<数据根>/qrcodes``。
"""

import argparse
import sys
from pathlib import Path

# 让 `import core.* / apps.*` 在「直接执行本文件」时也成立（仓库根 = 本文件的祖父目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import paths                                  # noqa: E402

paths.bootstrap()

from apps.qrcode.backend import generator, service       # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog='qrcode-cli',
        description='二维码批量生成器：读取 Excel「二维码编号」列，输出 HTML / Excel',
    )
    parser.add_argument('-d', '--data-root', default=None,
                        help='数据根目录（默认 %s）' % service.data_root())
    parser.add_argument('-e', '--excel', default=None,
                        help='直接指定 Excel 文件（默认读取 <数据根>/input/ 下的第一个）')
    args = parser.parse_args(argv)

    data_root = Path(args.data_root).resolve() if args.data_root else service.data_root()
    try:
        generator.run(data_root, log=print, excel_path=args.excel)
    except generator.GeneratorError as exc:
        print('\n错误: %s' % exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\n已中断。', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
