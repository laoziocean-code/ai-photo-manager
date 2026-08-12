"""HTML 摄影报告生成（Jinja2，杂志风）。

报告为单文件 HTML，缩略图以 base64 内嵌，便于直接分享。
context 由 AnalysisController 组装（见 analysis_controller._card）。
"""
import base64
import os
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.core.image_io import make_thumbnail

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _thumb_data_url(path: str) -> str:
    data = make_thumbnail(path, size=640)
    if not data:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def render_report(context: Dict[str, Any], output_path: str) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    # 为三档（及旧版 photos）补全缩略图 base64 data URL
    for key in ("tier1", "tier2", "tier3", "photos"):
        for p in context.get(key, []) or []:
            if not p.get("thumb"):
                p["thumb"] = _thumb_data_url(p.get("path", ""))
    template = env.get_template("report_template.html")
    html = template.render(**context)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
