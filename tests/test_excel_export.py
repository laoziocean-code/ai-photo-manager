"""精选 + 三档分级 + 默认输出目录测试。"""
import os
import tempfile

import pytest

from src.app.controllers.analysis_controller import _split_tiers
from src.core.image_io import ImageMeta
from src.core.record import PhotoRecord
from src.core.selection.top_selector import export_top


def _rec(path, score):
    rec = PhotoRecord(path=path, meta=ImageMeta(path=path))
    rec.total_score = score
    return rec


def test_export_top_copies_only_no_xlsx():
    d = tempfile.mkdtemp()
    try:
        out = os.path.join(d, "out")
        os.makedirs(out)
        paths = [os.path.join(d, f"p{i}.jpg") for i in range(2)]
        for p in paths:
            with open(p, "wb") as f:
                f.write(b"\x00")
        picked = [_rec(paths[0], 90.0), _rec(paths[1], 88.0)]
        top_dir = export_top(picked, out, 2)

        assert os.path.isdir(top_dir)
        assert os.path.exists(os.path.join(top_dir, "TOP1.jpg"))
        assert os.path.exists(os.path.join(top_dir, "TOP2.jpg"))
        # 不再生成任何清单文件
        assert not os.path.exists(os.path.join(top_dir, "精选清单.xlsx"))
        assert not os.path.exists(os.path.join(top_dir, "manifest.json"))
        assert not os.path.exists(os.path.join(top_dir, "精选清单.md"))
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_export_top_empty_picked_creates_dir():
    d = tempfile.mkdtemp()
    try:
        out = os.path.join(d, "out")
        os.makedirs(out)
        export_top([], out, 0)
        assert os.path.isdir(os.path.join(out, "AI精选"))
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_split_tiers_three_levels():
    # 20 张候选，score 从 95 到 5
    recs = [_rec(f"p{i}.jpg", 95 - i * 5) for i in range(20)]
    # score: 95,90,85,80,75,70,65,...
    tier1, tier2, tier3 = _split_tiers(recs, top_n=5)

    # tier1 = top_n=5
    assert len(tier1) == 5
    assert [r.total_score for r in tier1] == [95, 90, 85, 80, 75]

    # tier2 = 剩下中 score>=80
    assert all(r.total_score >= 80 for r in tier2)
    assert tier2 == []   # 80,75 被选入 tier1，剩下最高 70 < 80

    # tier3 = 剩下的全部
    assert all(r.total_score < 80 for r in tier3)
    assert len(tier3) == 15


def test_split_tiers_top_n_zero():
    recs = [_rec(f"p{i}.jpg", 90 - i) for i in range(5)]  # 90,89,88,87,86
    tier1, tier2, tier3 = _split_tiers(recs, top_n=0)
    assert tier1 == []
    # 全部 >=80 → tier2
    assert len(tier2) == 5
    assert tier3 == []


def test_split_tiers_all_below_threshold():
    recs = [_rec(f"p{i}.jpg", 60 - i) for i in range(5)]  # 60,59,58,57,56
    tier1, tier2, tier3 = _split_tiers(recs, top_n=10)
    assert len(tier1) == 5   # 全是 top_n
    assert tier2 == []        # 全部 < 80
    assert tier3 == []