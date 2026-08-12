"""Top N 精选 + 复制导出。

- select_top：按总分降序取前 n 张。
- export_top：复制到 <output_dir>/AI精选/ 下（TOP1.jpg ...）便于在资源管理器里直接查看原图，
  不再生成任何清单文件（所有信息统一在 HTML 报告中）。
"""
import os
import shutil
from typing import List, Sequence

from src.core.record import PhotoRecord


def select_top(results: Sequence[PhotoRecord], n: int = 10) -> List[PhotoRecord]:
    ranked = sorted(results, key=lambda r: r.total_score, reverse=True)
    return ranked[: max(0, n)]


_EXT_MAP = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png",
            ".webp": ".webp", ".bmp": ".jpg", ".tif": ".jpg", ".tiff": ".jpg"}


def export_top(picked: Sequence[PhotoRecord], output_dir: str, n: int = 10) -> str:
    """复制精选原图到 output_dir/AI精选/，返回该目录路径。不再写清单文件。"""
    top_dir = os.path.join(output_dir, "AI精选")
    os.makedirs(top_dir, exist_ok=True)
    for idx, rec in enumerate(picked, start=1):
        ext = os.path.splitext(rec.path)[-1].lower() or ".jpg"
        out_name = f"TOP{idx}{_EXT_MAP.get(ext, '.jpg')}"
        out_path = os.path.join(top_dir, out_name)
        try:
            shutil.copy2(rec.path, out_path)
        except Exception:
            pass
    return top_dir