#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后台任务与全局互斥
====================

Toolbox 里有两类「重任务」：

1. **长任务**——二维码批量生成：跑在后台线程里，前端轮询日志与结果；
2. **同步任务**——美债数据联网刷新：在请求线程里同步执行，直接返回结果。

两类任务共用**同一把全局互斥锁**：点哪个按钮运行哪个功能，同一时刻只允许一个任务在跑，
避免磁盘 / 网络 / CPU 被同时抢用（这也是工具台「按需运行、互不打扰」的实现方式）。

:data:`TASKS` 是进程级单例，应用后端直接 ``from core.tasks import TASKS`` 使用。
"""

import contextlib
import threading
import traceback
from datetime import datetime

__all__ = ['Task', 'TaskManager', 'LogWriter', 'TASKS']


class LogWriter:
    """把被调用代码的 ``print`` 输出按行实时写入任务日志（供前端轮询展示）。

    既是**文件对象**（可传给 ``print(..., file=...)`` / ``contextlib.redirect_stdout``），
    也是**可调用对象**（业务代码里常见的 ``log('...')`` 写法），两种风格都支持。
    """

    def __init__(self, sink: list):
        self._sink = sink
        self._buf = ''

    def __call__(self, *parts):
        self.write(' '.join(str(part) for part in parts) + '\n')

    def write(self, text: str):
        self._buf += text
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            line = line.rstrip('\r')
            if line:
                self._sink.append(line)

    def flush(self):
        pass

    def close(self):
        if self._buf.strip():
            self._sink.append(self._buf.rstrip('\r'))
        self._buf = ''


class Task:
    """一次后台任务的运行记录。"""

    def __init__(self, task_id: str, kind: str):
        self.id = task_id
        self.kind = kind
        self.status = 'running'          # running | done | error
        self.log: list[str] = []
        self.error: str | None = None
        self.result = None
        self.created_at = datetime.now().strftime('%H:%M:%S')

    def to_json(self) -> dict:
        return {
            'id': self.id,
            'kind': self.kind,
            'status': self.status,
            'log': list(self.log),
            'error': self.error,
            'result': self.result,
            'created_at': self.created_at,
        }


class TaskManager:
    """任务注册表 + 全局互斥锁。"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._exclusive_lock = threading.Lock()
        self._seq = 0

    # ---------------- 全局互斥 ----------------

    @contextlib.contextmanager
    def exclusive(self):
        """同步任务使用：``with TASKS.exclusive(): ...`` 保证不与其它任务并发。"""
        with self._exclusive_lock:
            yield

    # ---------------- 后台任务 ----------------

    def running(self) -> bool:
        with self._lock:
            return any(task.status == 'running' for task in self._tasks.values())

    def submit(self, kind: str, worker, task_id: str | None = None) -> str | None:
        """把 ``worker(log)`` 放进后台线程执行；已有任务在跑时返回 ``None``。

        ``worker`` 接收一个 :class:`LogWriter`，把日志写进任务记录；
        返回值作为任务结果保存，供前端轮询 ``GET .../task/<id>`` 获取。
        """
        with self._lock:
            if any(task.status == 'running' for task in self._tasks.values()):
                return None
            self._seq += 1
            task_id = task_id or 'task-%d' % self._seq
            task = Task(task_id, kind)
            self._tasks[task_id] = task

        threading.Thread(target=self._run, args=(task, worker), daemon=True).start()
        return task_id

    def _run(self, task: Task, worker):
        log = LogWriter(task.log)
        try:
            with self.exclusive():
                with contextlib.redirect_stdout(log):
                    task.result = worker(log)
            log.close()
            task.status = 'done'
        except SystemExit as exc:        # 脚本式代码常用 sys.exit(1) 表示业务错误
            log.close()
            task.status = 'error'
            task.error = '脚本退出码 %s' % (exc.code if exc.code is not None else 1)
        except Exception as exc:         # noqa: BLE001 - 任务失败要记录而不是抛出线程
            log.close()
            task.status = 'error'
            task.error = str(exc)
            task.log.append(traceback.format_exc(limit=3).rstrip())

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def get_json(self, task_id: str) -> dict | None:
        task = self.get(task_id)
        return task.to_json() if task else None


TASKS = TaskManager()
