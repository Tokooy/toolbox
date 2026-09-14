#!/usr/bin/env bash
# ============================================================
#  Toolbox 工具台 · 一键启动（Linux / macOS）
#  命令行、桌面图标、应用菜单都走这个脚本：
#  自动激活 conda 环境 self_ag → 启动服务 → 打开浏览器
# ============================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
ENV_NAME="self_ag"

cd "$REPO_ROOT"

# 1) 定位 conda（找不到就用系统 python；工具台与美债看板零第三方依赖，
#    只有二维码生成需要 qrcode/Pillow/openpyxl）
if command -v conda >/dev/null 2>&1; then
  CONDA_BASE="$(conda info --base 2>/dev/null)"
elif [ -d "$HOME/anaconda3" ]; then
  CONDA_BASE="$HOME/anaconda3"
elif [ -d "$HOME/miniconda3" ]; then
  CONDA_BASE="$HOME/miniconda3"
else
  CONDA_BASE=""
fi

ENV_PY=""
if [ -n "$CONDA_BASE" ] && [ -x "$CONDA_BASE/envs/$ENV_NAME/bin/python" ]; then
  ENV_PY="$CONDA_BASE/envs/$ENV_NAME/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  ENV_PY="$(command -v python3)"
fi

if [ -z "$ENV_PY" ]; then
  echo ""
  echo "  ✗ 既没有 conda 环境「$ENV_NAME」，也没找到 python3。"
  echo "    请先安装 Python 3.9+，或运行一次安装脚本创建环境："
  echo "      bash \"$HERE/install.sh\""
  echo ""
  read -r -p "  按回车键退出..." _
  exit 1
fi

# 2) 端口占用检测：若服务已在运行则直接打开浏览器
PORT="${PORT:-8080}"
if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then
  echo "  ✓ 服务已在运行，直接打开浏览器…"
  xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1 &
  sleep 1
  exit 0
fi

# 3) 启动服务（Ctrl+C 停止）
echo ""
echo "  ═══════════════════════════════════════════════"
echo "   Toolbox 工具台 正在启动"
echo "   Python：$ENV_PY"
echo "   浏览器将自动打开；如需停止请在本窗口按 Ctrl+C"
echo "   提示：美债数据若无法连接 FRED，可先执行"
echo "         export HTTPS_PROXY=http://127.0.0.1:7890"
echo "         再重新启动本脚本"
echo "  ═══════════════════════════════════════════════"
echo ""
exec "$ENV_PY" hub/server.py
