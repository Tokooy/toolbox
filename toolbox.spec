# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  Toolbox 工具台 · PyInstaller 打包配置（Windows 单文件 exe）v1.0
#  用法：pyinstaller --clean --noconfirm toolbox.spec
#  产物：dist/Toolbox.exe
#
#  设计说明（与 hub/server.py 的 FROZEN 分支配套）：
#    * 代码资源（hub/static、features.json、generate_qrcodes.py、treasury/server.py）
#      打进 exe，运行期从 _MEIPASS 解包目录读取（只读）；
#    * 可变数据（二维码 input/output、美债缓存）由 hub 运行时重定向到
#      exe 旁的持久目录，不落在 _MEIPASS 中。
# ============================================================

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# 二维码批量生成依赖（generate_qrcodes.py 在运行时才 import，
# 需显式收集：qrcode / Pillow / openpyxl 及其数据与动态库。
# 注：qrcode 走 Pillow 图片工厂（PilImage），无需 pypng）
for pkg in ('qrcode', 'PIL', 'openpyxl', 'et_xmlfile'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 应用自带资源：静态前端、功能注册表、供运行时动态加载的两个脚本
datas += [
    ('hub/static', 'hub/static'),
    ('hub/features.json', 'hub'),
    ('QRcode/generate_qrcodes.py', 'QRcode'),
    ('us-treasury-yields/server.py', 'us-treasury-yields'),
]

a = Analysis(
    ['hub/server.py'],
    pathex=[],
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
