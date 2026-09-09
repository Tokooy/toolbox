@echo off
chcp 65001 >nul
rem ============================================================
rem  Toolbox 工具台 · Windows 一键构建脚本
rem  生成单文件 Toolbox.exe（PyInstaller onefile，自带运行环境）
rem
rem  前提：本机已安装 Python 3.8+（推荐 conda/miniconda 环境）
rem  用法：双击本脚本，或在命令行执行  build_windows.bat
rem  产物：dist\Toolbox.exe
rem ============================================================
setlocal
cd /d "%~dp0"

echo.
echo  ════════════════════════════════════════════════════════
echo   Toolbox 工具台 · Windows 构建向导
echo  ════════════════════════════════════════════════════════

echo.
echo  [1/3] 检查并安装构建依赖（pyinstaller / qrcode / pillow / openpyxl）...
python -m pip install --upgrade pyinstaller "qrcode[pil]" pillow openpyxl
if errorlevel 1 goto :err

echo.
echo  [2/3] 使用 toolbox.spec 打包单文件 exe（onefile）...
pyinstaller --clean --noconfirm toolbox.spec
if errorlevel 1 goto :err

echo.
echo  [3/3] 完成！
echo.
echo  ════════════════════════════════════════════════════════
echo   ✓ exe 已生成：dist\Toolbox.exe
echo.
echo   使用方式：
echo     · 双击 Toolbox.exe 即启动，浏览器自动打开 http://127.0.0.1:8080
echo     · 数据目录会自动建立在 exe 同目录：
echo         - QRcode\input      放待处理的 Excel
echo         - QRcode\output     生成的 HTML / Excel
echo         - us-treasury-yields\data   美债数据缓存
echo     · 若把 exe 放在本仓库根目录旁，将直接复用仓库内现有数据目录
echo     · 停止服务：在 exe 控制台窗口按 Ctrl+C
echo  ════════════════════════════════════════════════════════
echo.
pause
exit /b 0

:err
echo.
echo  ✗ 构建失败，请检查上方错误信息后重试。
pause
exit /b 1
