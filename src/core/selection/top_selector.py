"""精选导出 + 全量归档 + 自动重命名。

- select_top：按总分降序取前 n 张。
- export_organized：把全部分析结果归档为四个文件夹（精选/普通/废片/去重），
  支持「保留原文件夹结构」与「特质-拍摄时间」自动重命名。
- build_auto_name：按「特质-拍摄时间」生成文件名（供归档时重命名）。
"""
import os
import re
import shutil
import time
from typing import List, Optional, Sequence

from src.core.record import PhotoRecord


def select_top(results: Sequence[PhotoRecord], n: int = 10) -> List[PhotoRecord]:
    ranked = sorted(results, key=lambda r: r.total_score, reverse=True)
    return ranked[: max(0, n)]


_EXT_MAP = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png",
            ".webp": ".webp", ".bmp": ".jpg", ".tif": ".jpg", ".tiff": ".jpg"}

# 归档文件夹名（顺序即界面展示顺序）
FOLDER_PICK = "精选"
FOLDER_NORMAL = "普通"
FOLDER_WASTE = "废片"
FOLDER_DUP = "去重"


def _safe_filename(name: str) -> str:
    """去除 Windows/macOS 文件名非法字符。"""
    for c in '<>:"/\\|?*':
        name = name.replace(c, "_")
    return name.strip() or "照片"


def _datetime_from_exif(rec: PhotoRecord) -> str:
    """从 EXIF DateTimeOriginal 提取「YYYY-MM-DD_HHMMSS」；失败返回空串。"""
    raw = ((rec.meta.exif or {}).get("datetime_taken") or "")
    s = str(raw).strip()
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) >= 14:
        return (f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
                f"_{digits[8:10]}{digits[10:12]}{digits[12:14]}")
    return ""


def build_auto_name(rec: PhotoRecord) -> str:
    """按「特质-拍摄时间」生成文件名主体（不含扩展名）。

    特质优先取 AI 分类（人像/风景/建筑/星空/美食/旅行）；分类为「其他」或
    缺失时，退而求其次用修图风格（如「胶片清新」「暗调电影感」），
    再没有才用「照片」。拍摄时间优先 EXIF，其次文件修改时间。
    """
    ai = rec.ai or {}
    trait = (ai.get("category") or "").strip()
    if not trait or trait == "其他":
        style = ((ai.get("lr_advice") or {}).get("style") or "").strip()
        if style:
            trait = _safe_filename(style)[:8]
        else:
            trait = "照片"
    dt = _datetime_from_exif(rec)
    if not dt:
        try:
            dt = time.strftime("%Y-%m-%d_%H%M%S",
                               time.localtime(os.path.getmtime(rec.path)))
        except Exception:
            dt = "未知时间"
    return _safe_filename(f"{trait}-{dt}")


def _unique_name(name: str, used: set) -> str:
    """重名时追加 _2 / _3 … 后缀。"""
    if name not in used:
        used.add(name)
        return name
    stem, ext = os.path.splitext(name)
    i = 2
    while True:
        cand = f"{stem}_{i}{ext}"
        if cand not in used:
            used.add(cand)
            return cand
        i += 1


def _rel_dir(path: str, src_root: str) -> str:
    """相对 src_root 的子目录路径；保留原文件夹结构用。"""
    if not src_root:
        return ""
    try:
        rel = os.path.relpath(os.path.dirname(path), src_root)
        return "" if rel in (".", "") else rel
    except Exception:
        return ""


def export_organized(
    tier1: Sequence[PhotoRecord],
    tier2: Sequence[PhotoRecord],
    tier3: Sequence[PhotoRecord],
    rejected: Sequence[PhotoRecord],
    output_dir: str,
    archive_all: bool = True,
    keep_structure: bool = False,
    auto_rename: bool = False,
    src_root: str = "",
) -> str:
    """把分析结果归档到 output_dir 下的分类文件夹，返回 output_dir。

    分类规则：
        精选 = tier1（AI 推荐 TopN）
        普通 = tier2 + tier3（其余候选）
        废片 = rejected 中非去重（模糊/曝光/分辨率等）
        去重 = rejected 中去重（dup_of 非空）
    - archive_all=False 时只导出「精选」。
    - keep_structure=True 时在分类文件夹内保留原相对子目录。
    - auto_rename=True 时对精选/普通按「特质-拍摄时间」重命名。
    """
    groups: List[tuple] = [
        (FOLDER_PICK, list(tier1), True),
        (FOLDER_NORMAL, list(tier2) + list(tier3), True),
        (FOLDER_WASTE, [r for r in rejected if not r.dup_of], False),
        (FOLDER_DUP, [r for r in rejected if r.dup_of], False),
    ]
    if not archive_all:
        groups = [(FOLDER_PICK, list(tier1), True)]

    for label, recs, renameable in groups:
        dir_ = os.path.join(output_dir, label)
        os.makedirs(dir_, exist_ok=True)  # 始终创建，保证四文件夹结构稳定
        if not recs:
            continue
        used: set = set()
        for i, rec in enumerate(recs, start=1):
            ext = os.path.splitext(rec.path)[1].lower() or ".jpg"
            ext = _EXT_MAP.get(ext, ext)
            rel = _rel_dir(rec.path, src_root) if keep_structure else ""
            dest_dir = os.path.join(dir_, rel) if rel else dir_
            os.makedirs(dest_dir, exist_ok=True)

            if auto_rename and renameable:
                name = _unique_name(build_auto_name(rec) + ext, used)
            elif label == FOLDER_PICK and not keep_structure:
                name = f"TOP{i}{ext}"
            else:
                name = _unique_name(os.path.basename(rec.path), used)

            try:
                shutil.copy2(rec.path, os.path.join(dest_dir, name))
            except Exception:
                pass
    return output_dir


def export_top(picked: Sequence[PhotoRecord], output_dir: str, n: int = 10) -> str:
    """向后兼容：只导出精选到 output_dir/AI精选/（旧调用）。"""
    top_dir = os.path.join(output_dir, "AI精选")
    os.makedirs(top_dir, exist_ok=True)
    for idx, rec in enumerate(picked, start=1):
        ext = os.path.splitext(rec.path)[-1].lower() or ".jpg"
        out_name = f"TOP{idx}{_EXT_MAP.get(ext, '.jpg')}"
        try:
            shutil.copy2(rec.path, os.path.join(top_dir, out_name))
        except Exception:
            pass
    return top_dir
