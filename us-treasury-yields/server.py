#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美国国债收益率看板 · US Treasury Yield Dashboard
=================================================
一个零第三方依赖（纯 Python 标准库）的本地 Web 服务：

  * 数据源：美国圣路易斯联邦储备银行 FRED（美联储官方数据发布渠道）
      https://fred.stlouisfed.org/
  * 序列：DGS2 / DGS10 / DGS30 —— 美国国债 2/10/30 年期恒定到期收益率（日频，%）
  * 行为：首次启动时若本地没有缓存数据，自动从 FRED 获取 2020 年至今的全部数据；
          之后每次运行都直接读取本地缓存，只有点击网页上的「获取最新数据」按钮
          才会再次联网获取（POST /api/refresh）。
  * 运行：python server.py  →  http://127.0.0.1:5000
"""

import csv
import io
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError, HTTPError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

# --------------------------------------------------------------------------
# 路径与常量
# --------------------------------------------------------------------------
# 数据/缓存根目录：默认与脚本同目录（standalone 运行不受影响）；
# 被 Toolbox 单文件 exe 内嵌加载时，由 hub 通过环境变量指向 exe 旁的持久目录
# （exe 解包出的 _MEIPASS 是只读临时目录，缓存写进去会在退出后丢失）。
BASE_DIR = os.environ.get('TOOLBOX_TREASURY_HOME') or os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'treasury_yields.csv')
META_PATH = os.path.join(DATA_DIR, 'meta.json')

START_DATE = '2020-01-01'          # 数据起始日期（2020 年至今）
PORT = int(os.environ.get('PORT', '8080'))

FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}'
# 序列 ID → 展示名
SERIES = {'DGS2': '2-Year', 'DGS10': '10-Year', 'DGS30': '30-Year'}

_refresh_lock = threading.Lock()


# --------------------------------------------------------------------------
# 数据获取与缓存
# --------------------------------------------------------------------------
NETWORK_HINT = ('；提示：请确认本机网络/代理可访问 FRED，或为本机配置代理后重启服务'
                '（例如 export HTTPS_PROXY=http://127.0.0.1:7890），再重新点击获取')


def _detect_proxy():
    """自动探测可用代理：优先环境变量，其次常见本地代理端口（Clash/v2ray 等）。

    用户常开了全局代理但未设置环境变量，导致服务进程（curl/urllib）直连被
    FRED 边缘节点限流；这里自动接管本地代理端口，让「开了代理」真正生效。
    """
    import socket

    for var in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy',
                'ALL_PROXY', 'all_proxy'):
        val = os.environ.get(var, '').strip()
        if val:
            return val.rstrip('/')
    for port in (7890, 7897, 1080, 10809, 10808, 8889, 8118):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            s.connect(('127.0.0.1', port))
            return f'http://127.0.0.1:{port}'
        except OSError:
            pass
        finally:
            s.close()
    return None


# 模块加载时探测一次（服务启动时）；无代理则为 None（直连）
PROXY = _detect_proxy()


def _http_get(url, timeout=12, attempts=2):
    """多策略获取 URL 文本（针对 FRED/Akamai 限流与大陆网络环境优化）。

    关键：**不要携带浏览器 UA** —— Akamai Bot Manager 会对「浏览器 UA + 非浏览器
    TLS 指纹」的组合做黑洞限流（表现为连接建立后无响应直至超时），而诚实的默认 UA
    （curl/8.x、Python-urllib/3.x）可正常放行。实测：浏览器 UA 直连/走代理均超时，
    默认 UA 直连/走代理均 200。
    策略 1：系统 curl（强制 HTTP/1.1 规避 HTTP/2 帧被干扰），自动使用探测到的代理；
    策略 2：Python 标准库 urllib（同样自动走代理）。
    """
    import subprocess
    import time as _time

    last_err = None
    for attempt in range(attempts):
        try:
            cmd = ['curl', '-sS', '--http1.1', '--compressed',
                   '--max-time', str(timeout)]
            if PROXY:
                cmd += ['-x', PROXY]
            cmd += ['--retry', '1', '--retry-delay', '1', url]
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 15)
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout.decode('utf-8-sig')
            last_err = (proc.stderr.decode('utf-8', errors='replace').strip()
                        or f'curl 退出码 {proc.returncode}')
        except FileNotFoundError:
            last_err = '系统未安装 curl'
            break  # 无 curl，直接走 urllib
        except subprocess.TimeoutExpired as exc:
            last_err = f'curl 超时: {exc}'
        except OSError as exc:
            last_err = f'curl 调用失败: {exc}'
        if attempt < attempts - 1:
            _time.sleep(1)

    try:
        if PROXY:
            proxy_handler = urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})
            opener = urllib.request.build_opener(proxy_handler)
        else:
            opener = urllib.request.build_opener()
        with opener.open(url, timeout=timeout) as resp:
            return resp.read().decode('utf-8-sig')
    except (URLError, HTTPError, OSError) as exc:
        raise RuntimeError(f'curl 失败({last_err})；urllib 失败({exc})'
                           f'{NETWORK_HINT}') from exc


def _add_one_day(date_str: str) -> str:
    """YYYY-MM-DD + 1 天"""
    d = datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def fetch_series(sid, start=START_DATE):
    """从 FRED 下载单个序列自 start（含）起的 CSV，返回 [(date, value|None), ...]。

    增量场景（start 为最后数据日期的次日）下，FRED 可能没有新数据而只返回表头，
    此时返回空列表属于正常情况；只有响应体完全为空才视为异常。
    """
    url = FRED_URL.format(sid=sid, start=start)
    text = _http_get(url)
    if not text.strip():
        raise RuntimeError(f'FRED 未返回 {sid} 的任何数据')

    rows = []
    for line in csv.reader(io.StringIO(text)):
        if len(line) < 2:
            continue
        date = line[0].strip()
        raw = line[1].strip()
        if not date or date.upper() in ('DATE', 'OBSERVATION_DATE'):
            continue
        value = None if raw in ('', '.') else float(raw)
        rows.append((date, value))
    return rows


def refresh_data():
    """增量更新：只从各序列「最后非空数据日期 + 1 天」起联网获取，合并后原子写回。

    - 已有缓存：每个序列各自计算增量起点（避免某个序列数据滞后导致漏取），
      只下载缺失的那几天，不重复拉全量，减少网络开销；
    - 无缓存：从 START_DATE 全量获取；
    - 失败保护：任何一步失败都会抛异常，本地旧缓存保持原样不动。
    """
    with _refresh_lock:
        # ── 读现有缓存：构建 merged 与各序列最后非空日期 ──
        merged = {}
        last_dates = {}  # sid -> 最后非空数据日期
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    date = row['date']
                    rec = {}
                    for sid in SERIES:
                        raw = row.get(sid, '').strip()
                        val = None if raw == '' else float(raw)
                        rec[sid] = val
                        if val is not None:
                            last_dates[sid] = date
                    merged[date] = rec

        # ── 增量起点：无缓存则全量 ──
        # 注意：FRED 的 cosd 参数若超出其数据范围会回退返回**全量历史**（实测），
        # 因此增量起点取「本地最后日期当天」而非次日——cosd=last 始终有效，
        # 返回 last 起的所有数据（含之后的新数据），与缓存重复的日期由 setdefault 跳过。
        new_dates = set()
        for sid in SERIES:
            incremental = sid in last_dates
            start = last_dates[sid] if incremental else START_DATE
            rows = fetch_series(sid, start=start)
            for date, value in rows:
                merged.setdefault(date, {})[sid] = value
                if incremental and date > last_dates[sid]:
                    new_dates.add(date)  # 仅统计真正新增的日期
            if not incremental:
                new_dates |= {d for d, _ in rows}  # 全量（首次）模式下全部视为新增

        dates = sorted(merged)
        if not dates:
            raise RuntimeError('未获取到任何数据')

        # ── 原子写回 ──
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp_path = CSV_PATH + '.tmp'
        with open(tmp_path, 'w', newline='', encoding='utf-8') as f:
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
        os.replace(tmp_path, CSV_PATH)

        meta = {
            'source': 'FRED (Federal Reserve Bank of St. Louis)',
            'series': list(SERIES.keys()),
            'start_date': START_DATE,
            'last_date': dates[-1],
            'rows': len(dates),
            'mode': 'incremental' if last_dates else 'full',
            'new_dates': len(new_dates),
            'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        with open(META_PATH, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta


def load_data():
    """读取本地缓存并组装为前端 JSON。

    无缓存时**不自动联网**（网络不通时避免请求卡死），返回 no_data 标记，
    由前端提示用户点击「获取最新数据」按需获取。
    """
    if not os.path.exists(CSV_PATH):
        return {
            'no_data': True,
            'start_date': START_DATE,
            'last_date': None,
            'rows': 0,
            'updated_at': None,
            'dates': [],
            'series': {sid: {'name': SERIES[sid], 'values': []} for sid in SERIES},
        }

    dates, values = [], {sid: [] for sid in SERIES}
    with open(CSV_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            dates.append(row['date'])
            for sid in SERIES:
                raw = row.get(sid, '').strip()
                values[sid].append(None if raw == '' else float(raw))

    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding='utf-8') as f:
            meta = json.load(f)

    return {
        'start_date': meta.get('start_date', START_DATE),
        'last_date': dates[-1] if dates else None,
        'rows': len(dates),
        'updated_at': meta.get('updated_at'),
        'dates': dates,   # 横轴日期数组（YYYY-MM-DD，交易日）—— 前端依赖此字段
        'series': {sid: {'name': SERIES[sid], 'values': values[sid]} for sid in SERIES},
    }


# --------------------------------------------------------------------------
# HTTP 服务
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'TreasuryYieldDashboard/1.0'

    def log_message(self, fmt, *args):
        sys.stderr.write('[%s] %s\n' % (datetime.now().strftime('%H:%M:%S'), fmt % args))

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端已断开，忽略

    def _send_error(self, status, message):
        self._send_json({'error': message}, status)

    def _serve_static(self, path):
        rel = path[len('/static/'):]
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            self._send_error(404, 'Not Found')
            return
        with open(full, 'rb') as f:
            body = f.read()
        ctype, _ = mimetypes.guess_type(full)
        self.send_response(200)
        self.send_header('Content-Type', ctype or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端已断开，忽略

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/':
            self._serve_static('/static/index.html')
        elif path == '/api/data':
            try:
                self._send_json(load_data())
            except Exception as exc:  # noqa: BLE001 —— 向客户端返回可读错误
                self._send_error(500, f'读取数据失败: {exc}')
        elif path.startswith('/static/'):
            self._serve_static(path)
        else:
            self._send_error(404, 'Not Found')

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        if path == '/api/refresh':
            try:
                meta = refresh_data()
                payload = load_data()
                payload['refreshed'] = True
                payload['refresh_meta'] = meta
                self._send_json(payload)
            except Exception as exc:  # noqa: BLE001
                self._send_error(502, f'从 FRED 获取数据失败: {exc}')
        else:
            self._send_error(404, 'Not Found')


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # 无缓存时在后台线程尝试首次获取（不阻塞服务启动；失败仅提示，可随时点按钮重试）
    if not os.path.exists(CSV_PATH):
        def _background_fetch():
            try:
                meta = refresh_data()
                print(f'  ✓ 首次数据获取完成：{meta["rows"]} 个交易日，截至 {meta["last_date"]}')
            except Exception as exc:  # noqa: BLE001
                print(f'  ⚠ 首次自动获取失败（{exc}）\n'
                      f'    服务已正常启动，可打开网页后点击「获取最新数据」重试；'
                      f'    若在中国大陆无法直连 FRED，请配置 HTTPS_PROXY 代理后重启。',
                      file=sys.stderr)
        threading.Thread(target=_background_fetch, daemon=True).start()

    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as exc:
        print(f'\n✗ 启动失败：端口 {PORT} 已被占用（{exc}）')
        print('  可能已有服务实例在运行。请先关闭旧实例，或换端口启动：')
        print(f'    PORT={PORT + 100} python server.py')
        sys.exit(1)
    url = f'http://127.0.0.1:{PORT}'
    print()
    print(f'  美国国债收益率看板已启动：{url}')
    print(f'  按 Ctrl+C 停止服务')
    print()
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 —— 无桌面环境时忽略
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止。')


if __name__ == '__main__':
    main()
