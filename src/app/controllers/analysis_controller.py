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
from src.core.retouch.lr_advice import (
    format_lr, lr_copy_text, lr_note, lr_params,
)
from src.core.scoring.scorer import compute_total, grade
from src.core.selection.top_selector import export_organized, select_top
from src.utils.logger import get_logger

logger = get_logger("analysis")

# 估算「节省的人工时间」基准：人工逐张浏览+评分+筛选一张照片的耗时（秒）
_SECONDS_PER_PHOTO = 30


def _fmt_duration(seconds: float) -> str:
    """把秒数格式化为「X 分 Y 秒 / X 时 Y 分」等人类可读串。"""
    s = int(round(seconds))
    if s < 60:
        return f"{s} 秒"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m} 分 {sec} 秒"
    h, m = divmod(m, 60)
    return f"{h} 时 {m} 分"


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
        t_start = time.monotonic()

        def progress(stage, cur, total, msg=""):
            if on_progress:
                on_progress(stage, cur, total, msg)

        progress("preprocess", 0, len(image_paths), "本地预处理中（去重/相似/模糊/曝光/分辨率）…")
        candidates, rejected = filter_photos(
            image_paths, options,
            on_progress=lambda s, c, t, m: progress(s, c, t, m),
        )
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
        token_input = 0
        token_output = 0
        for i, rec in enumerate(candidates):
            if self._stop:
                break
            progress("ai", i, total, f"AI 评分 {i + 1}/{total}：{os.path.basename(rec.path)}")
            try:
                rec.ai = model.analyze(rec.path, prompt)
                rec.total_score = compute_total(rec.ai.get("scores", {}))
                usage = getattr(model, "usage", None) or {}
                token_input += int(usage.get("input_tokens", 0) or 0)
                token_output += int(usage.get("output_tokens", 0) or 0)
            except Exception as e:
                logger.error(f"AI 分析失败 {rec.path}: {e}")
                rec.ai = {}
                rec.total_score = 0.0
            results.append(rec)

        duration_sec = max(0.0, time.monotonic() - t_start)
        token_total = token_input + token_output
        ai_count = len(results)
        saved_sec = int(len(image_paths) * _SECONDS_PER_PHOTO)

        tier1, tier2, tier3 = _split_tiers(results, top_n)
        progress("export", 0, 1, "归档照片与生成报告…")
        archive_all = bool((options or {}).get("archive_all", True))
        keep_structure = bool((options or {}).get("keep_structure", False))
        auto_rename = bool((options or {}).get("auto_rename", False))
        try:
            src_root = os.path.commonpath(image_paths) if image_paths else ""
        except Exception:
            src_root = ""
        export_organized(
            tier1, tier2, tier3, rejected, output_dir,
            archive_all=archive_all, keep_structure=keep_structure,
            auto_rename=auto_rename, src_root=src_root,
        )

        avg = round(sum(r.total_score for r in results) / total, 1) if total else 0
        render_report({
            "analysis_time": time.strftime("%Y-%m-%d %H:%M"),
            "total": len(image_paths),
            "picked": len(tier1),
            "tier2_count": len(tier2),
            "tier3_count": len(tier3),
            "avg_score": avg,
            "duration_sec": round(duration_sec, 1),
            "duration_text": _fmt_duration(duration_sec),
            "ai_count": ai_count,
            "tokens": {
                "input_tokens": token_input,
                "output_tokens": token_output,
                "total": token_total,
            },
            "saved_sec": saved_sec,
            "saved_time": _fmt_duration(saved_sec),
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
                "duration_sec": round(duration_sec, 1),
                "duration_text": _fmt_duration(duration_sec),
                "ai_count": ai_count,
                "tokens": {
                    "input_tokens": token_input,
                    "output_tokens": token_output,
                    "total": token_total,
                },
                "saved_sec": saved_sec,
                "saved_time": _fmt_duration(saved_sec),
            })


def _thumb_data_url(path: str) -> str:
    data = make_thumbnail(path, size=640)
    if not data:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def _card(rec):
    lr = rec.ai.get("lr_advice", {})
    return {
        "path": rec.path,
        "name": rec.name,
        "score": round(rec.total_score, 1),
        "grade": grade(rec.total_score),
        "review": rec.ai.get("review", ""),
        "retouch": format_lr(lr),
        "lr_params": lr_params(lr),
        "lr_copy": lr_copy_text(lr),
        "lr_note": lr_note(lr),
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
