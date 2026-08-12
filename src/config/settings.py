"""设置管理：API Key 加密存储 + 模型/目录偏好 + 分析历史（基于 QSettings）。"""
import json
import os
import time

from PySide6.QtCore import QSettings

from src.utils.crypto import decrypt_string, encrypt_string


class SettingsManager:
    def __init__(self):
        self._qs = QSettings("AIStudio", "AI摄影管家")
        self._key_tag = "api_key_enc"
        self._model_tag = "model_id"
        self._override_tag = "model_override"
        self._base_url_tag = "base_url"
        self._in_tag = "input_dir"
        self._out_tag = "output_dir"
        self._recent_tag = "recent_reports"
        self._dedup_tag = "dedup_level"
        self._notify_tag = "notify_on_finish"
        self._shutdown_tag = "auto_shutdown"

    # ---- API Key（加密）----
    def get_api_key(self) -> str:
        v = self._qs.value(self._key_tag)
        if not v:
            return ""
        try:
            return decrypt_string(v)
        except Exception:
            return ""

    def set_api_key(self, key: str):
        if key:
            self._qs.setValue(self._key_tag, encrypt_string(key))
        else:
            self._qs.remove(self._key_tag)

    # ---- 视觉模型 ----
    def get_model_id(self) -> str:
        return self._qs.value(self._model_tag, "glm-vision")

    def set_model_id(self, mid: str):
        self._qs.setValue(self._model_tag, mid)

    # ---- 模型名覆盖（留空则用预设 default_model）----
    def get_model_override(self) -> str:
        return self._qs.value(self._override_tag, "") or ""

    def set_model_override(self, name: str):
        name = (name or "").strip()
        if name:
            self._qs.setValue(self._override_tag, name)
        else:
            self._qs.remove(self._override_tag)

    # ---- base_url 覆盖（自定义兼容模型用；留空则用预设）----
    def get_base_url(self) -> str:
        return self._qs.value(self._base_url_tag, "") or ""

    def set_base_url(self, url: str):
        url = (url or "").strip()
        if url:
            self._qs.setValue(self._base_url_tag, url)
        else:
            self._qs.remove(self._base_url_tag)

    # ---- 目录 ----
    def get_input_dir(self) -> str:
        return self._qs.value(self._in_tag, "")

    def set_input_dir(self, d: str):
        self._qs.setValue(self._in_tag, d)

    def get_output_dir(self) -> str:
        return self._qs.value(self._out_tag, "")

    def set_output_dir(self, d: str):
        self._qs.setValue(self._out_tag, d)

    # ---- 去重档位 ----
    def get_dedup_level(self) -> str:
        return self._qs.value(self._dedup_tag, "标准")

    def set_dedup_level(self, level: str):
        self._qs.setValue(self._dedup_tag, level)

    # ---- 完成提醒 / 自动关机 ----
    def get_notify_on_finish(self) -> bool:
        return self._qs.value(self._notify_tag, True, type=bool)

    def set_notify_on_finish(self, on: bool):
        self._qs.setValue(self._notify_tag, bool(on))

    def get_auto_shutdown(self) -> bool:
        return self._qs.value(self._shutdown_tag, False, type=bool)

    def set_auto_shutdown(self, on: bool):
        self._qs.setValue(self._shutdown_tag, bool(on))

    # ---- 分析历史（最近报告，JSON 持久化，最多 20 条）----
    def get_recent_reports(self) -> list:
        raw = self._qs.value(self._recent_tag, "") or ""
        if not raw:
            return []
        try:
            lst = json.loads(raw)
            return lst if isinstance(lst, list) else []
        except Exception:
            return []

    def add_recent_report(self, folder: str, report_path: str, total: int,
                          picked: int, dedup_count: int = 0, model_name: str = "") -> list:
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M"),
            "folder": folder,
            "report": report_path,
            "total": total,
            "picked": picked,
            "dedup": dedup_count,
            "model": model_name,
        }
        lst = self.get_recent_reports()
        lst = [e for e in lst if e.get("report") != report_path]
        lst.insert(0, entry)
        del lst[20:]
        self._qs.setValue(self._recent_tag, json.dumps(lst, ensure_ascii=False))
        return lst

    def clear_recent_reports(self):
        self._qs.remove(self._recent_tag)

    def remove_recent_report(self, report_path: str):
        lst = self.get_recent_reports()
        lst = [e for e in lst if e.get("report") != report_path]
        self._qs.setValue(self._recent_tag, json.dumps(lst, ensure_ascii=False))
