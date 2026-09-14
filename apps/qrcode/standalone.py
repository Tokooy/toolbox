#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二维码批量生成 · 独立运行
============================

只启动这一个工具的网页（没有工具台的侧栏与其它功能），接口与工具台内完全一致：

    GET  /api/qrcode/status           输入目录与上次结果概要
    POST /api/qrcode/upload?filename= 上传 Excel
    POST /api/qrcode/run              提交生成任务
    GET  /api/qrcode/task/<id>        轮询任务日志与结果

只想跑一次批量生成、不需要网页时，用命令行入口 ``python apps/qrcode/cli.py``。

用法::

    python apps/qrcode/standalone.py
    PORT=9000 python apps/qrcode/standalone.py

默认端口 5001（可用 ``PORT`` 环境变量覆盖）。
"""

import sys
from pathlib import Path

# 让 `import core.*` 在「直接执行本文件」时也成立（仓库根 = 本文件的祖父目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import paths                              # noqa: E402

paths.bootstrap()

from core.standalone import serve_app               # noqa: E402

if __name__ == '__main__':
    serve_app('qrcode')
