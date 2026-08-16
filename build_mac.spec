# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（macOS .app）。

构建（在 macOS 上，需先 pip install -r requirements.txt 与 pyinstaller）：
    python build_mac.py

产物：dist/AI摄影管家.app

说明：
- 采用 onedir + BUNDLE 生成标准 .app 包，启动快、体验好。
- rawpy 在 macOS 上自带 libraw 动态库，PyInstaller 自带 rawpy hook 通常能自动收集；
  这里再用 collect_dynamic_libs 做双保险。
- 图标优先 logo.icns，缺失时回退 logo.png（macOS 下 png 也可作为 .app 图标）。
- 不签名（codesign_identity=None）：首次打开需在「访达」右键 → 打开，或在
  「系统设置 → 隐私与安全性」点击「仍要打开」。如需分发，请自行用 Apple Developer
  证书签名并公证（notarytool）。
- 不含 Windows 专有的 version_info.txt / OpenSSL DLL 修复逻辑。
"""
import os
import sys


def _app_dir():
    """兼容 `pyinstaller x.spec` 与 `python -m PyInstaller x.spec` 两种调用。"""
    try:
        return os.path.dirname(os.path.realpath(__file__))
    except NameError:
        for a in sys.argv:
            if a.endswith(".spec"):
                return os.path.dirname(os.path.realpath(a))
        return os.getcwd()


APP_DIR = _app_dir()


def _collect_rawpy_libs():
    """双保险收集 rawpy 动态库（macOS 上通常为 libraw*.dylib）。"""
    try:
        from PyInstaller.utils.hooks import collect_dynamic_libs
        return collect_dynamic_libs("rawpy")
    except Exception:
        return []


def _icon():
    for name in ("logo.icns", "logo.png", "logo.ico"):
        p = os.path.join(APP_DIR, "src", "assets", name)
        if os.path.exists(p):
            return p
    return None


_icon_path = _icon()

a = Analysis(
    [os.path.join(APP_DIR, "src", "main.py")],
    pathex=[APP_DIR],
    binaries=_collect_rawpy_libs(),
    datas=[
        (os.path.join(APP_DIR, "src", "app", "styles", "theme.qss"), "src/app/styles"),
        (os.path.join(APP_DIR, "src", "core", "report", "templates"), "src/core/report/templates"),
        (os.path.join(APP_DIR, "src", "assets"), "src/assets"),
    ],
    hiddenimports=[
        "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
        "openai", "anthropic", "cv2", "PIL", "jinja2", "cryptography",
        "rawpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI摄影管家",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon_path,
)

app = BUNDLE(
    exe,
    a.binaries,
    a.datas,
    name="AI摄影管家.app",
    icon=_icon_path,
    bundle_identifier="com.aistudio.ai-photo-manager",
    info_plist={
        "CFBundleName": "AI摄影管家",
        "CFBundleDisplayName": "AI摄影管家",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSPhotoLibraryUsageDescription": "需要访问照片以进行 AI 摄影分析。",
        "NSDesktopFolderUsageDescription": "需要访问桌面以读取/导出照片。",
        "NSDocumentsFolderUsageDescription": "需要访问文稿以读取/导出照片。",
    },
)
