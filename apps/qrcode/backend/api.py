#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口层：``/api/qrcode/*``
============================

二维码生成是**长任务**，因此接口是「提交任务 + 轮询进度」两段式：

* ``GET  /api/qrcode/status``        —— 输入目录与上次结果概要
* ``POST /api/qrcode/upload``        —— 上传 Excel（``?filename=``，请求体为文件内容）
* ``POST /api/qrcode/run``           —— 提交生成任务，立即返回 ``task_id``
* ``GET  /api/qrcode/task/<id>``     —— 轮询任务：日志逐行增长，完成时带结果
* ``GET  /api/qrcode/result``        —— 直接取最近一次生成结果（页面回显用）
* ``GET  /api/qrcode/image/<name>``  —— 单张二维码 PNG
* ``GET  /api/qrcode/download``      —— 下载 HTML / Excel（``?file=``）

生成任务在后台线程里跑，并占用 :data:`core.tasks.TASKS` 的全局互斥锁，
所以生成期间不会与美债刷新等功能并发。
"""

from core.tasks import TASKS

from . import generator, service

__all__ = ['register']


def register(router, ctx):
    prefix = ctx.prefix

    def worker(log):
        generator.run(service.data_root(), log=log)
        return service.build_result(prefix)

    # ---------------- 状态 / 结果 ----------------

    def status(req):
        summary = service.result_summary()
        req.send_json({
            'input_files': service.input_files(),
            'has_result': summary['has_result'],
            'html_name': summary['html_name'],
            'xlsx_name': summary['xlsx_name'],
            'running': TASKS.running(),
        })

    def result(req):
        req.send_json(service.build_result(prefix))

    # ---------------- 生成任务 ----------------

    def run(req):
        if TASKS.running():
            req.send_error(409, '已有任务正在运行，请稍候')
            return
        task_id = TASKS.submit('qrcode', worker)
        if task_id is None:
            req.send_error(409, '已有任务正在运行，请稍候')
            return
        req.send_json({'task_id': task_id})

    def task(req):
        payload = TASKS.get_json(req.params['task_id'])
        if payload is None:
            req.send_error(404, '任务不存在')
            return
        req.send_json(payload)

    # ---------------- 文件 ----------------

    def image(req):
        path = service.image_path(req.params['name'])
        if path is None:
            req.send_error(404, 'Not Found')
            return
        req.send_file(path, 'image/png')

    def download(req):
        path = service.output_path(req.query_one('file', ''))
        if path is None:
            req.send_error(404, 'Not Found')
            return
        content_type = ('application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet' if path.suffix == '.xlsx'
                        else 'text/html; charset=utf-8')
        req.send_file(path, content_type, filename=path.name)

    def upload(req):
        filename = req.query_one('filename', '未命名.xlsx')
        try:
            saved = service.save_upload(filename, req.body())
        except ValueError as exc:
            req.send_error(400, str(exc))
            return
        req.send_json({'ok': True, 'filename': saved})

    router.get('/status', status)
    router.get('/result', result)
    router.get('/task/<task_id>', task)
    router.get('/image/<name>', image)
    router.get('/download', download)
    router.post('/run', run)
    router.post('/upload', upload)


def on_startup(ctx):
    """确认数据目录存在，避免首次运行时前端看到「目录不存在」。"""
    service.ensure_dirs()
