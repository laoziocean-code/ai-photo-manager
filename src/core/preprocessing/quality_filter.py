"""本地预处理编排：产出候选集与废片集。

流程（均不调用任何网络/AI，先淘汰废片以节省 API 成本）：
    读图+EXIF → 精确去重(MD5) → 相似聚类(pHash) → 模糊过滤 → 曝光过滤 → 分辨率过滤

返回 (candidates, rejected)，每个元素都是 PhotoRecord。
- candidates：status="candidate"，进入后续 AI 评分。
- rejected：status="rejected"，附 reject_reason，仅用于报告展示。

去重按档位（dedup_level）控制相似判重阈值，被去重的照片记录
dup_group/dup_of 归属，可用 collect_dedup_groups 汇总成报告用结构。
"""
import os
from typing import Dict, List, Optional, Sequence

from src.core.image_io import ImageMeta, extract_exif, is_raw
from src.core.preprocessing.blur_detect import blur_score, is_blurry
from src.core.preprocessing.deduplication import (
    DEDUP_LEVELS, DEFAULT_DEDUP_LEVEL, compute_md5, compute_phash,
    find_groups, resolve_dedup_threshold,
)
from src.core.preprocessing.exposure_detect import exposure_stats
from src.core.record import PhotoRecord
from src.utils.file_utils import sniff_raw

DEFAULT_OPTIONS: Dict[str, object] = {
    "dedup_level": DEFAULT_DEDUP_LEVEL,  # 去重档位（五档 + 关闭）
    "phash_threshold": 8,        # 兼容旧配置：显式阈值（dedup_level 优先）
    "blur_threshold": 80.0,      # Laplacian 方差低于此值判为模糊
    "min_dimension": 800,        # 最短边最小像素
    "min_megapixels": 0.5,       # 最小百万像素
    "phash_hash_size": 8,
}


def _best(recs: List[PhotoRecord]) -> PhotoRecord:
    """在相似组里挑「最清晰者」作为保留代表。"""
    return max(recs, key=lambda r: (r.blur if not r.is_blurry else -1))


def filter_photos(paths: Sequence[str], options: Optional[Dict] = None,
                  on_progress=None):
    """本地预处理，返回 (candidates, rejected)。

    on_progress(stage, cur, total, msg)：逐文件回调，stage 恒为 "preprocess"，
    便于界面显示实时进度与预计剩余时间（RAW 批量预处理可能较耗时）。
    """
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    records: List[PhotoRecord] = []
    n = len(paths)

    for idx, p in enumerate(paths):
        if on_progress:
            on_progress("preprocess", idx, n,
                        f"预处理 {idx + 1}/{n}：{os.path.basename(p)}")
        try:
            meta_raw = extract_exif(p)
            rec = PhotoRecord(
                path=p,
                meta=ImageMeta(
                    path=p,
                    width=meta_raw.get("width", 0),
                    height=meta_raw.get("height", 0),
                    size_bytes=meta_raw.get("size_bytes", 0),
                    exif=meta_raw,
                ),
            )
            rec.md5 = compute_md5(p)
            rec.phash = compute_phash(p, int(opts["phash_hash_size"]))
            rec.phash_str = str(rec.phash)
            rec.blur = blur_score(p)
            rec.is_blurry = rec.blur < float(opts["blur_threshold"])
            rec.exposure = exposure_stats(p)
            w, h = rec.meta.width, rec.meta.height
            if w and h:
                mp = (w * h) / 1_000_000
                min_side = min(w, h)
                rec.resolution_ok = (mp >= float(opts["min_megapixels"])) and (
                    min_side >= int(opts["min_dimension"])
                )
            else:
                # 尺寸未知（EXIF 与解码都取不到，常见于个别 RAW）：不做分辨率
                # 淘汰，避免好照片被误杀；真读不出的文件会在后续阶段暴露错误。
                rec.resolution_ok = True
            records.append(rec)
        except Exception as e:
            rec = PhotoRecord(path=p)
            rec.status = "rejected"
            rec.reject_reason = f"无法读取：{e}"
            records.append(rec)

    _dedupe_exact(records)
    _dedupe_similar(records, resolve_dedup_threshold(opts))
    _filter_quality(records)

    candidates = [r for r in records if r.status == "candidate"]
    rejected = [r for r in records if r.status == "rejected"]
    return candidates, rejected


def collect_dedup_groups(rejected: Sequence[PhotoRecord]) -> List[Dict[str, object]]:
    """汇总被去重照片 → 报告用结构。

    返回示例：
        [{"kept": "保留文件的路径", "reason": "高度相似（感知哈希）",
          "similar": ["被去重文件1", "被去重文件2"]}, ...]
    每组只出现一次，按被去重数量降序排列。
    """
    by_kept: Dict[str, Dict[str, object]] = {}
    for r in rejected:
        if not r.dup_of:
            continue
        g = by_kept.get(r.dup_of)
        if g is None:
            g = {"kept": r.dup_of, "reason": r.reject_reason, "similar": []}
            by_kept[r.dup_of] = g
        g["similar"].append(r.path)
    groups = list(by_kept.values())
    groups.sort(key=lambda g: len(g["similar"]), reverse=True)
    return groups


def _dedupe_exact(records: List[PhotoRecord]) -> None:
    by_md5: Dict[str, List[PhotoRecord]] = {}
    for r in records:
        if r.status == "rejected" or not r.md5:
            continue
        by_md5.setdefault(r.md5, []).append(r)
    group_no = 0
    for grp in by_md5.values():
        if len(grp) > 1:
            group_no += 1
            keep = _best(grp)
            keep.dup_group = group_no
            for r in grp:
                if r is not keep:
                    r.status = "rejected"
                    r.reject_reason = "完全重复（MD5 相同）"
                    r.dup_group = group_no
                    r.dup_of = keep.path


def _dedupe_similar(records: List[PhotoRecord], threshold: Optional[int]) -> None:
    if threshold is None:
        return
    valid = [r for r in records if r.status != "rejected" and r.phash is not None]
    groups = find_groups(valid, threshold)
    group_no = 1000  # 与精确去重组号错开，避免混淆
    for grp in groups:
        if len(grp) > 1:
            group_no += 1
            grp_recs = [valid[i] for i in grp]
            keep = _best(grp_recs)
            keep.dup_group = group_no
            for r in grp_recs:
                if r is not keep:
                    r.status = "rejected"
                    r.reject_reason = "高度相似（感知哈希）"
                    r.dup_group = group_no
                    r.dup_of = keep.path


def _is_rawish(path: str) -> bool:
    """是否按 RAW 处理（扩展名白名单 + 文件头魔数兜底）。"""
    return is_raw(path) or sniff_raw(path)


def _filter_quality(records: List[PhotoRecord]) -> None:
    for r in records:
        if r.status == "rejected":
            continue
        if _is_rawish(r.path):
            # RAW 不做模糊/曝光淘汰：RAW 保留完整动态范围，欠曝/夜景可后期恢复；
            # 且全局 Laplacian 方差对夜空等暗场景系统性失灵（大片纯黑方差天然低），
            # 内嵌预览图也可能偏黑失真。质量判断交给 AI 视觉评分——本地预处理对
            # RAW 只做去重与分辨率校验，避免误杀摄影师的高质量源文件。
            if not r.resolution_ok:
                r.status = "rejected"
                r.reject_reason = "分辨率过低"
                continue
            r.status = "candidate"
            continue
        if r.is_blurry:
            r.status = "rejected"
            r.reject_reason = "疑似模糊/对焦不实"
            continue
        verdict = r.exposure.get("verdict", "未知")
        if verdict in ("严重欠曝", "严重过曝"):
            r.status = "rejected"
            r.reject_reason = verdict
            continue
        if not r.resolution_ok:
            r.status = "rejected"
            r.reject_reason = "分辨率过低"
            continue
        r.status = "candidate"
