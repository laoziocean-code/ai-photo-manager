"""归档导出 + 自动重命名 + Lightroom 参数 单元测试（无需 AI/网络）。"""
import os
import shutil
import tempfile

import pytest
from PIL import Image

from src.core.record import PhotoRecord
from src.core.retouch.lr_advice import format_lr, lr_copy_text, lr_note, lr_params
from src.core.selection.top_selector import (
    build_auto_name, export_organized, select_top,
)


def _rec(path, score=80.0, category="风景", dup_of=""):
    r = PhotoRecord(path=path)
    r.total_score = score
    r.ai = {"category": category,
            "lr_advice": {"exposure": 0.2, "highlights": -15, "shadows": 10,
                          "temperature": 8, "style": "胶片清新",
                          "explanation": "平衡肤色"}}
    r.dup_of = dup_of
    return r


def _img(path, color=(120, 120, 120)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (100, 100), color).save(path)


@pytest.fixture
def photos():
    d = tempfile.mkdtemp()
    try:
        files = {
            "a": os.path.join(d, "a.jpg"),
            "b": os.path.join(d, "b.jpg"),
            "c": os.path.join(d, "c.jpg"),
            "d": os.path.join(d, "d.jpg"),
        }
        for p in files.values():
            _img(p)
        yield files
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_select_top(photos):
    recs = [PhotoRecord(path=p) for p in photos.values()]
    for i, r in enumerate(recs):
        r.total_score = 90 - i * 10
    assert [r.total_score for r in select_top(recs, 2)] == [90, 80]


def test_export_organized_four_folders(photos):
    out = os.path.join(os.path.dirname(photos["a"]), "out")
    tier1 = [_rec(photos["a"], score=90)]
    tier2 = [_rec(photos["b"], score=85)]
    tier3 = [_rec(photos["c"], score=70)]
    rejected = [_rec(photos["d"], score=0, dup_of=photos["a"])]
    export_organized(tier1, tier2, tier3, rejected, out, archive_all=True)
    for name in ("精选", "普通", "废片", "去重"):
        assert os.path.isdir(os.path.join(out, name)), name
    # 精选含 a，普通含 b/c，去重含 d
    assert len(os.listdir(os.path.join(out, "精选"))) == 1
    assert len(os.listdir(os.path.join(out, "普通"))) == 2
    assert len(os.listdir(os.path.join(out, "去重"))) == 1
    assert len(os.listdir(os.path.join(out, "废片"))) == 0


def test_export_organized_archive_off(photos):
    out = os.path.join(os.path.dirname(photos["a"]), "out2")
    tier1 = [_rec(photos["a"], score=90)]
    tier2 = [_rec(photos["b"], score=85)]
    rejected = [_rec(photos["d"], score=0, dup_of=photos["a"])]
    export_organized(tier1, tier2, [], rejected, out, archive_all=False)
    assert os.path.isdir(os.path.join(out, "精选"))
    assert not os.path.exists(os.path.join(out, "普通"))


def test_export_auto_rename(photos):
    out = os.path.join(os.path.dirname(photos["a"]), "out3")
    tier1 = [_rec(photos["a"], score=90, category="风景")]
    export_organized(tier1, [], [], [], out, archive_all=True, auto_rename=True)
    names = os.listdir(os.path.join(out, "精选"))
    assert len(names) == 1
    # 「风景-YYYY-MM-DD_HHMMSS.jpg」格式
    assert names[0].startswith("风景-") and names[0].endswith(".jpg")


def test_build_auto_name_fallback():
    r = PhotoRecord(path="x.jpg")
    r.ai = {"category": "星空"}
    name = build_auto_name(r)
    assert name.startswith("星空-")


def test_lr_params_and_copy():
    lr = {"exposure": 0.2, "highlights": -15, "shadows": 10,
          "temperature": 8, "style": "胶片清新", "explanation": "平衡肤色"}
    params = lr_params(lr)
    assert {p["label"] for p in params} == {"曝光度", "高光", "阴影", "色温"}
    txt = lr_copy_text(lr)
    assert "曝光度 +0.20" in txt
    assert "高光 -15" in txt
    assert "阴影 +10" in txt
    assert "色温 +8" in txt
    assert lr_note(lr) == "平衡肤色"
    assert "曝光" in format_lr(lr)


def test_lr_empty():
    assert lr_copy_text({}) == ""
    assert lr_params({}) == []
    assert format_lr({}) == "（暂无明显调整建议）"
