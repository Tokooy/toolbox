#!/usr/bin/env bash
# ============================================================
#  Toolbox 工具台 · 一键安装（Linux / macOS）
#   ① 创建 conda 环境 self_ag 并安装依赖（二维码生成所需）
#   ② 安装桌面快捷方式与应用菜单项（双击即可启动）
#
#  用法：bash packaging/linux/install.sh
# ============================================================
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
ENV_NAME="self_ag"
LAUNCHER="$HERE/启动.sh"

echo ""
echo "  ═══════════════════════════════════════════════"
echo "   Toolbox 工具台 · 安装向导"
echo "   仓库目录：$REPO_ROOT"
echo "  ═══════════════════════════════════════════════"
echo ""

# ---------- ① conda 环境 ----------
if ! command -v conda >/dev/null 2>&1; then
  echo "  ✗ 未找到 conda，请先安装 Miniconda/Anaconda："
  echo "    https://docs.conda.io/en/latest/miniconda.html"
  echo "  （若只想跑美债看板 / 工具台本体，直接用系统 python 运行也可以——它们零第三方依赖）"
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
chmod +x "$LAUNCHER"

make_desktop_file() {
  cat > "$1" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Toolbox 工具台
Name[zh_CN]=Toolbox 工具台
Comment=多功能本地工具集 · 美债收益率 / 二维码生成
Exec=$LAUNCHER
Icon=$HERE/icon.svg
Terminal=true
Categories=Utility;Office;
EOF
  chmod +x "$1"
}

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
make_desktop_file "$APPS_DIR/toolbox.desktop"

# 桌面副本（GNOME 需要标记为可信才能双击运行）
if [ -d "$HOME/Desktop" ]; then
  make_desktop_file "$HOME/Desktop/Toolbox工具台.desktop"
  if command -v gio >/dev/null 2>&1; then
    gio set "$HOME/Desktop/Toolbox工具台.desktop" metadata::trusted true 2>/dev/null || true
  fi
fi
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo ""
echo "  ✓ 桌面快捷方式已安装："
echo "    · 桌面图标  「Toolbox 工具台」"
echo "    · 应用菜单  （GNOME 搜索「Toolbox」）"
echo ""
echo "  ▶ 现在可以双击桌面图标启动；或命令行运行："
echo "      bash \"$LAUNCHER\""
echo ""
echo "  安装完成！"
echo "  ═══════════════════════════════════════════════"
