"""报告页：当前报告统计 + 最近分析历史（可快速重开报告/文件夹）。"""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from src.config.settings import SettingsManager


class ReportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._summary = None
        self._settings = SettingsManager()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)
        root.addWidget(QLabel("报告", objectName="pageTitle"))

        self._stats = QGridLayout()
        root.addLayout(self._stats)

        self._history = QListWidget()
        self._history.setMaximumHeight(220)
        self._history.itemDoubleClicked.connect(lambda it: self._open_report(it))
        root.addWidget(self._history)

        hbtns = QHBoxLayout()
        hbtns.addWidget(QLabel("最近分析：双击或选择后打开", objectName="pageSub"))
        hbtns.addStretch(1)
        btn_clear = QPushButton("清除历史")
        btn_clear.clicked.connect(self._clear_history)
        hbtns.addWidget(btn_clear)
        root.addLayout(hbtns)

        root.addStretch(1)

        self._btn_report = QPushButton("在浏览器打开报告")
        self._btn_report.setObjectName("primaryBtn")
        self._btn_report.setEnabled(False)
        self._btn_report.clicked.connect(lambda: self._open_report(self._history.currentItem()))
        self._btn_folder = QPushButton("打开精选文件夹")
        self._btn_folder.setEnabled(False)
        self._btn_folder.clicked.connect(self._open_current_folder)
        act = QHBoxLayout()
        act.addStretch(1)
        act.addWidget(self._btn_folder)
        act.addWidget(self._btn_report)
        root.addLayout(act)

    def refresh(self):
        self._reload_history()
        while self._stats.count():
            item = self._stats.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not self._summary:
            self._stats.addWidget(QLabel("尚无报告。请先在首页开始分析。"), 0, 0)
            self._btn_report.setEnabled(False)
            self._btn_folder.setEnabled(False)
            return
        tier1 = self._summary.get("tier1", [])
        tier2 = self._summary.get("tier2", [])
        tier3 = self._summary.get("tier3", [])
        rejected = self._summary.get("rejected", [])
        total_analyzed = len(tier1) + len(tier2) + len(tier3) + len(rejected)
        all_scored = tier1 + tier2 + tier3
        avg = round(sum(r.total_score for r in all_scored) / len(all_scored), 1) if all_scored else 0
        items = [
            ("分析照片", total_analyzed),
            ("精选", len(tier1)),
            ("良好", len(tier2)),
            ("普通", len(tier3)),
            ("废片", len(rejected)),
            ("平均分", avg),
        ]
        if self._summary.get("dedup_count"):
            items.insert(1, ("自动去重", self._summary["dedup_count"]))
        for i, (k, v) in enumerate(items):
            self._stats.addWidget(
                QLabel(f"<b style='font-size:24px;color:#E07B39'>{v}</b><br>"
                       f"<span style='color:#A59787;font-size:13px'>{k}</span>"),
                0, i)
        self._btn_report.setEnabled(True)
        self._btn_folder.setEnabled(True)

    def set_summary(self, summary):
        self._summary = summary
        self.refresh()

    def _reload_history(self):
        self._history.clear()
        for entry in self._settings.get_recent_reports():
            if not os.path.exists(entry.get("report", "")):
                continue
            dedup = f" / 去重 {entry['dedup']}" if entry.get("dedup") else ""
            text = (f"{entry['time']} · {entry.get('folder', '')} · "
                    f"{entry.get('total', 0)} 张，精选 {entry.get('picked', 0)}{dedup}")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry)
            item.setToolTip(entry.get("report", ""))
            self._history.addItem(item)

    def _clear_history(self):
        if not self._history.count():
            return
        if QMessageBox.question(self, "清除历史", "确定清空最近分析记录？") == QMessageBox.Yes:
            self._settings.clear_recent_reports()
            self._reload_history()

    # ---- 打开 ----
    def _entry_report(self, item):
        if item is None:
            return None
        entry = item.data(Qt.UserRole)
        return entry.get("report") if entry else None

    def _open_report(self, item):
        path = self._entry_report(item)
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _open_current_folder(self):
        if self._summary:
            d = os.path.join(self._summary["output_dir"], "AI精选")
            if os.path.isdir(d):
                QDesktopServices.openUrl(QUrl.fromLocalFile(d))
                return
        item = self._history.currentItem()
        path = self._entry_report(item)
        if path:
            d = os.path.join(os.path.dirname(path), "AI精选")
            if not os.path.isdir(d):
                d = os.path.dirname(path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
