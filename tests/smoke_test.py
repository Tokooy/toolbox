#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toolbox 冒烟测试（零第三方依赖）
===================================

在临时数据目录里拉起真实的工具台服务，把「宿主外壳 + 两个工具」的核心链路跑一遍：

* 宿主：``GET /``、``/api/health``、``/api/apps``、静态资源与目录穿越防护
* 美债：``GET /api/treasury/data``（用仓库内置种子数据验证“有数据”分支）
* 二维码：上传 Excel → 提交任务 → 轮询日志 → 取结果 → 拉图片 → 下载 Excel

用法（仓库根目录下）：

.. code-block:: bash

    python tests/smoke_test.py

退出码 0 表示全部通过；任何一项失败都会打印 ``✗`` 明细并以 1 退出，可直接用于 CI。
"""

import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 测试全程使用临时数据目录，绝不碰仓库里的真实数据（必须在 import core 之前设置）
# 注意：不用 tempfile.mkdtemp —— 它以 0o700 建目录，在部分受限环境下其子目录不可写
_TMP_DATA = ROOT / ('.smoke-%d' % os.getpid())
_TMP_DATA.mkdir(parents=True, exist_ok=True)
os.environ['TOOLBOX_DATA_ROOT'] = str(_TMP_DATA)

from core import http, paths, registry        # noqa: E402
from hub import server as hub                 # noqa: E402

PASSED, FAILED = [], []
PORT = 0


def check(name: str, condition: bool, detail: str = ''):
    if condition:
        PASSED.append(name)
        print('  ✓ %s' % name)
    else:
        FAILED.append('%s %s' % (name, detail))
        print('  ✗ %s %s' % (name, detail))


def request(method: str, path: str, data: bytes | None = None):
    """返回 ``(status, headers, body_bytes)``，4xx/5xx 不抛异常。"""
    url = 'http://127.0.0.1:%d%s' % (PORT, path)
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def json_of(method: str, path: str, data: bytes | None = None):
    status, _, body = request(method, path, data)
    try:
        return status, json.loads(body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return status, {}


def seed_treasury() -> bool:
    """把仓库内置的美债种子缓存复制到临时数据目录，验证“有数据”分支。"""
    for candidate in (ROOT / 'data' / 'treasury', ROOT / 'us-treasury-yields' / 'data'):
        if (candidate / 'treasury_yields.csv').is_file():
            shutil.copytree(candidate, _TMP_DATA / 'treasury', dirs_exist_ok=True)
            return True
    return False


def make_excel(path: Path, codes):
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.cell(row=1, column=1).value = '二维码编号'
    for index, code in enumerate(codes, start=2):
        sheet.cell(row=index, column=1).value = code
    workbook.save(str(path))


def main() -> int:
    global PORT

    apps = registry.discover()
    check('发现应用清单', len(apps) >= 2, '实际 %d 个' % len(apps))
    check('应用顺序与 id', [a.id for a in apps][:2] == ['treasury', 'qrcode'],
          str([a.id for a in apps]))

    router = hub.build_router(apps, hub.load_config())
    router.get('/', lambda req: req.send_file(paths.STATIC_DIR / 'index.html'))
    server = http.make_server('127.0.0.1', 0, router, hub.static_mounts(apps), 'SmokeTest')
    PORT = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print('\n临时服务：http://127.0.0.1:%d  数据目录：%s\n' % (PORT, _TMP_DATA))

    # ---------------- 宿主 ----------------
    status, _, body = request('GET', '/')
    check('GET / 返回外壳页面', status == 200 and b'<div id="app">' in body, 'status=%s' % status)

    status, payload = json_of('GET', '/api/health')
    check('GET /api/health', status == 200 and payload.get('ok') is True, str(payload))

    status, payload = json_of('GET', '/api/apps')
    listed = {app['id']: app for app in payload.get('apps', [])}
    check('GET /api/apps 下发应用清单',
          status == 200 and 'treasury' in listed and 'qrcode' in listed, str(list(payload)))
    check('清单带前端入口 URL',
          listed.get('qrcode', {}).get('panel', '').startswith('/apps/qrcode/'),
          str(listed.get('qrcode')))

    for asset in ('/static/index.html', '/static/vendor/vue.global.prod.js'):
        status, _, body = request('GET', asset)
        check('静态资源 %s' % asset, status == 200 and len(body) > 0, 'status=%s' % status)

    # 外壳 + 宿主 SDK + 各应用前端：必须是可被浏览器当作 ES module 执行的 MIME 类型
    for asset in ('/static/shell.js', '/static/shell.css', '/static/sdk/runtime.js',
                  '/static/sdk/api.js', '/static/sdk/ui.js', '/static/sdk/icons.js'):
        status, headers, body = request('GET', asset)
        check('外壳资源 %s' % asset, status == 200 and len(body) > 0, 'status=%s' % status)

    for asset in ('/apps/treasury/panel.js', '/apps/treasury/panel.css',
                  '/apps/qrcode/panel.js', '/apps/qrcode/panel.css'):
        status, headers, body = request('GET', asset)
        ok = status == 200 and len(body) > 0
        if asset.endswith('.js'):
            ok = ok and 'javascript' in headers.get('Content-Type', '')
        check('应用前端资源 %s' % asset, ok, 'status=%s type=%s' % (status, headers.get('Content-Type')))

    status, _, body = request('GET', '/')
    check('外壳页面加载 shell.js', b'/static/shell.js' in body and b'shell.css' in body)

    for attack in ('/static/..%2f..%2fhub/server.py', '/static/%2e%2e/%2e%2e/hub/server.py'):
        status, _, _ = request('GET', attack)
        check('静态资源拒绝目录穿越 %s' % attack, status == 404, 'status=%s' % status)

    # ---------------- 美债 ----------------
    seeded = seed_treasury()
    status, payload = json_of('GET', '/api/treasury/data')
    if seeded:
        check('GET /api/treasury/data 读取缓存', status == 200 and payload.get('rows', 0) > 0,
              'rows=%s' % payload.get('rows'))
        check('美债返回三条序列',
              sorted(payload.get('series', {})) == ['DGS10', 'DGS2', 'DGS30'],
              str(sorted(payload.get('series', {}))))
        check('美债日期与数值等长',
              len(payload.get('dates', [])) == len(payload['series']['DGS2']['values']))
    else:
        print('  - 跳过美债缓存断言（仓库内没有种子数据）')

    # ---------------- 二维码 ----------------
    excel = _TMP_DATA / 'smoke_input.xlsx'
    # 编号给足量：既覆盖「多行 HTML / Excel 输出」，也让生成过程足够长，
    # 从而稳定地验证「同一时刻只运行一个任务」的并发保护
    codes = ['SMOKE-%03d' % index for index in range(1, 41)]
    make_excel(excel, codes)

    status, payload = json_of('POST', '/api/qrcode/upload?filename=smoke_input.xlsx',
                              excel.read_bytes())
    check('上传 Excel', status == 200 and payload.get('ok') is True, str(payload))

    status, payload = json_of('GET', '/api/qrcode/status')
    check('输入目录可见上传文件', status == 200 and len(payload.get('input_files', [])) == 1,
          str(payload.get('input_files')))

    status, payload = json_of('POST', '/api/qrcode/run')
    task_id = payload.get('task_id')
    check('提交生成任务', status == 200 and bool(task_id), str(payload))

    status, payload = json_of('POST', '/api/qrcode/run')
    check('并发任务被拒绝', status == 409, 'status=%s' % status)

    result = None
    deadline = time.time() + 120
    while time.time() < deadline:
        status, payload = json_of('GET', '/api/qrcode/task/%s' % task_id)
        if payload.get('status') in ('done', 'error'):
            result = payload
            break
        time.sleep(0.4)

    check('任务在限时内结束', result is not None, '任务超时')
    if result:
        check('任务成功', result['status'] == 'done',
              '错误：%s\n%s' % (result.get('error'), '\n'.join(result.get('log', []))))
        log_text = '\n'.join(result.get('log', []))
        check('日志含 5 个步骤标记',
              all(('[%d/5]' % i) in log_text for i in range(1, 6)))
        data = result.get('result') or {}
        check('结果条目数 = 编号数', data.get('count') == len(codes), str(data.get('count')))
        check('结果含 HTML / Excel 下载项', len(data.get('outputs', [])) == 2,
              str(data.get('outputs')))

        if data.get('items'):
            image_url = data['items'][0]['image']
            check('预览图片地址已改写为 HTTP', image_url.startswith('/api/qrcode/image/'),
                  image_url)
            status, _, body = request('GET', image_url)
            check('二维码图片可访问', status == 200 and body[:4] == b'\x89PNG',
                  'status=%s' % status)

        for output in data.get('outputs', []):
            status, _, body = request('GET', output['url'])
            ok = status == 200 and len(body) > 0
            if output['kind'] == 'xlsx':
                ok = ok and body[:2] == b'PK'
            check('下载 %s' % output['name'], ok, 'status=%s' % status)

    status, payload = json_of('GET', '/api/qrcode/result')
    check('GET /api/qrcode/result 回显结果', status == 200 and payload.get('has_result') is True)

    # ---------------- 汇总 ----------------
    server.shutdown()
    print('\n' + '=' * 56)
    if FAILED:
        print('  ✗ 失败 %d 项 / 通过 %d 项' % (len(FAILED), len(PASSED)))
        for item in FAILED:
            print('    - %s' % item)
        return 1
    print('  ✓ 全部通过（%d 项）' % len(PASSED))
    return 0


if __name__ == '__main__':
    try:
        code = main()
    finally:
        shutil.rmtree(_TMP_DATA, ignore_errors=True)
    raise SystemExit(code)
