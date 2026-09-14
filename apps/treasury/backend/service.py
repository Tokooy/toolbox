#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""业务层：增量更新与前端数据组装
=================================

对外只有两个函数：

* :func:`refresh_data` —— 按需联网更新本地缓存（增量，失败不动旧数据）
* :func:`load_data`    —— 读取本地缓存并组装成前端需要的 JSON 结构
"""

from datetime import datetime, timezone

from . import fred, store

__all__ = ['refresh_data', 'load_data']

NETWORK_HINT = fred.NETWORK_HINT


def refresh_data() -> dict:
    """增量更新：只从各序列「最后非空数据日期」当天起联网获取，合并后原子写回。

    - 已有缓存：每个序列各自计算增量起点（避免某个序列数据滞后导致漏取），
      只下载缺失的那几天，不重复拉全量，减少网络开销；
    - 无缓存：从 ``START_DATE`` 全量获取；
    - 失败保护：任何一步失败都会抛异常，本地旧缓存保持原样不动。
    """
    merged = store.read_rows()
    last_dates: dict[str, str] = {}      # sid -> 最后非空数据日期
    for date, record in merged.items():
        for sid in fred.SERIES:
            if record.get(sid) is not None:
                last_dates[sid] = date
    mode = 'incremental' if last_dates else 'full'

    # 增量起点取「本地最后日期当天」而非次日：FRED 的 cosd 参数若超出其数据范围会
    # 回退返回**全量历史**（实测），cosd=last 始终有效；与缓存重复的日期直接覆盖，
    # 反而能修正 FRED 对最近一个交易日的数值修订。
    new_dates: set[str] = set()
    for sid in fred.SERIES:
        incremental = sid in last_dates
        start = last_dates[sid] if incremental else fred.START_DATE
        for date, value in fred.fetch_series(sid, start=start):
            merged.setdefault(date, {})[sid] = value
            if incremental:
                if date > last_dates[sid]:
                    new_dates.add(date)  # 仅统计真正新增的日期
            else:
                new_dates.add(date)      # 首次（全量）模式下全部视为新增

    dates = sorted(merged)
    if not dates:
        raise RuntimeError('未获取到任何数据')

    meta = {
        'source': 'FRED (Federal Reserve Bank of St. Louis)',
        'series': list(fred.SERIES),
        'start_date': fred.START_DATE,
        'last_date': dates[-1],
        'rows': len(dates),
        'mode': mode,
        'new_dates': len(new_dates),
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    store.write_cache(dates, merged, meta)
    return meta


def load_data() -> dict:
    """读取本地缓存并组装为前端 JSON。

    无缓存时**不自动联网**（网络不通时避免请求卡死），返回 ``no_data`` 标记，
    由前端提示用户点击「获取最新数据」按需获取。
    """
    if not store.has_cache():
        return {
            'no_data': True,
            'start_date': fred.START_DATE,
            'last_date': None,
            'rows': 0,
            'updated_at': None,
            'dates': [],
            'series': {sid: {'name': name, 'values': []}
                       for sid, name in fred.SERIES.items()},
        }

    rows = store.read_rows()
    dates = sorted(rows)
    values = {sid: [rows[date].get(sid) for date in dates] for sid in fred.SERIES}
    meta = store.read_meta()

    return {
        'start_date': meta.get('start_date', fred.START_DATE),
        'last_date': dates[-1] if dates else None,
        'rows': len(dates),
        'updated_at': meta.get('updated_at'),
        'dates': dates,      # 横轴日期数组（YYYY-MM-DD，交易日）—— 前端依赖此字段
        'series': {sid: {'name': name, 'values': values[sid]}
                   for sid, name in fred.SERIES.items()},
    }
