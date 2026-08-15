#!/usr/bin/env bash
# 在 macOS 上构建 .app 并生成可分发 .dmg（含「前往 Applications」快捷方式）
# 前置：pip install -r requirements.txt pyinstaller
# 用法：bash package_dmg.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

APP_NAME="AI摄影管家"
APP_PATH="dist/$APP_NAME.app"
DMG_NAME="$APP_NAME.dmg"
DMG_PATH="dist/$DMG_NAME"

# 0) 图标缺失则先生成
if [ ! -f "src/assets/logo.icns" ]; then
  bash make_icns.sh
fi

# 1) 构建 .app
python3 build_mac.py

# 2) 制作 .dmg（先放入 .app 与 Applications 快捷方式，再转换为压缩镜像）
STAGE="dist/dmg_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP_PATH" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

if [ -f "$DMG_PATH" ]; then rm -f "$DMG_PATH"; fi
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG_PATH"
rm -rf "$STAGE"

echo "完成：$DMG_PATH"
