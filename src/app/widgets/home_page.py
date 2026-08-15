"""首页：软件介绍 / 分析参数（去重档位、精选数量、照片与输出目录） / 开始分析。

API Key 与视觉模型配置已收拢到「设置」弹窗；主页右下角仅显示
当前模型名与连通状态（后台线程 ping）。
"""
import os
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.app.widgets.settings_dialog import SettingsDialog
from src.app.workers.ping_worker import PingWorker
from src.config.models_config import MODEL_PRESETS, get_preset
from src.config.settings import SettingsManager
from src.core.preprocessing.deduplication import DEDUP_LEVELS, DEFAULT_DEDUP_LEVEL


class DragDirLineEdit(QLineEdit):
    """支持把文件夹直接拖进来填路径；非文件夹或非本地路径拒绝。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        md = event.mimeData()
        if md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            p = url.toLocalFile()
            if os.path.isdir(p):
                self.setText(p)
                event.acceptProposedAction()
                return
        event.ignore()


class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        self._settings = SettingsManager()
        self._ping_worker = None
        # 已持久化的输出目录 = 用户曾经手动选择过；启动时若非空则视为用户已锁定
        self._out_modified = bool(self._settings.get_output_dir())
        # 程序化设置 _out_edit 文本时设 True，抑制「用户输入」标记
        self._setting_out = False
        self._build_ui()
        self._refresh_ping()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.addWidget(QLabel("AI摄影管家", objectName="pageTitle"))
        header.addStretch(1)
        btn_settings = QPushButton("设置")
        btn_settings.setObjectName("settingsBtn")
        btn_settings.clicked.connect(self._open_settings)
        header.addWidget(btn_settings)
        root.addLayout(header)

        root.addWidget(QLabel("从海量照片中，挑出值得发布的少数精品，并告诉你如何修。", objectName="pageSub"))

        row_dedup = QHBoxLayout()
        row_dedup.addWidget(QLabel("去重强度"))
        self._dedup = QComboBox()
        for level in DEDUP_LEVELS:
            self._dedup.addItem(level, level)
        idx = self._dedup.findData(self._settings.get_dedup_level())
        self._dedup.setCurrentIndex(idx if idx >= 0 else 0)
        self._dedup.currentIndexChanged.connect(
            lambda i: self._settings.set_dedup_level(self._dedup.itemData(i))
        )
        row_dedup.addWidget(self._dedup)
        row_dedup.addWidget(QLabel("越严只去极相似，越宽会去除更多连拍/同场景", objectName="pageSub"))
        row_dedup.addStretch(1)
        root.addLayout(row_dedup)

        row_top = QHBoxLayout()
        row_top.addWidget(QLabel("精选数量"))
        self._top_spin = QSpinBox()
        self._top_spin.setObjectName("topSpin")
        self._top_spin.setRange(3, 50)
        self._top_spin.setValue(10)
        self._top_spin.setSingleStep(1)
        # 直接键盘输入更顺手（拖箭头 / 滚轮只是补充）
        self._top_spin.setKeyboardTracking(False)
        self._top_spin.setAccelerated(True)
        self._top_spin.setFixedWidth(120)
        row_top.addWidget(self._top_spin)
        row_top.addWidget(QLabel("可直接输入数字（3-50），或用上下箭头调整",
                                objectName="pageSub"))
        row_top.addStretch(1)
        root.addLayout(row_top)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("照片文件夹"))
        self._in_edit = DragDirLineEdit()
        self._in_edit.setPlaceholderText("可拖拽文件夹到此处，或点击「选择」")
        self._in_edit.setText(self._settings.get_input_dir())
        self._in_edit.textChanged.connect(self._on_in_changed)
        btn_in = QPushButton("选择")
        btn_in.clicked.connect(self._choose_input)
        row_in.addWidget(self._in_edit)
        row_in.addWidget(btn_in)
        root.addLayout(row_in)

        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("输出目录"))
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("留空自动生成：照片文件夹/AI摄影管家_YYYYMMDD_HHMMSS/")
        self._out_edit.setText(self._settings.get_output_dir())
        self._out_edit.textChanged.connect(self._on_out_changed)
        btn_out = QPushButton("另选")
        btn_out.clicked.connect(self._choose_output)
        row_out.addWidget(self._out_edit)
        row_out.addWidget(btn_out)
        root.addLayout(row_out)

        # ---- 归档 / 重命名开关 ----
        row_opts = QHBoxLayout()
        self._cb_archive = QCheckBox("归档全部照片（精选/普通/废片/去重）")
        self._cb_archive.setChecked(self._settings.get_archive_all())
        self._cb_archive.toggled.connect(self._settings.set_archive_all)
        self._cb_structure = QCheckBox("保留原文件夹结构")
        self._cb_structure.setChecked(self._settings.get_keep_structure())
        self._cb_structure.toggled.connect(self._settings.set_keep_structure)
        self._cb_rename = QCheckBox("自动重命名（特质-拍摄时间）")
        self._cb_rename.setChecked(self._settings.get_auto_rename())
        self._cb_rename.toggled.connect(self._settings.set_auto_rename)
        row_opts.addWidget(self._cb_archive)
        row_opts.addWidget(self._cb_structure)
        row_opts.addWidget(self._cb_rename)
        row_opts.addStretch(1)
        root.addLayout(row_opts)

        root.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self._model_status = QLabel("模型 · 检测中…", objectName="modelStatus")
        self._model_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self._model_status)
        self._start_btn = QPushButton("开始分析")
        self._start_btn.setObjectName("primaryBtn")
        self._start_btn.clicked.connect(self._on_start)
        bottom.addWidget(self._start_btn)
        root.addLayout(bottom)

    def set_analyzing(self, busy: bool):
        """分析进行中禁用「开始分析」按钮（禁用态自动显示为灰色）。"""
        self._start_btn.setEnabled(not busy)

    # ---- 设置 / 模型状态 ----
    def _open_settings(self):
        SettingsDialog(self).exec()
        self._refresh_ping()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_ping()

    def _model_display_name(self) -> str:
        mid = self._settings.get_model_id()
        preset = get_preset(mid)
        override = self._settings.get_model_override()
        model = override or preset.get("default_model", "")
        name = preset.get("name", mid)
        return f"{name} · {model}" if model else name

    def _refresh_ping(self):
        if self._ping_worker is not None:
            return
        self._model_status.setText("模型 · 检测中…")
        self._ping_worker = PingWorker(
            self._settings.get_model_id(),
            self._settings.get_api_key(),
            self._settings.get_base_url(),
            self._settings.get_model_override(),
        )
        self._ping_worker.done.connect(self._on_ping_done)
        self._ping_worker.start()

    def _on_ping_done(self, ok, ms, detail):
        model = self._model_display_name()
        if ok:
            self._model_status.setText(f"{model} ｜ ● 已连接 {ms}ms")
        else:
            self._model_status.setText(f"{model} ｜ ○ 未连接")
            self._model_status.setToolTip(detail)
        self._ping_worker.deleteLater()
        self._ping_worker = None

    # ---- 目录选择 + 自动默认输出 ----
    def _choose_input(self):
        d = QFileDialog.getExistingDirectory(self, "选择照片文件夹")
        if d:
            self._in_edit.setText(d)
            self._settings.set_input_dir(d)

    def _choose_output(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self._out_modified = True
            self._setting_out = True
            self._out_edit.setText(d)
            self._setting_out = False
            self._settings.set_output_dir(d)

    def _on_in_changed(self, _text: str):
        # 照片目录改变时，若输出目录未被用户手动锁定，刷新预览
        self._refresh_out_preview()

    def _on_out_changed(self, _text: str):
        # 用户在输出框里打字 → 视为手动锁定
        if not self._setting_out:
            self._out_modified = True

    def _refresh_out_preview(self):
        if self._out_modified:
            return
        default = self._default_out_dir()
        if not default:
            return
        self._setting_out = True
        self._out_edit.setText(default)
        self._setting_out = False

    def _default_out_dir(self) -> str:
        in_dir = self._in_edit.text().strip()
        if not in_dir:
            return ""
        ts = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(in_dir, f"AI摄影管家_{ts}")

    def _resolve_out_dir(self) -> str:
        """返回本次分析实际使用的输出目录：用户填的优先；否则自动按照片文件夹 + 时间戳生成。"""
        out = self._out_edit.text().strip()
        if out:
            return out
        return self._default_out_dir()

    # ---- 开始分析 ----
    def _on_start(self):
        api_key = self._settings.get_api_key()
        if not api_key:
            QMessageBox.warning(self, "需要 API Key", "请先在「设置」中配置视觉模型的 API Key。")
            self._open_settings()
            return
        in_dir = self._in_edit.text().strip()
        out_dir = self._resolve_out_dir()
        if not in_dir or not os.path.isdir(in_dir):
            QMessageBox.warning(self, "选择文件夹", "请选择有效的照片文件夹。")
            return
        if not out_dir:
            QMessageBox.warning(self, "选择文件夹", "请选择输出目录。")
            return
        # 把实际使用的输出目录显示并持久化（方便历史记录与再次使用）
        self._setting_out = True
        if self._out_edit.text().strip() != out_dir:
            self._out_edit.setText(out_dir)
        self._setting_out = False
        self._settings.set_output_dir(out_dir)

        model_id = self._settings.get_model_id()
        model_override = self._settings.get_model_override()
        top_n = self._top_spin.value()
        options = {
            "dedup_level": self._dedup.currentData() or DEFAULT_DEDUP_LEVEL,
            "archive_all": self._cb_archive.isChecked(),
            "keep_structure": self._cb_structure.isChecked(),
            "auto_rename": self._cb_rename.isChecked(),
        }
        mw = self.window()
        if hasattr(mw, "start_analysis"):
            mw.start_analysis(model_id, api_key, in_dir, out_dir, top_n,
                              model_override, options)
