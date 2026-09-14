#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toolbox 运行时路径解析
========================

同一份代码要在三种场景下找到自己的「代码」与「数据」：

===========  ================================  ==========================================
场景          代码根 CODE_ROOT                   数据根 DATA_ROOT
===========  ================================  ==========================================
源码运行      仓库根目录                          <仓库根>/data
单文件 exe    PyInstaller 解包目录 _MEIPASS       exe 所在目录/data（退出后仍保留）
Docker        /app                                /app/data（可用数据卷挂载）
===========  ================================  ==========================================

* **代码根**只读：前端资源、应用后端、脚本，打包后从 ``_MEIPASS`` 读取；
* **数据根**可写：二维码 input/output/qrcodes、美债缓存，绝不写进只读的代码根。

可用环境变量覆盖：

* ``TOOLBOX_ROOT``      —— 覆盖数据根的父目录（默认：exe 所在目录 / 仓库根）
* ``TOOLBOX_DATA_ROOT`` —— 直接指定数据根（优先级最高）
"""

import os
import sys
from pathlib import Path

__all__ = [
    'FROZEN', 'CODE_ROOT', 'APP_ROOT', 'DATA_ROOT',
    'HUB_DIR', 'STATIC_DIR', 'APPS_DIR',
    'bootstrap', 'app_dir', 'app_data_dir',
]

# 打包为单文件 exe 后：程序本体解包到只读临时目录 _MEIPASS，__file__ 不再可靠
FROZEN = bool(getattr(sys, 'frozen', False))

if FROZEN:  # pragma: no cover - 仅在 PyInstaller 打包产物中生效
    CODE_ROOT = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)).resolve()
    APP_ROOT = Path(os.environ.get('TOOLBOX_ROOT') or Path(sys.executable).parent).resolve()
else:
    # core/paths.py -> core/ -> 仓库根
    CODE_ROOT = Path(__file__).resolve().parent.parent
    APP_ROOT = CODE_ROOT

DATA_ROOT = Path(os.environ.get('TOOLBOX_DATA_ROOT') or (APP_ROOT / 'data')).resolve()
# 显式指定了数据根就不再回退旧目录：这种场景下用户已经明确数据放哪儿
DATA_ROOT_EXPLICIT = bool(os.environ.get('TOOLBOX_DATA_ROOT'))

HUB_DIR = CODE_ROOT / 'hub'
STATIC_DIR = HUB_DIR / 'static'
APPS_DIR = CODE_ROOT / 'apps'


def bootstrap() -> None:
    """把代码根加入 ``sys.path``，使 ``import core.* / apps.*`` 在任意启动方式下都成立。

    * 源码运行 ``python hub/server.py`` 时 Python 只把 ``hub/`` 放进 sys.path；
    * 打包 exe 时 ``apps/`` 作为数据文件随包发布，需要 ``_MEIPASS`` 在 sys.path 上。
    """
    root = str(CODE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def app_dir(app_id: str) -> Path:
    """应用代码目录：``apps/<app_id>/``（只读，含 backend / frontend）"""
    return APPS_DIR / app_id


def app_data_dir(app_id: str, legacy: str | None = None) -> Path:
    """应用数据目录：``<DATA_ROOT>/<app_id>/``（可写，与应用代码分离）。

    ``legacy`` 用于兼容旧版目录布局：传入旧版相对路径（如 ``QRcode``、
    ``us-treasury-yields/data``）。仅当「新目录尚不存在、旧目录已存在」时沿用旧目录，
    避免升级后用户已有的输入文件/缓存“凭空消失”；把数据搬到新位置后自动切换到新目录。
    显式设置了 ``TOOLBOX_DATA_ROOT`` 时不做回退。
    """
    new = DATA_ROOT / app_id
    if legacy and not DATA_ROOT_EXPLICIT:
        old = (APP_ROOT / legacy).resolve()
        if old.is_dir() and not new.exists():
            return old
    return new
