#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 FRED 原始 CSV 存档重建本地缓存（不联网）
===============================================

.. code-block:: bash

    python apps/treasury/seed_data.py

读取 ``<数据根>/treasury/raw/DGS{2,10,30}.csv``（随仓库提交的 FRED 原始下载文件，
可用于逐行核对），合并成 ``<数据根>/treasury/treasury_yields.csv`` 与 ``meta.json``。

正常情况下**不需要手动运行** —— 服务首次启动会自动联网获取并生成同样格式的缓存；
只有在你想用 ``raw/`` 里的原始快照重建缓存（例如迁移到新机器、或确认数据未失真）时才用它。
"""

import csv
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

# 让 `import core.* / apps.*` 在「直接执行本文件」时也成立（仓库根 = 本文件的祖父目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import paths                                  # noqa: E402

paths.bootstrap()

from apps.treasury.backend import fred, store            # noqa: E402


def parse_raw(path: Path) -> list[tuple[str, float | None]]:
    """解析 FRED 原始 CSV（容错：跳过 URL 首行 / 空行 / 表头 / 缺失值）。"""
    rows = []
    with open(path, encoding='utf-8-sig') as handle:
        for line in csv.reader(io.StringIO(handle.read())):
            if len(line) < 2:
                continue
            date = line[0].strip()
            raw = line[1].strip()
            # 跳过表头行与非日期行（例如首行的来源 URL）
            if len(date) != 10 or date[4] != '-' or date[7] != '-':
                continue
            rows.append((date, None if raw in ('', '.') else float(raw)))
    return rows


def main() -> int:
    raw_dir = store.raw_dir()
    merged: dict[str, dict[str, float | None]] = {}
    for sid in sorted(fred.SERIES):
        path = raw_dir / ('%s.csv' % sid)
        if not path.is_file():
            print('✗ 缺少原始文件：%s' % path, file=sys.stderr)
            return 1
        for date, value in parse_raw(path):
            merged.setdefault(date, {})[sid] = value

    dates = sorted(merged)
    if not dates:
        print('✗ 原始文件里没有解析到任何数据', file=sys.stderr)
        return 1

    meta = {
        'source': 'FRED (Federal Reserve Bank of St. Louis)',
        'series': sorted(fred.SERIES),
        'start_date': fred.START_DATE,
        'last_date': dates[-1],
        'rows': len(dates),
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    store.write_cache(dates, merged, meta)

    print('✓ 已合并 %d 个交易日（%s ~ %s）' % (len(dates), dates[0], dates[-1]))
    print('  输出：%s' % store.csv_path())
    print('        %s' % store.meta_path())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
