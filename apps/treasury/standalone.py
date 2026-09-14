#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""美债收益率看板 · 独立运行
============================

只启动这一个工具的网页（没有工具台的侧栏与其它功能），接口与工具台内完全一致：

    GET  /api/treasury/data       读取本地缓存（不联网）
    POST /api/treasury/refresh    按需增量更新

用法::

    python apps/treasury/standalone.py
    PORT=9000 python apps/treasury/standalone.py

默认端口 5000（可用 ``PORT`` 环境变量覆盖；工具台 hub 默认 8080，因此两者可同时运行）。
"""

import sys
from pathlib import Path

# 让 `import core.*` 在「直接执行本文件」时也成立（仓库根 = 本文件的祖父目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import paths                              # noqa: E402

paths.bootstrap()

from core.standalone import serve_app               # noqa: E402

if __name__ == '__main__':
    serve_app('treasury')
