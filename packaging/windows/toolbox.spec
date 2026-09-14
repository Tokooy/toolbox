# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  Toolbox 工具台 · PyInstaller 打包配置（Windows 单文件 exe）
#
#  用法（在仓库根目录执行）：
#      pyinstaller --clean --noconfirm packaging/windows/toolbox.spec
#  产物：dist/Toolbox.exe（单文件，自带 Python 运行时与全部依赖）
#
#  设计说明（与 core/paths.py 的 FROZEN 分支配套）：
#    * 代码资源（core/、apps/、hub/static、hub/hub.json）打进 exe，
#      运行期从 _MEIPASS 解包目录读取 —— 那里是只读的临时目录；
#    * 可变数据（data/：二维码输入输出、美债缓存）由 core.paths 重定向到
#      **exe 所在目录**，退出后依然保留，不会随临时目录被清空。
# ============================================================
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent.parent        # packaging/windows/ -> 仓库根

datas = []
binaries = []
hiddenimports = []

# 二维码批量生成依赖：生成脚本在运行时才被 import，静态分析看不到，需显式收集
# （qrcode 走 Pillow 图片工厂，因此不需要 pypng）
for pkg in ('qrcode', 'PIL', 'openpyxl', 'et_xmlfile'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# 应用自带资源：公共内核、各工具（后端 + 前端 + 清单）、外壳前端与配置
datas += [
    (str(ROOT / 'core'), 'core'),
    (str(ROOT / 'apps'), 'apps'),
    (str(ROOT / 'hub' / 'static'), 'hub/static'),
    (str(ROOT / 'hub' / 'hub.json'), 'hub'),
    # 种子数据（只读）：首次启动由 apps/treasury/backend/store.py:ensure_seed()
    # 复制到 exe 旁的 data/ 目录，使离线环境也能立刻看到美债历史曲线
    (str(ROOT / 'data' / 'treasury'), 'seed/treasury'),
]

a = Analysis(
    [str(ROOT / 'hub' / 'server.py')],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Toolbox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # 控制台窗口：显示启动日志 / 按 Ctrl+C 停止
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
