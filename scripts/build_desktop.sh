#!/usr/bin/env bash
# LifeVault Desktop 构建脚本（Linux / macOS）
#
# 串联三个步骤：
#   1. Nuxt 前端构建 → frontend/.output/public
#   2. PyInstaller 后端打包 → backend/dist/lifevault-backend
#   3. electron-builder → desktop/release/LifeVault-x.y.z.<dmg|AppImage|deb>
#
# 用法：
#   ./scripts/build_desktop.sh                # 全量构建（自动按平台选择 target）
#   ./scripts/build_desktop.sh --skip-frontend
#   ./scripts/build_desktop.sh --skip-backend
#   ./scripts/build_desktop.sh --skip-bundle  # 仅 staging，不重新构建前端/后端
#
# 依赖：Python 3.11+、Node 20+、PyInstaller

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$REPO_ROOT/frontend"
BACKEND="$REPO_ROOT/backend"
DESKTOP="$REPO_ROOT/desktop"

SKIP_FRONTEND=0
SKIP_BACKEND=0
SKIP_BUNDLE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-frontend) SKIP_FRONTEND=1; shift ;;
    --skip-backend)  SKIP_BACKEND=1;  shift ;;
    --skip-bundle)   SKIP_BUNDLE=1;   shift ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

# 自动按当前平台选择 electron-builder target
case "$(uname -s)" in
  Darwin) TARGET="mac" ;;
  Linux)  TARGET="linux" ;;
  *) echo "unsupported platform: $(uname -s)"; exit 1 ;;
esac

step() { printf '\n\033[36m=== %s ===\033[0m\n' "$1"; }
ok()   { printf '\033[32mOK: %s\033[0m\n' "$1"; }
die()  { printf '\033[31mFAIL: %s\033[0m\n' "$1"; exit 1; }

# --- 1. 前端构建 ------------------------------------------------------------
if [[ $SKIP_FRONTEND -eq 0 && $SKIP_BUNDLE -eq 0 ]]; then
  step "Building Nuxt frontend"
  cd "$FRONTEND"
  [[ -d node_modules ]] || npm install
  NUXT_PUBLIC_API_BASE="" npm run build
  ok "frontend built to .output/public"
fi

# --- 2. 后端 PyInstaller 打包 -----------------------------------------------
if [[ $SKIP_BACKEND -eq 0 && $SKIP_BUNDLE -eq 0 ]]; then
  step "Building backend with PyInstaller"
  cd "$BACKEND"
  python -m pip install --quiet pyinstaller
  python -m pip install --quiet -e .
  python -m PyInstaller lifevault-backend.spec --clean --noconfirm --log-level WARN
  [[ -f dist/lifevault-backend ]] || die "lifevault-backend not produced"
  ok "backend packaged"
fi

# --- 3. 复制产物到 desktop/resources ----------------------------------------
step "Staging resources for electron-builder"
RES_BACKEND="$DESKTOP/resources/backend"
RES_FRONTEND="$DESKTOP/resources/frontend"
rm -rf "$RES_BACKEND" "$RES_FRONTEND"
mkdir -p "$RES_BACKEND" "$RES_FRONTEND"

BACKEND_BIN="$BACKEND/dist/lifevault-backend"
[[ -f "$BACKEND_BIN" ]] || die "missing $BACKEND_BIN - run without --skip-backend first"
cp "$BACKEND_BIN" "$RES_BACKEND/"
chmod +x "$RES_BACKEND/lifevault-backend"
ok "backend binary staged"

FRONTEND_PUBLIC="$FRONTEND/.output/public"
[[ -d "$FRONTEND_PUBLIC" ]] || die "missing $FRONTEND_PUBLIC - run without --skip-frontend first"
cp -r "$FRONTEND_PUBLIC/." "$RES_FRONTEND/"
ok "frontend staged"

# --- 4. electron-builder 打包 ----------------------------------------------
if [[ $SKIP_BUNDLE -eq 0 ]]; then
  step "Running electron-builder ($TARGET)"
  cd "$DESKTOP"
  [[ -d node_modules ]] || npm install
  npx tsc -p tsconfig.json
  # 国内网络环境下，GitHub 下载 electron 二进制常超时；
  # 优先用 npmmirror 镜像，若已设则尊重用户配置
  export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"
  export ELECTRON_BUILDER_BINARIES_MIRROR="${ELECTRON_BUILDER_BINARIES_MIRROR:-https://npmmirror.com/mirrors/electron-builder-binaries/}"
  # 本项目不代码签名
  export CSC_IDENTITY_AUTO_DISCOVERY=false
  # 关键：清除 ELECTRON_RUN_AS_NODE，否则 electron 以纯 Node 模式运行（app 为 undefined）
  unset ELECTRON_RUN_AS_NODE
  npx electron-builder --"$TARGET"
  ok "bundle produced in desktop/dist-release/"
fi

step "Done"
echo "产物位置: $DESKTOP/dist-release/"
ls -lh "$DESKTOP/dist-release/" 2>/dev/null || true
