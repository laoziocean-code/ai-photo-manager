"""分析后台线程：在独立线程跑 AnalysisController，通过信号回报进度。

GUI 线程只接收信号，不阻塞。
"""
from PySide6.QtCore import QThread, Signal

from src.app.controllers.analysis_controller import AnalysisController
from src.utils.file_utils import list_images


class AnalysisWorker(QThread):
    progress = Signal(str, int, int, str)   # stage, current, total, message
    finished = Signal(object)               # summary dict
    error = Signal(str)

    def __init__(self, model_id, api_key, input_dir, output_dir, top_n=10, options=None,
                 model_override=""):
        super().__init__()
        self._model_id = model_id
        self._api_key = api_key
        self._input_dir = input_dir
        self._output_dir = output_dir
        self._top_n = top_n
        self._options = options
        self._model_override = model_override
        self._ctrl = AnalysisController()

    def stop(self):
        self._ctrl.stop()

    def run(self):
        try:
            paths = list_images(self._input_dir)
            if not paths:
                self.error.emit("所选文件夹没有受支持的图片（jpg/jpeg/png/webp/bmp/tif 或 NEF/CR2/ARW 等 RAW）。")
                return
            self._ctrl.run(
                paths, self._model_id, self._api_key, self._output_dir,
                self._top_n, self._options,
                model_override=self._model_override,
                on_progress=lambda s, c, t, m: self.progress.emit(s, c, t, m),
                on_done=lambda summary: self.finished.emit({
                    **summary,
                    "input_dir": self._input_dir,
                    "model_id": self._model_id,
                }),
            )
        except Exception as e:
            self.error.emit(str(e))
