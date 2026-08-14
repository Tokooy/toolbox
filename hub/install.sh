#!/usr/bin/env bash
# ============================================================
#  Toolbox 工具台 · 一键安装
#   ① 创建 conda 环境 self_ag 并安装依赖（QRcode 所需）
#   ② 安装桌面快捷方式（可双击启动）
# ============================================================
set -e

HUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="self_ag"

echo ""
echo "  ═══════════════════════════════════════════════"
echo "   Toolbox 工具台 · 安装向导"
echo "  ═══════════════════════════════════════════════"
echo ""

# ---------- ① conda 环境 ----------
if ! command -v conda >/dev/null 2>&1; then
  echo "  ✗ 未找到 conda，请先安装 Miniconda/Anaconda："
  echo "    https://docs.conda.io/en/latest/miniconda.html"
  exit 1
fi

CONDA_BASE="$(conda info --base)"
ENV_PY="$CONDA_BASE/envs/$ENV_NAME/bin/python"

if [ -x "$ENV_PY" ]; then
  echo "  ✓ conda 环境「$ENV_NAME」已存在，跳过创建"
else
  echo "  ▶ 创建 conda 环境「$ENV_NAME」(python 3.11) …"
  conda create -y -n "$ENV_NAME" python=3.11
  echo "  ▶ 安装依赖 qrcode / Pillow / openpyxl …"
  conda run -n "$ENV_NAME" pip install -q "qrcode[pil]" pillow openpyxl
  echo "  ✓ 环境创建完成"
fi

"$ENV_PY" -c "import qrcode, PIL, openpyxl" 2>/dev/null \
  || { echo "  ✗ 依赖检查失败，请重新运行 install.sh"; exit 1; }

# ---------- ② 桌面快捷方式 ----------
DESKTOP_SRC="$HUB_DIR/Toolbox工具台.desktop"
DESKTOP_APP="$HOME/.local/share/applications/toolbox.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_SRC" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Toolbox 工具台
Name[zh_CN]=Toolbox 工具台
Comment=多功能本地工具集 · 美债收益率 / 二维码生成
Exec=$HUB_DIR/启动.sh
Icon=$HUB_DIR/icon.svg
Terminal=true
Categories=Utility;Office;
EOF
chmod +x "$DESKTOP_SRC" "$HUB_DIR/启动.sh"

cp "$DESKTOP_SRC" "$DESKTOP_APP"

# 桌面副本（GNOME 需要标记为可信才能双击运行）
if [ -d "$HOME/Desktop" ]; then
  cp "$DESKTOP_SRC" "$HOME/Desktop/Toolbox工具台.desktop"
  chmod +x "$HOME/Desktop/Toolbox工具台.desktop"
  if command -v gio >/dev/null 2>&1; then
    gio set "$HOME/Desktop/Toolbox工具台.desktop" metadata::trusted true 2>/dev/null || true
  fi
fi
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "  ✓ 桌面快捷方式已安装："
echo "    · 桌面图标  「Toolbox 工具台」"
echo "    · 应用菜单  （GNOME 搜索「Toolbox」）"
echo ""
echo "  ▶ 现在可以双击桌面图标启动；或命令行运行："
echo "      bash \"$HUB_DIR/启动.sh\""
echo ""
echo "  安装完成！"
echo "  ═══════════════════════════════════════════════"
