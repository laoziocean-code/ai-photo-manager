"""后台线程：ping 模型端点，避免阻塞 UI。"""
from PySide6.QtCore import QThread, Signal

from src.core.ai.ping import ping_model


class PingWorker(QThread):
    done = Signal(bool, int, str)   # ok, 延迟ms, 详情

    def __init__(self, model_id, api_key, base_url_override="", model_override="",
                 parent=None):
        super().__init__(parent)
        self._model_id = model_id
        self._api_key = api_key
        self._base_url_override = base_url_override
        self._model_override = model_override

    def run(self):
        ok, ms, detail = ping_model(
            self._model_id, self._api_key,
            self._base_url_override, self._model_override,
        )
        self.done.emit(ok, ms, detail)
