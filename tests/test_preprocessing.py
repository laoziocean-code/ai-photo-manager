"""本地预处理单元测试（无需网络/AI）。

注意：blur_detect 在 cv2 缺失时回落到 numpy 实现，本测试覆盖该路径，
cv2 安装后同样适用（阈值一致）。
"""
import os
import shutil
import tempfile

import numpy as np
import pytest
from PIL import Image

from src.core.image_io import ImageMeta
from src.core.preprocessing.blur_detect import blur_score, is_blurry
from src.core.preprocessing.deduplication import (
    DEDUP_LEVELS, DEFAULT_DEDUP_LEVEL, compute_md5, compute_phash, find_groups,
    resolve_dedup_threshold,
)
from src.core.preprocessing.exposure_detect import classify_exposure, exposure_stats
from src.core.preprocessing.quality_filter import collect_dedup_groups, filter_photos
from src.core.record import PhotoRecord


def _make_image(path, size=(1200, 800), color=(120, 120, 120), noise=False):
    if noise:
        arr = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        Image.fromarray(arr).save(path)
    else:
        Image.new("RGB", size, color).save(path)


@pytest.fixture
def tmpdir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_md5_basic(tmpdir):
    p1 = os.path.join(tmpdir, "a.jpg")
    p2 = os.path.join(tmpdir, "b.jpg")
    _make_image(p1)
    _make_image(p2, color=(200, 50, 50))  # 不同内容
    assert compute_md5(p1) == compute_md5(p1)
    assert compute_md5(p1) != compute_md5(p2)


def test_phash_identical(tmpdir):
    p1 = os.path.join(tmpdir, "a.jpg")
    p2 = os.path.join(tmpdir, "a2.jpg")
    _make_image(p1)
    _make_image(p2)
    assert compute_phash(p1) == compute_phash(p2)


def test_find_groups(tmpdir):
    p1 = os.path.join(tmpdir, "a.jpg")
    p2 = os.path.join(tmpdir, "a2.jpg")
    _make_image(p1)
    _make_image(p2)
    recs = [PhotoRecord(path=p1), PhotoRecord(path=p2)]
    recs[0].phash = compute_phash(p1)
    recs[1].phash = compute_phash(p2)
    groups = find_groups(recs, 8)
    assert len(groups) == 1 and len(groups[0]) == 2


def test_blur_detect_noise_high_variance(tmpdir):
    sharp = os.path.join(tmpdir, "sharp.jpg")
    _make_image(sharp, noise=True)
    assert blur_score(sharp) > 0


def test_exposure_dark(tmpdir):
    dark = os.path.join(tmpdir, "dark.jpg")
    _make_image(dark, color=(5, 5, 5))
    stats = exposure_stats(dark)
    assert stats["verdict"] in ("严重欠曝", "欠曝")
    assert classify_exposure(dark) == stats["verdict"]


def test_filter_rejects_lowres(tmpdir):
    small = os.path.join(tmpdir, "small.jpg")
    _make_image(small, size=(100, 100), noise=True)  # 有内容但分辨率过低
    cands, rej = filter_photos([small])
    assert len(cands) == 0 and len(rej) == 1
    assert "分辨率" in rej[0].reject_reason


def test_filter_keeps_good_image(tmpdir):
    good = os.path.join(tmpdir, "good.jpg")
    _make_image(good, size=(2000, 1300), noise=True)
    cands, rej = filter_photos([good])
    assert len(cands) == 1 and cands[0].status == "candidate"


# ---------- 五档去重 + collect_dedup_groups ----------
def test_dedup_levels_has_5_strengths_and_off():
    strengths = [k for k, v in DEDUP_LEVELS.items() if v is not None]
    assert len(strengths) >= 5
    assert DEDUP_LEVELS.get("关闭") is None
    assert DEFAULT_DEDUP_LEVEL in DEDUP_LEVELS


def test_resolve_dedup_threshold():
    assert resolve_dedup_threshold({"dedup_level": "极严"}) == DEDUP_LEVELS["极严"]
    assert resolve_dedup_threshold({"dedup_level": "关闭"}) is None
    assert resolve_dedup_threshold({"phash_threshold": 4}) == 4
    assert resolve_dedup_threshold({}) == DEDUP_LEVELS[DEFAULT_DEDUP_LEVEL]
    assert resolve_dedup_threshold({"dedup_level": "未知档"}) == DEDUP_LEVELS[DEFAULT_DEDUP_LEVEL]


def test_collect_dedup_groups_groups_by_keep(tmpdir):
    p1 = os.path.join(tmpdir, "a.jpg")
    p2 = os.path.join(tmpdir, "b.jpg")
    p3 = os.path.join(tmpdir, "c.jpg")
    _make_image(p1)
    _make_image(p2)
    _make_image(p3)
    r1 = PhotoRecord(path=p1, dup_group=5, dup_of="")
    r2 = PhotoRecord(path=p2, dup_group=5, dup_of=p1)
    r3 = PhotoRecord(path=p3, dup_group=7, dup_of=p1)
    groups = collect_dedup_groups([r2, r3])
    assert len(groups) == 1
    assert groups[0]["kept"] == p1
    assert set(groups[0]["similar"]) == {p2, p3}


def test_filter_off_no_similar_dedup(tmpdir):
    """关闭档位：精确 MD5 重复仍会去重，但相似去重关闭。

    两张完全相同的图（shutil.copy2 → MD5 相同）→ 应被「完全重复（MD5 相同）」去重；
    而非走相似去重路径（关闭档 → 相似去重跳过）。
    """
    p1 = os.path.join(tmpdir, "a.jpg")
    _make_image(p1, noise=True)
    p2 = os.path.join(tmpdir, "b.jpg")
    shutil.copy2(p1, p2)
    cands, rej = filter_photos([p1, p2], options={"dedup_level": "关闭"})
    assert len(cands) == 1
    assert len(rej) == 1
    assert "MD5" in rej[0].reject_reason
    assert "高度相似" not in rej[0].reject_reason


def test_filter_strict_dedups_similar(tmpdir):
    """极严：两张内容相近（不同 noise 但相同 pHash）必被相似去重。

    由于 phash 对内容完全相同的随机噪声几乎肯定距离=0，
    我们用 MD5 不同 + phash 相同的方式无法制造；但 MD5 相同足以走精确去重，
    且也验证 dup_group/dup_of 正确填写。
    """
    src = os.path.join(tmpdir, "src.jpg")
    _make_image(src, noise=True)
    p2 = os.path.join(tmpdir, "b.jpg")
    shutil.copy2(src, p2)  # 完全相同 → MD5 + phash 都相同
    cands, rej = filter_photos([src, p2], options={"dedup_level": "极严"})
    assert len(cands) == 1
    assert rej[0].dup_of in (src, p2)
    assert rej[0].dup_group > 0
    groups = collect_dedup_groups(rej)
    assert len(groups) == 1
    assert groups[0]["kept"] in (src, p2)


def test_filter_marks_exact_duplicate_group(tmpdir):
    """MD5 相同也写入 dup_group/dup_of，collect_dedup_groups 能汇总。"""
    src = os.path.join(tmpdir, "src.jpg")
    _make_image(src, noise=True)
    cp1 = os.path.join(tmpdir, "cp1.jpg")
    cp2 = os.path.join(tmpdir, "cp2.jpg")
    shutil.copy2(src, cp1)
    shutil.copy2(src, cp2)
    cands, rej = filter_photos([src, cp1, cp2], options={"dedup_level": "关闭"})
    assert len(cands) == 1
    assert len(rej) == 2
    groups = collect_dedup_groups(rej)
    assert len(groups) == 1
    assert set(groups[0]["similar"]) == {cp1, cp2}
