# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（单文件 EXE）。

构建：
    python build.py

产物：dist/AI摄影管家.exe
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


def _rawpy_dlls():
    """rawpy 在 Windows 自带 raw_r.dll / vcomp140.dll，需显式打进 rawpy/ 目录，
    否则冻结后 _rawpy.pyd 加载时会报找不到 DLL。"""
    try:
        import rawpy as _rp
        import os as _os
        pkg = _os.path.dirname(_rp.__file__)
        out = []
        for n in ("raw_r.dll", "vcomp140.dll"):
            p = _os.path.join(pkg, n)
            if _os.path.exists(p):
                out.append((p, "rawpy"))
        return out
    except Exception:
        return []


a = Analysis(
    [os.path.join(APP_DIR, "src", "main.py")],
    pathex=[APP_DIR],
    binaries=_rawpy_dlls(),
    datas=[
        (os.path.join(APP_DIR, "src", "app", "styles", "theme.qss"), "src/app/styles"),
        (os.path.join(APP_DIR, "src", "core", "report", "templates"), "src/core/report/templates"),
        (os.path.join(APP_DIR, "src", "assets"), "src/assets"),
    ],
    hiddenimports=[
        "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
        "openai", "anthropic", "cv2", "PIL", "imagehash", "jinja2", "cryptography",
        "rawpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# --- 修正 OpenSSL DLL（关键修复）---
# PyInstaller 在沙箱里会把 _ssl.pyd 依赖的 libcrypto/libssl 误收集成 WorkBuddy
# 自带的 Git(MinGW) 版本；它与官方 Python(MSVC) 编译的 _ssl.pyd ABI 不兼容，
# 运行 EXE 时就会报 "DLL load failed while importing _ssl"。
# 这里强制把这两个 DLL 的来源替换为 Python 安装目录里官方编译的那一份。
try:
    import _ssl as _ssl_mod
    _ssl_dir = os.path.dirname(_ssl_mod.__file__)
except Exception:
    _ssl_dir = os.path.join(os.path.dirname(sys.executable), "DLLs")
_openssl_want = {"libcrypto-3-x64.dll", "libssl-3-x64.dll"}
_openssl_fixed = {}
for _n in _openssl_want:
    _p = os.path.join(_ssl_dir, _n)
    if os.path.exists(_p):
        _openssl_fixed[_n] = _p
    else:
        # 兜底：在受管 Python 版本目录里找
        _alt = os.path.join(
            os.path.dirname(os.path.dirname(sys.executable)),
            "versions", "3.13.12", "DLLs", _n)
        if os.path.exists(_alt):
            _openssl_fixed[_n] = _alt
if _openssl_fixed:
    for _i, _entry in enumerate(a.binaries):
        if isinstance(_entry, (tuple, list)) and len(_entry) >= 2:
            _name = _entry[0]
            if _name in _openssl_fixed:
                _src = _entry[1]
                if os.path.normcase(_src) != os.path.normcase(_openssl_fixed[_name]):
                    if len(_entry) >= 3:
                        a.binaries[_i] = (_name, _openssl_fixed[_name], _entry[2])
                    else:
                        a.binaries[_i] = (_name, _openssl_fixed[_name])

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AI摄影管家",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=["libcrypto-3-x64.dll", "libssl-3-x64.dll"],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(APP_DIR, "src", "assets", "logo.ico"),
    version=os.path.join(APP_DIR, "version_info.txt"),
)
