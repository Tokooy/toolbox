#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口层：``/api/treasury/*``
==============================

宿主（``hub`` 或本应用的 ``standalone``）把本模块注册到 ``/api/treasury`` 子路由上：

* ``GET  /api/treasury/data``    —— 读取本地缓存（从不联网，秒回）
* ``POST /api/treasury/refresh`` —— 按需联网增量更新，返回更新后的完整数据

两个接口与美债单工具站点的接口**完全一致**，因此同一份前端面板既能跑在工具台里，
也能跑在“只有美债”的独立页面上。
"""

from core.tasks import TASKS

from . import service, store

__all__ = ['register', 'on_startup']


def register(router, ctx):
    router.get('/data', _data)
    router.post('/refresh', _refresh)


def _data(req):
    try:
        req.send_json(service.load_data())
    except Exception as exc:                     # noqa: BLE001 - 错误要回给前端展示
        req.send_error(500, '读取数据失败: %s' % exc)


def _refresh(req):
    try:
        # 与二维码生成共用全局任务锁：同一时刻只允许一个重任务运行
        with TASKS.exclusive():
            meta = service.refresh_data()
            payload = service.load_data()
        payload['refreshed'] = True
        payload['refresh_meta'] = meta
        req.send_json(payload)
    except Exception as exc:                     # noqa: BLE001
        req.send_error(502, '从 FRED 获取数据失败: %s' % exc)


def on_startup(ctx):
    """无本地缓存时：先用随包种子数据铺一份（如有），再在后台尝试联网获取。

    种子数据让打包 exe / Docker 在离线环境也能立刻看到 2020 年以来的历史曲线；
    联网获取失败只提示、不影响服务，用户随时可以点「获取最新数据」重试。
    """
    if store.ensure_seed():
        print('  ✓ 已用内置种子数据初始化美债缓存（离线可用，点按钮可增量更新）')
    if store.has_cache():
        return
    try:
        meta = service.refresh_data()
        print('  ✓ 美债首次数据获取完成：%d 个交易日，截至 %s'
              % (meta['rows'], meta['last_date']))
    except Exception as exc:                     # noqa: BLE001
        print('  ⚠ 美债首次自动获取失败（%s）\n'
              '    服务已正常启动，可打开网页后点击「获取最新数据」重试；\n'
              '    若在中国大陆无法直连 FRED，请配置 HTTPS_PROXY 代理后重启。' % exc)
