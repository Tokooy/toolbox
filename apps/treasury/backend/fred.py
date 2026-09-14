#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网络层：从 FRED 下载美债收益率序列
=====================================

数据源：美国圣路易斯联邦储备银行 FRED（美联储官方数据发布渠道）
https://fred.stlouisfed.org/

序列：DGS2 / DGS10 / DGS30 —— 美国国债 2 / 10 / 30 年期恒定到期收益率（日频，%）。

针对大陆网络环境的三个关键处理（实测有效，勿轻易改动）：

1. **自动探测代理**：用户常开了全局代理但没设环境变量，这里自动接管常见本地代理端口；
2. **不携带浏览器 UA**：FRED 边缘节点（Akamai）会黑洞「浏览器 UA + 非浏览器 TLS 指纹」
   的组合请求（表现为连接成功但一直不返回），诚实的默认 UA（curl / urllib）可正常放行；
3. **系统 curl 优先**：强制 HTTP/1.1 规避部分网络对 HTTP/2 帧的干扰，失败再用 urllib 兜底。
"""

import csv
import io
import os
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

__all__ = ['SERIES', 'START_DATE', 'PROXY', 'fetch_series', 'detect_proxy']

START_DATE = '2020-01-01'          # 数据起始日期（2020 年至今）
FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}'

# 序列 ID → 前端展示名
SERIES = {'DGS2': '2-Year', 'DGS10': '10-Year', 'DGS30': '30-Year'}

NETWORK_HINT = ('；提示：请确认本机网络/代理可访问 FRED，或为本机配置代理后重启服务'
                '（例如 export HTTPS_PROXY=http://127.0.0.1:7890），再重新点击获取')

_PROXY_PORTS = (7890, 7897, 1080, 10809, 10808, 8889, 8118)
_PROXY_VARS = ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy')


def detect_proxy():
    """自动探测可用代理：优先环境变量，其次常见本地代理端口（Clash / v2ray 等）。"""
    for var in _PROXY_VARS:
        value = os.environ.get(var, '').strip()
        if value:
            return value.rstrip('/')
    for port in _PROXY_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        try:
            sock.connect(('127.0.0.1', port))
            return 'http://127.0.0.1:%d' % port
        except OSError:
            pass
        finally:
            sock.close()
    return None


# 模块加载时探测一次（服务启动时）；无代理则为 None（直连）
PROXY = detect_proxy()


def _curl(url: str, timeout: int) -> str:
    """系统 curl 抓取（强制 HTTP/1.1、自动压缩、自动重试）。"""
    cmd = ['curl', '-sS', '--http1.1', '--compressed', '--max-time', str(timeout)]
    if PROXY:
        cmd += ['-x', PROXY]
    cmd += ['--retry', '1', '--retry-delay', '1', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 15)
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout.decode('utf-8-sig')
    raise RuntimeError(proc.stderr.decode('utf-8', errors='replace').strip()
                       or 'curl 退出码 %d' % proc.returncode)


def _urllib(url: str, timeout: int) -> str:
    """标准库兜底（同样自动走探测到的代理）。"""
    if PROXY:
        opener = build_opener(ProxyHandler({'http': PROXY, 'https': PROXY}))
    else:
        opener = build_opener()
    with opener.open(url, timeout=timeout) as resp:
        return resp.read().decode('utf-8-sig')


def http_get(url: str, timeout: int = 12, attempts: int = 2) -> str:
    """多策略获取 URL 文本：curl 优先、urllib 兜底，带有限次重试。"""
    last_err = None
    for attempt in range(attempts):
        try:
            return _curl(url, timeout)
        except FileNotFoundError:
            last_err = '系统未安装 curl'
            break                       # 无 curl，直接走 urllib
        except subprocess.TimeoutExpired:
            last_err = 'curl 超时'
        except (OSError, RuntimeError) as exc:
            last_err = 'curl 调用失败: %s' % exc
        if attempt < attempts - 1:
            time.sleep(1)

    try:
        return _urllib(url, timeout)
    except (URLError, HTTPError, OSError, ValueError) as exc:
        raise RuntimeError('curl 失败(%s)；urllib 失败(%s)%s'
                           % (last_err, exc, NETWORK_HINT)) from exc


def fetch_series(sid: str, start: str = START_DATE) -> list[tuple[str, float | None]]:
    """下载单个序列自 ``start``（含）起的 CSV，返回 ``[(date, value|None), ...]``。

    增量场景（``start`` 为已有数据的最后日期）下，FRED 可能没有新数据而只返回表头，
    此时返回空列表属于正常情况；只有响应体完全为空才视为异常。
    """
    text = http_get(FRED_URL.format(sid=sid, start=start))
    if not text.strip():
        raise RuntimeError('FRED 未返回 %s 的任何数据' % sid)

    rows = []
    for line in csv.reader(io.StringIO(text)):
        if len(line) < 2:
            continue
        date = line[0].strip()
        raw = line[1].strip()
        if not date or date.upper() in ('DATE', 'OBSERVATION_DATE'):
            continue
        rows.append((date, None if raw in ('', '.') else float(raw)))
    return rows
