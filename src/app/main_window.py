"""主窗口：左侧导航 + 右侧堆叠页面（首页 / 分析 / 报告）。"""
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QLabel,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from src.app.widgets.home_page import HomePage
from src.app.widgets.analysis_page import AnalysisPage
from src.app.widgets.report_page import ReportPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._last_summary = None
        self.setWindowTitle("AI摄影管家")
        self.resize(1100, 720)
        self._build_ui()

    def _build_ui(self):
        central = QFrame()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 24, 16, 16)
        sb.addWidget(QLabel("AI摄影管家", objectName="appTitle"))
        self._nav = QListWidget()
        self._nav.addItems(["首页", "分析", "报告"])
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._switch_page)
        sb.addWidget(self._nav)
        sb.addStretch(1)
        root.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._home = HomePage()
        self._analysis = AnalysisPage()
        self._report = ReportPage()
        self._stack.addWidget(self._home)
        self._stack.addWidget(self._analysis)
        self._stack.addWidget(self._report)
        root.addWidget(self._stack)

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        if idx == 2:  # 进入报告页时刷新统计
            self._report.refresh()

    # ---- 跨页面协作 ----
    def start_analysis(self, model_id, api_key, input_dir, output_dir, top_n=10,
                       model_override="", options=None):
        self._stack.setCurrentIndex(1)
        self._home.set_analyzing(True)
        self._analysis.start(model_id, api_key, input_dir, output_dir, top_n,
                             model_override, options)

    def set_summary(self, summary):
        self._last_summary = summary
        self._report.set_summary(summary)

    def set_analyzing(self, busy: bool):
        self._home.set_analyzing(busy)
