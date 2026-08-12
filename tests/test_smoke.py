"""骨架冒烟测试：在无显示环境下构造主窗口，验证导入与构建无误。

运行：
    python -m pytest tests/test_smoke.py
（CI / 无界面环境会自动使用 offscreen 平台）
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow


def test_window_constructs():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    window.close()
    assert window is not None
