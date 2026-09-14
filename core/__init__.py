# -*- coding: utf-8 -*-
"""Toolbox 共享内核（core）
=========================

不属于任何具体工具的公共能力，被 `hub`（多工具宿主）与 `apps/*`（各工具）共同复用：

  * ``core.paths``      —— 运行时路径解析（源码 / PyInstaller 单文件 exe / Docker）
  * ``core.http``       —— 极简 HTTP 路由与请求响应封装（纯标准库）
  * ``core.tasks``      —— 后台任务管理与全局任务互斥
  * ``core.registry``   —— 应用发现与装配（apps/<id>/app.json + backend.api）
  * ``core.standalone`` —— 把单个应用作为独立站点运行

依赖方向：``apps/* -> core``，``hub -> core + apps/*``；``core`` 不反向依赖任何业务代码。
"""

__all__ = ['http', 'paths', 'registry', 'standalone', 'tasks']
