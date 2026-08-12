"""分析主控：把各业务模块串成一条流水线。

回调签名：
    on_progress(stage: str, current: int, total: int, message: str)
    on_done(summary: dict)

stage ∈ preprocess | ai | export | done
summary 含 results / rejected / tier1 / tier2 / tier3 / output_dir / dedup_*

三档分法：
    tier1 精选：top_n 张（无论分数）
    tier2 良好：非精选中 grade >= A（>= 80）
    tier3 普通：其余非废片候选（grade < 80）
所有信息都汇总进 HTML 报告（精选/良好/普通 三档卡片 + 废片名称+原因 + 去重说明）。
"""
import base64
import os
import time

from src.core.ai.factory import build_model
from src.core.ai.prompt_templates import scoring_prompt
from src.core.ai.response_parser import format_publish
from src.core.image_io import humanize_exif, make_thumbnail
from src.core.preprocessing.deduplication import DEDUP_LEVELS, DEFAULT_DEDUP_LEVEL
from src.core.preprocessing.quality_filter import (
    collect_dedup_groups, filter_photos,
)
from src.core.report.html_report import render_report
from src.core.retouch.lr_advice import format_lr
from src.core.scoring.scorer import compute_total, grade
from src.core.selection.top_selector import export_top, select_top
from src.utils.logger import get_logger

logger = get_logger("analysis")


def _split_tiers(results, top_n: int):
    """把全部 candidate 按分数拆成 三档。

    tier1 精选：top_n 张（与分数无关，作为「AI 推荐的 TopN」）。
    tier2 良好：剩余中 grade >= A（>= 80）。
    tier3 普通：剩余中 grade < A。
    排序均按 score 降序。
    """
    ranked = sorted(results, key=lambda r: r.total_score, reverse=True)
    tier1 = ranked[: max(0, top_n)]
    rest = ranked[max(0, top_n):]
    tier2 = [r for r in rest if r.total_score >= 80.0]
    tier3 = [r for r in rest if r.total_score < 80.0]
    return tier1, tier2, tier3


class AnalysisController:
    def __init__(self):
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self, image_paths, model_id, api_key, output_dir, top_n=10,
            options=None, model_override="", on_progress=None, on_done=None):
        def progress(stage, cur, total, msg=""):
            if on_progress:
                on_progress(stage, cur, total, msg)

        progress("preprocess", 0, len(image_paths), "本地预处理中（去重/相似/模糊/曝光/分辨率）…")
        candidates, rejected = filter_photos(image_paths, options)
        dedup_groups = collect_dedup_groups(rejected)
        dedup_count = sum(len(g["similar"]) for g in dedup_groups)
        dedup_level = (options or {}).get("dedup_level", DEFAULT_DEDUP_LEVEL)
        if dedup_level not in DEDUP_LEVELS:
            dedup_level = DEFAULT_DEDUP_LEVEL
        progress("preprocess", len(image_paths), len(image_paths),
                 f"候选 {len(candidates)} 张，去重 {dedup_count} 张，淘汰废片 {len(rejected)} 张")

        model = build_model(model_id, api_key, model_override=model_override)
        prompt = scoring_prompt()
        results = []
        total = len(candidates)
        for i, rec in enumerate(candidates):
            if self._stop:
                break
            progress("ai", i, total, f"AI 评分 {i + 1}/{total}：{os.path.basename(rec.path)}")
            try:
                rec.ai = model.analyze(rec.path, prompt)
                rec.total_score = compute_total(rec.ai.get("scores", {}))
            except Exception as e:
                logger.error(f"AI 分析失败 {rec.path}: {e}")
                rec.ai = {}
                rec.total_score = 0.0
            results.append(rec)

        tier1, tier2, tier3 = _split_tiers(results, top_n)
        progress("export", 0, 1, "导出精选原图与生成报告…")
        export_top(tier1, output_dir, top_n)

        avg = round(sum(r.total_score for r in results) / total, 1) if total else 0
        render_report({
            "analysis_time": time.strftime("%Y-%m-%d %H:%M"),
            "total": len(image_paths),
            "picked": len(tier1),
            "tier2_count": len(tier2),
            "tier3_count": len(tier3),
            "avg_score": avg,
            "dedup_level": dedup_level,
            "dedup_count": dedup_count,
            "dedup_groups": dedup_groups,
            "tier1": [_card(r) for r in tier1],
            "tier2": [_card(r) for r in tier2],
            "tier3": [_card(r) for r in tier3],
            "rejected": [_rejected_card(r) for r in rejected],
        }, os.path.join(output_dir, "摄影报告.html"))

        progress("done", 1, 1, "完成")
        if on_done:
            on_done({
                "results": results,
                "rejected": rejected,
                "tier1": tier1,
                "tier2": tier2,
                "tier3": tier3,
                "output_dir": output_dir,
                "dedup_level": dedup_level,
                "dedup_count": dedup_count,
                "dedup_groups": dedup_groups,
            })


def _thumb_data_url(path: str) -> str:
    data = make_thumbnail(path, size=640)
    if not data:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def _card(rec):
    return {
        "path": rec.path,
        "name": rec.name,
        "score": round(rec.total_score, 1),
        "grade": grade(rec.total_score),
        "review": rec.ai.get("review", ""),
        "retouch": format_lr(rec.ai.get("lr_advice", {})),
        "category": rec.ai.get("category", ""),
        "publish": format_publish(rec.ai.get("publish", {})),
        "exif": humanize_exif(rec.meta.exif),
        "thumb": _thumb_data_url(rec.path),
    }


def _rejected_card(rec):
    return {
        "name": rec.name,
        "path": rec.path,
        "reason": rec.reject_reason,
        "is_dup": bool(rec.dup_of),
        "dup_of": os.path.basename(rec.dup_of) if rec.dup_of else "",
    }
