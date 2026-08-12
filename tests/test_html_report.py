import os
import shutil
import tempfile

from PIL import Image

from src.core.report.html_report import render_report


def test_render_report():
    d = tempfile.mkdtemp()
    try:
        img = os.path.join(d, "x.jpg")
        Image.new("RGB", (200, 200), (100, 100, 100)).save(img)
        ctx = {
            "analysis_time": "2026-01-01 00:00",
            "total": 3,
            "picked": 1,
            "tier2_count": 1,
            "tier3_count": 0,
            "avg_score": 80.0,
            "dedup_level": "标准",
            "dedup_count": 0,
            "dedup_groups": [],
            "tier1": [{
                "path": img, "name": "x.jpg", "score": 80.0, "grade": "A",
                "review": "不错", "retouch": "风格：胶片",
                "category": "风景", "publish": "平台：小红书",
                "exif": {"相机": "X"}, "thumb": "",
            }],
            "tier2": [],
            "tier3": [],
            "rejected": [],
        }
        out = os.path.join(d, "report.html")
        render_report(ctx, out)
        assert os.path.exists(out)
        html = open(out, encoding="utf-8").read()
        assert "x.jpg" in html
        assert "摄影报告" in html
        assert "data:image/jpeg;base64" in html  # 缩略图内嵌
        # 三档区都有渲染
        assert "精选" in html and "良好" in html and "普通" in html
    finally:
        shutil.rmtree(d, ignore_errors=True)