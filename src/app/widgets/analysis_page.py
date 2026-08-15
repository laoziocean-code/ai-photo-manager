"""分析页：运行分析、进度展示（含预计剩余时间）、候选/废片结果表。"""
import os
import subprocess
import sys
import time

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QProgressBar, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from src.app.workers.analysis_worker import AnalysisWorker
from src.config.settings import SettingsManager
from src.core.image_io import make_thumbnail
from src.core.scoring.scorer import grade


def _fmt_eta(seconds: float) -> str:
    """把秒数格式化成「约 X 分 Y 秒 / 约 X 秒」。"""
    s = int(round(seconds))
    if s < 60:
        return f"约 {max(1, s)} 秒"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"约 {m} 分 {sec} 秒"
    h, m = divmod(m, 60)
    return f"约 {h} 时 {m} 分"


def _fmt_duration(seconds: float) -> str:
    """把耗时秒数格式化成「X 分 Y 秒 / X 时 Y 分」。"""
    s = int(round(seconds))
    if s < 60:
        return f"{s} 秒"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m} 分 {sec} 秒"
    h, m = divmod(m, 60)
    return f"{h} 时 {m} 分"


class AnalysisPage(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._summary = None
        self._settings = SettingsManager()
        self._done_box = None
        self._shutdown_scheduled = False
        self._stage = None
        self._stage_start = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        root.addWidget(QLabel("分析", objectName="pageTitle"))
        self._hint = QLabel("在首页选择照片文件夹与输出目录后，点击「开始分析」。")
        self._hint.setObjectName("pageSub")
        root.addWidget(self._hint)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status = QLabel("")
        self._btn_stop = QPushButton("停止")
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.setEnabled(False)
        prog_row = QHBoxLayout()
        prog_row.addWidget(self._status, 1)
        prog_row.addWidget(self._btn_stop)
        root.addWidget(self._progress)
        root.addWidget(self._status)
        root.addLayout(prog_row)

        self._tabs = QTabWidget()
        self._tabs.setVisible(False)
        self._t1_table = self._new_table(
            ["排名", "缩略图", "文件名", "评分", "等级", "分类", "摄影师点评"])
        self._t2_table = self._new_table(
            ["文件名", "评分", "等级", "分类", "摄影师点评"])
        self._t3_table = self._new_table(
            ["文件名", "评分", "等级", "分类", "摄影师点评"])
        self._rej_table = self._new_table(["文件名", "去除原因"])
        self._tabs.addTab(self._t1_table, "精选")
        self._tabs.addTab(self._t2_table, "良好")
        self._tabs.addTab(self._t3_table, "普通")
        self._tabs.addTab(self._rej_table, "废片")
        root.addWidget(self._tabs, 1)

        self._btn_report = QPushButton("在浏览器打开报告")
        self._btn_report.setObjectName("primaryBtn")
        self._btn_report.setEnabled(False)
        self._btn_report.clicked.connect(self._open_report)
        self._btn_folder = QPushButton("打开输出文件夹")
        self._btn_folder.setEnabled(False)
        self._btn_folder.clicked.connect(self._open_folder)
        act = QHBoxLayout()
        act.addStretch(1)
        act.addWidget(self._btn_folder)
        act.addWidget(self._btn_report)
        root.addLayout(act)

    def _new_table(self, headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.verticalHeader().setVisible(False)
        return t

    # ---- 由 MainWindow 调用 ----
    def start(self, model_id, api_key, input_dir, output_dir, top_n, model_override="",
              options=None):
        self._summary = None
        self._stage = None
        self._stage_start = None
        self._tabs.setVisible(False)
        self._progress.setValue(0)
        self._status.setText("准备中…")
        self._btn_stop.setEnabled(True)
        self._btn_report.setEnabled(False)
        self._btn_folder.setEnabled(False)
        self._worker = AnalysisWorker(model_id, api_key, input_dir, output_dir, top_n,
                                      options=options, model_override=model_override)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._status.setText("正在停止…")

    def _on_progress(self, stage, cur, total, msg):
        pct = int(cur / total * 100) if total else 0
        self._progress.setValue(pct)
        now = time.time()
        if stage != self._stage:
            self._stage = stage
            self._stage_start = now
        elapsed = now - (self._stage_start or now)
        remain = total - cur
        # 预处理/AI 两阶段均显示预计剩余时间（预处理含 RAW 解码，可能较慢）
        if stage in ("preprocess", "ai") and cur > 0 and elapsed > 1.0 and remain > 0:
            eta = elapsed / cur * remain
            self._status.setText(f"{msg} · 预计剩余 {_fmt_eta(eta)}")
            return
        self._status.setText(msg)

    def _on_error(self, msg):
        self._status.setText("错误：" + msg)
        self._btn_stop.setEnabled(False)
        self._notify_analyzing(False)

    def _on_finished(self, summary):
        self._summary = summary
        self._btn_stop.setEnabled(False)
        self._progress.setValue(100)
        # 完成状态附带统计：耗时 / Token / 节省人工时间
        parts = []
        if summary.get("duration_sec"):
            parts.append(f"耗时 {_fmt_duration(summary['duration_sec'])}")
        tokens = summary.get("tokens") or {}
        if tokens.get("total"):
            parts.append(f"Token {tokens['total']}")
        if summary.get("saved_time"):
            parts.append(f"节省人工 {summary['saved_time']}")
        self._status.setText("完成 ✅" + (" · " + " · ".join(parts) if parts else ""))
        self._populate(summary)
        self._tabs.setVisible(True)
        self._btn_report.setEnabled(True)
        self._btn_folder.setEnabled(True)
        self._record_history(summary)
        self._notify_analyzing(False)
        mw = self.window()
        if hasattr(mw, "set_summary"):
            mw.set_summary(summary)
        self._notify_complete(summary)

    def _notify_analyzing(self, busy: bool):
        mw = self.window()
        if hasattr(mw, "set_analyzing"):
            mw.set_analyzing(busy)

    # ---- 完成提醒（弹窗 + 声音）与自动关机 ----
    def _notify_complete(self, summary):
        notify = self._settings.get_notify_on_finish()
        shutdown = self._settings.get_auto_shutdown()
        if not notify and not shutdown:
            return
        # 跨平台提示音：Qt 的 beep() 在 Windows/macOS/Linux 均可用
        try:
            QApplication.beep()
        except Exception:
            pass
        self._shutdown_scheduled = False
        if shutdown:
            self._shutdown_scheduled = self._schedule_shutdown()
        if notify or self._shutdown_scheduled:
            self._show_done_box(self._shutdown_scheduled)

    def _schedule_shutdown(self) -> bool:
        """安排分析完成后自动关机，返回是否成功安排。

        - Windows：直接调用系统 shutdown 命令（60 秒后关机）。
        - macOS / Linux：无可靠且无侵入的等效命令（静默关机需 root 权限，
          且容易误关用户其它工作），此处安全降级为「不执行关机」，
          仅保留完成提醒。
        """
        if sys.platform.startswith("win32"):
            try:
                subprocess.Popen([
                    "shutdown", "/s", "/t", "60",
                    "/c", "AI摄影管家：分析完成，系统将在 60 秒后关机。",
                ])
                return True
            except Exception:
                return False
        return False

    def _show_done_box(self, shutdown):
        n = (len(self._summary.get("tier1", [])) +
             len(self._summary.get("tier2", [])) +
             len(self._summary.get("tier3", [])) +
             len(self._summary.get("rejected", [])))
        picked = len(self._summary.get("tier1", []))
        box = QMessageBox(self)
        box.setWindowTitle("分析完成")
        box.setIcon(QMessageBox.Information)
        box.setText(f"分析完成！共分析 {n} 张，精选 {picked} 张。")
        box.setStandardButtons(QMessageBox.Ok)
        if shutdown:
            box.setInformativeText("系统将在 60 秒后自动关机，可点「取消关机」撤销。")
            cancel = box.addButton("取消关机", QMessageBox.ActionRole)
            cancel.clicked.connect(self._cancel_shutdown)
        self._done_box = box
        box.show()

    def _cancel_shutdown(self):
        if sys.platform.startswith("win32"):
            try:
                subprocess.run(["shutdown", "/a"], timeout=10)
            except Exception:
                pass

    def _record_history(self, summary):
        from src.config.models_config import get_preset
        from src.config.settings import SettingsManager
        report = os.path.join(summary.get("output_dir", ""), "摄影报告.html")
        if not os.path.exists(report):
            return
        folder = summary.get("input_dir") or os.path.dirname(summary.get("output_dir", ""))
        preset = get_preset(summary.get("model_id", "glm-vision"))
        model = preset.get("name", "模型")
        tier1 = summary.get("tier1", [])
        tier2 = summary.get("tier2", [])
        tier3 = summary.get("tier3", [])
        total = len(tier1) + len(tier2) + len(tier3) + len(summary.get("rejected", []))
        SettingsManager().add_recent_report(
            folder, report,
            total=total,
            picked=len(tier1),
            dedup_count=summary.get("dedup_count", 0),
            model_name=model,
        )

    def _populate(self, summary):
        tier1 = summary.get("tier1", [])
        tier2 = summary.get("tier2", [])
        tier3 = summary.get("tier3", [])
        rejected = summary.get("rejected", [])

        self._fill_t1(self._t1_table, tier1)
        self._fill_thin(self._t2_table, tier2)
        self._fill_thin(self._t3_table, tier3)

        rt = self._rej_table
        rt.setRowCount(len(rejected))
        for i, rec in enumerate(rejected):
            rt.setItem(i, 0, QTableWidgetItem(rec.name))
            rt.setItem(i, 1, QTableWidgetItem(rec.reject_reason))
        rt.setColumnWidth(0, 200)
        rt.setColumnWidth(1, 520)

        self._tabs.setTabText(0, f"精选（{len(tier1)}）")
        self._tabs.setTabText(1, f"良好（{len(tier2)}）")
        self._tabs.setTabText(2, f"普通（{len(tier3)}）")
        self._tabs.setTabText(3, f"废片（{len(rejected)}）")

    def _fill_t1(self, t, recs):
        t.setRowCount(len(recs))
        for i, rec in enumerate(recs):
            t.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            thumb = make_thumbnail(rec.path, size=120)
            lbl = QLabel()
            if thumb:
                pm = QPixmap()
                pm.loadFromData(thumb)
                lbl.setPixmap(pm.scaled(100, 75, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            t.setCellWidget(i, 1, lbl)
            t.setItem(i, 2, QTableWidgetItem(rec.name))
            t.setItem(i, 3, QTableWidgetItem(str(round(rec.total_score, 1))))
            t.setItem(i, 4, QTableWidgetItem(grade(rec.total_score)))
            t.setItem(i, 5, QTableWidgetItem(rec.ai.get("category", "")))
            t.setItem(i, 6, QTableWidgetItem((rec.ai.get("review", "") or "")[:80]))
            t.setRowHeight(i, 84)
        t.setColumnWidth(0, 50)
        t.setColumnWidth(1, 110)
        t.setColumnWidth(2, 180)
        t.setColumnWidth(3, 60)
        t.setColumnWidth(4, 50)
        t.setColumnWidth(5, 80)
        t.setColumnWidth(6, 420)

    def _fill_thin(self, t, recs):
        t.setRowCount(len(recs))
        for i, rec in enumerate(recs):
            t.setItem(i, 0, QTableWidgetItem(rec.name))
            t.setItem(i, 1, QTableWidgetItem(str(round(rec.total_score, 1))))
            t.setItem(i, 2, QTableWidgetItem(grade(rec.total_score)))
            t.setItem(i, 3, QTableWidgetItem(rec.ai.get("category", "")))
            t.setItem(i, 4, QTableWidgetItem((rec.ai.get("review", "") or "")[:80]))
        t.setColumnWidth(0, 220)
        t.setColumnWidth(1, 60)
        t.setColumnWidth(2, 50)
        t.setColumnWidth(3, 80)
        t.setColumnWidth(4, 480)

    def _open_report(self):
        if not self._summary:
            return
        path = os.path.join(self._summary["output_dir"], "摄影报告.html")
        if os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _open_folder(self):
        if not self._summary:
            return
        d = self._summary["output_dir"]
        if os.path.isdir(d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
