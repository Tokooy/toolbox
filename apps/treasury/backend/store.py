#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存储层：本地缓存的读写
=========================

磁盘布局（``<DATA_ROOT>/treasury/``，与代码目录分离）：

.. code-block:: text

    data/treasury/
    ├── raw/                    # FRED 原始 CSV 存档（溯源凭证，随仓库提交）
    │   ├── DGS2.csv
    │   ├── DGS10.csv
    │   └── DGS30.csv
    ├── treasury_yields.csv     # 合并后的本地缓存（date, DGS2, DGS10, DGS30）
    └── meta.json               # 元信息（数据截至日期、行数、更新时间）

写入采用「临时文件 + ``os.replace``」原子替换：写盘过程中断电或异常，旧缓存保持完好。
"""

import csv
import json
import os
from pathlib import Path

from core import paths

__all__ = ['LEGACY_DIR', 'data_dir', 'raw_dir', 'csv_path', 'meta_path',
           'ensure_dir', 'has_cache', 'read_rows', 'read_meta', 'write_cache']

# 旧版（重构前）本应用的缓存目录，用于升级后自动沿用用户已有数据
LEGACY_DIR = 'us-treasury-yields/data'

FIELDS = ('date', 'DGS2', 'DGS10', 'DGS30')


def data_dir() -> Path:
    return paths.app_data_dir('treasury', legacy=LEGACY_DIR)


def raw_dir() -> Path:
    return data_dir() / 'raw'


def csv_path() -> Path:
    return data_dir() / 'treasury_yields.csv'


def meta_path() -> Path:
    return data_dir() / 'meta.json'


def ensure_dir() -> Path:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def has_cache() -> bool:
    return csv_path().is_file()


def read_rows() -> dict[str, dict[str, float | None]]:
    """读取缓存为 ``{date: {sid: value|None}}``；无缓存返回空字典。"""
    path = csv_path()
    if not path.is_file():
        return {}
    merged: dict[str, dict[str, float | None]] = {}
    with open(path, encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            date = row.get('date', '').strip()
            if not date:
                continue
            record = {}
            for sid in FIELDS[1:]:
                raw = (row.get(sid) or '').strip()
                record[sid] = None if raw == '' else float(raw)
            merged[date] = record
    return merged


def read_meta() -> dict:
    path = meta_path()
    if not path.is_file():
        return {}
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def write_cache(dates, merged: dict, meta: dict) -> None:
    """把合并后的数据与元信息原子写回磁盘。"""
    ensure_dir()
    target = csv_path()
    tmp_path = str(target) + '.tmp'
    with open(tmp_path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        for date in dates:
            row = merged[date]
            writer.writerow([date] + ['' if row.get(sid) is None else row[sid]
                                      for sid in FIELDS[1:]])
    os.replace(tmp_path, target)

    with open(meta_path(), 'w', encoding='utf-8') as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
