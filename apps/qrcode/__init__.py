# -*- coding: utf-8 -*-
"""二维码批量生成 · Bulk QR-Code Generator

后端目录结构：

* ``generator.py`` 纯生成逻辑：Excel（``二维码编号`` 列）→ 二维码 PNG → HTML / Excel
* ``service.py``   数据目录、上传与已生成结果的扫描（面向网页的能力）
* ``api.py``       接口层：``/api/qrcode/*``（任务式调用，前端轮询日志与结果）

命令行用法（不启动网页）：``python apps/qrcode/cli.py``
"""
