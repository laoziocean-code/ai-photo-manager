"""设置弹窗：API Key（本地加密保存）+ 视觉模型 + 模型名/端点覆盖 + 完成行为。"""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from src.config.models_config import MODEL_PRESETS
from src.config.settings import SettingsManager


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(470, 380)
        self._settings = SettingsManager()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._key = QLineEdit()
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setPlaceholderText("输入你的视觉模型 API Key（本地加密保存）")
        saved = self._settings.get_api_key()
        if saved:
            self._key.setText(saved)
        form.addRow("API Key", self._key)

        self._model = QComboBox()
        for p in MODEL_PRESETS:
            self._model.addItem(p["name"], p["id"])
        idx = self._model.findData(self._settings.get_model_id())
        if idx >= 0:
            self._model.setCurrentIndex(idx)
        form.addRow("视觉模型", self._model)

        self._override = QLineEdit()
        self._override.setPlaceholderText("留空用预设（如 glm-4v-plus）；可填 glm-4v / glm-4v-flash 等精确 id")
        self._override.setText(self._settings.get_model_override())
        form.addRow("模型名(可覆盖)", self._override)

        self._base_url = QLineEdit()
        self._base_url.setPlaceholderText("留空用预设端点；自定义兼容模型时填写")
        self._base_url.setText(self._settings.get_base_url())
        form.addRow("API 端点(可覆盖)", self._base_url)

        layout.addLayout(form)

        self._notify = QCheckBox("分析完成时提醒（弹窗 + 提示音）")
        self._notify.setChecked(self._settings.get_notify_on_finish())
        layout.addWidget(self._notify)

        self._shutdown = QCheckBox("分析完成后自动关机")
        self._shutdown.setChecked(self._settings.get_auto_shutdown())
        layout.addWidget(self._shutdown)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        key = self._key.text().strip()
        if key:
            self._settings.set_api_key(key)
        else:
            self._settings.set_api_key("")
        self._settings.set_model_id(self._model.itemData(self._model.currentIndex()))
        self._settings.set_model_override(self._override.text())
        self._settings.set_base_url(self._base_url.text())
        self._settings.set_notify_on_finish(self._notify.isChecked())
        self._settings.set_auto_shutdown(self._shutdown.isChecked())
        QMessageBox.information(self, "已保存", "设置已保存。API Key 为本地加密存储，不会上传服务器。")
        self.accept()
