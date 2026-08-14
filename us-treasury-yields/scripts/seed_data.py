#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_data.py — 从 data/raw/ 下的 FRED 原始 CSV 合并生成本地缓存数据
=================================================================
用法：python seed_data.py

该脚本只做「原始文件 → 合并缓存」的本地转换，不访问网络：
  data/raw/DGS2.csv + DGS10.csv + DGS30.csv  →  data/treasury_yields.csv + meta.json

正常情况下不需要手动运行 —— server.py 首次启动会自动联网获取并生成相同格式的缓存。
当你希望用 data/raw/ 里的原始快照重建缓存时再运行它。
"""

import csv
import io
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'treasury_yields.csv')
META_PATH = os.path.join(DATA_DIR, 'meta.json')

SERIES = {'DGS2', 'DGS10', 'DGS30'}
START_DATE = '2020-01-01'


def parse_raw(path):
    """解析 FRED 原始 CSV（容错：跳过 URL 首行 / 空行 / 表头 / 缺失值）。"""
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        for line in csv.reader(io.StringIO(f.read())):
            if len(line) < 2:
                continue
            date = line[0].strip()
            raw = line[1].strip()
            # 跳过表头行与非日期行（如 URL）
            if not date or not (len(date) == 10 and date[4] == '-' and date[7] == '-'):
                continue
            value = None if raw in ('', '.') else float(raw)
            rows.append((date, value))
    return rows


def main():
    merged = {}
    for sid in sorted(SERIES):
        path = os.path.join(RAW_DIR, f'{sid}.csv')
        if not os.path.exists(path):
            raise SystemExit(f'缺少原始文件：{path}')
        for date, value in parse_raw(path):
            merged.setdefault(date, {})[sid] = value

    dates = sorted(merged)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'DGS2', 'DGS10', 'DGS30'])
        for d in dates:
            row = merged[d]
            writer.writerow([
                d,
                row['DGS2'] if row.get('DGS2') is not None else '',
                row['DGS10'] if row.get('DGS10') is not None else '',
                row['DGS30'] if row.get('DGS30') is not None else '',
            ])

    meta = {
        'source': 'FRED (Federal Reserve Bank of St. Louis)',
        'series': sorted(SERIES),
        'start_date': START_DATE,
        'last_date': dates[-1],
        'rows': len(dates),
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f'✓ 已合并 {len(dates)} 个交易日（{dates[0]} ~ {dates[-1]}）')
    print(f'  输出：{CSV_PATH}')
    print(f'        {META_PATH}')


if __name__ == '__main__':
    main()
