"""打包辅助：调用 PyInstaller 按 build_exe.spec 生成单文件 EXE。"""
import os
import subprocess
import sys


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = os.path.join(here, "build_exe.spec")
    cmd = [sys.executable, "-m", "PyInstaller", spec, "--noconfirm", "--clean"]
    print("运行：", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("完成，产物位于 dist/AI摄影管家.exe")


if __name__ == "__main__":
    main()
