"""打包辅助（macOS）：调用 PyInstaller 按 build_mac.spec 生成 .app。

使用：
    python build_mac.py

前置：macOS 上已 pip install -r requirements.txt 与 pyinstaller。
产物：dist/AI摄影管家.app
"""
import os
import subprocess
import sys


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = os.path.join(here, "build_mac.spec")
    if not sys.platform.startswith("darwin"):
        print("⚠️  build_mac.spec 仅适用于 macOS，当前平台：%s" % sys.platform)
        print("   Windows 请使用：python build.py")
        return 1
    cmd = [sys.executable, "-m", "PyInstaller", spec, "--noconfirm", "--clean"]
    print("运行：", " ".join(cmd))
    subprocess.run(cmd, check=True)
    out = os.path.join(here, "dist", "AI摄影管家.app")
    print("完成，产物位于：%s" % out)
    print("首次打开：在「访达」中右键 AI摄影管家.app →「打开」→「仍要打开」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
