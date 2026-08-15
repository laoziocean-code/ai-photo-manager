# -*- coding: utf-8 -*-
"""AI摄影管家 - 应用入口。

运行方式（在项目根目录）:
    python -m src.main

图标策略（确保 Windows 任务栏/标题栏显示金色光圈 Logo）：
1. EXE 资源级图标由 build_exe.spec 中的 icon=logo.ico 设置（Windows 资源层）。
2. 运行时再通过 QApplication + MainWindow 显式 setWindowIcon，确保标题栏显示金色光圈。
3. PyInstaller frozen 时优先用 sys._MEIPASS 定位资产；非 frozen 用 __file__。
4. 优先 ICO（Windows 任务栏最佳兼容性），缺失时回退 PNG。
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow
from src.app.styles.theme import load_stylesheet


def _asset_root() -> str:
    """资产根目录：frozen 下是 _MEIPASS，否则用 __file__ 所在目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and os.path.isdir(meipass):
        return os.path.join(meipass, "src")
    return os.path.dirname(os.path.abspath(__file__))


def _asset(name: str) -> str:
    """资产绝对路径。"""
    return os.path.join(_asset_root(), "assets", name)


def _pick_icon() -> str | None:
    """跨平台图标选择：macOS 优先 .icns，其余优先 .ico，缺失回退 PNG。"""
    if sys.platform == "darwin":
        order = ("logo.icns", "logo.png", "logo.ico")
    else:
        order = ("logo.ico", "logo.png", "logo.icns")
    for name in order:
        p = _asset(name)
        if os.path.exists(p):
            return p
    return None


def _setup_hidpi(app: QApplication):
    """Retina / 高分屏适配（跨平台，macOS 必需）。

    Qt6 默认已开启高 DPI 缩放；这里补充缩放系数取整策略，
    避免非整数倍缩放时界面发虚或布局错位。属性不存在时静默跳过，
    不影响旧版本运行。
    """
    try:
        if hasattr(Qt, "AA_EnableHighDpiScaling"):
            app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
            app.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass


def create_app(argv) -> QApplication:
    app = QApplication(argv)
    _setup_hidpi(app)
    app.setApplicationName("AI摄影管家")
    app.setApplicationDisplayName("AI摄影管家")
    app.setOrganizationName("AIStudio")
    app.setDesktopFileName("AI摄影管家")  # 让 Windows 任务栏正确分组

    icon_path = _pick_icon()
    if icon_path:
        # 优先 256 高清图（ICO 多尺寸会自动选）；PNG/ICNS fallback Qt 用内置解码器
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
    app.setStyleSheet(load_stylesheet())
    return app


def main():
    app = create_app(sys.argv)
    window = MainWindow()

    icon_path = _pick_icon()
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))

    # 关键：在 show() 之前设置 ApplicationDisplayName 让任务栏识别
    window.show()
    # 二次保险：show 之后再设一次（部分 Windows 版本只在 show 后取图标）
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()