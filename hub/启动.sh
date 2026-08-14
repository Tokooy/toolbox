#!/usr/bin/env bash
# ============================================================
#  Toolbox 工具台 · 一键启动（命令行 / 双击桌面图标均可用）
#  自动激活 conda 环境 self_ag 并启动服务、打开浏览器
# ============================================================
set -u

HUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="self_ag"

cd "$HUB_DIR"

# 1) 定位 conda
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
if [ -n "$CONDA_BASE" ]; then
  ENV_PY="$CONDA_BASE/envs/$ENV_NAME/bin/python"
fi

# 2) 环境不存在则提示安装
if [ -z "$ENV_PY" ] || [ ! -x "$ENV_PY" ]; then
  echo ""
  echo "  ✗ 未找到 conda 环境「$ENV_NAME」。"
  echo "    请先运行一次安装脚本完成环境创建："
  echo "      bash \"$HUB_DIR/install.sh\""
  echo ""
  read -r -p "  按回车键退出..." _
  exit 1
fi

# 3) 端口占用检测：若服务已在运行则直接打开浏览器
PORT="${PORT:-8080}"
if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then
  echo "  ✓ 服务已在运行，直接打开浏览器…"
  xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1 &
  sleep 1
  exit 0
fi

# 4) 启动服务（Ctrl+C 停止）
echo ""
echo "  ═══════════════════════════════════════════════"
echo "   Toolbox 工具台 正在启动（conda 环境: $ENV_NAME）"
echo "   浏览器将自动打开；如需停止请在本窗口按 Ctrl+C"
echo "   提示：美债数据若无法连接 FRED，可先执行"
echo "         export HTTPS_PROXY=http://127.0.0.1:7890"
echo "         再重新启动本脚本"
echo "  ═══════════════════════════════════════════════"
echo ""
exec "$ENV_PY" server.py
