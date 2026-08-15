#!/usr/bin/env bash
# 在 macOS 上把 src/assets/logo.png 转成 macOS 应用图标 src/assets/logo.icns
# 用法：bash make_icns.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/src/assets/logo.png"
OUT="$HERE/src/assets/logo.icns"

if [ ! -f "$SRC" ]; then
  echo "找不到 $SRC，请确认资源存在。" >&2
  exit 1
fi

TMP="$(mktemp -d)"
ICONSET="$TMP/logo.iconset"
mkdir -p "$ICONSET"

# 生成各尺寸（含 Retina 2x），覆盖 .icns 需要的全部槽位
for sz in 16 32 64 128 256 512; do
  dbl=$((sz * 2))
  sips -z "$sz" "$sz"     "$SRC" --out "$ICONSET/icon_${sz}x${sz}.png"
  sips -z "$dbl" "$dbl"   "$SRC" --out "$ICONSET/icon_${sz}x${sz}@2x.png"
done

iconutil --convert icns "$ICONSET" -o "$OUT"
rm -rf "$TMP"
echo "已生成 $OUT"
