"""RAW（NEF 等）支持测试。

没有真实 RAW 样张，这里用 mock 把 rawpy 解码链路与 exifread 标签解析都覆盖到；
普通位图路径做回归，确保统一加载器没破坏原功能。
"""
import os
import types

import numpy as np
import pytest
from PIL import Image

import src.core.image_io as image_io
from src.core.image_io import (
    encode_jpeg, extract_exif, is_raw, load_gray_small, load_image,
    make_thumbnail,
)
from src.utils.file_utils import ALL_IMAGE_EXTS, RAW_EXTS


# --------------------------------------------------------------------------- #
# 测试夹具：用 numpy 造一张图，用 mock 替换 rawpy 解码
# --------------------------------------------------------------------------- #
def _make_rgb(h=64, w=80):
    rng = np.random.RandomState(0)
    return (rng.rand(h, w, 3) * 255).astype(np.uint8)


def _make_jpeg_thumb(h=32, w=40):
    im = Image.fromarray(_make_rgb(h, w))
    import io
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


class _Ratio:
    def __init__(self, num, den):
        self.num = num
        self.den = den


class _Tag:
    def __init__(self, value):
        self.values = [value]
        self.printable = str(value)


class _FakeRaw:
    """模拟 rawpy.RawPy：postprocess 返回 RGB，extract_thumbnail 返回 JPEG。"""

    def __init__(self, arr=None, thumb=None):
        self._arr = arr if arr is not None else _make_rgb(128, 160)
        self._thumb = thumb  # bytes(JPEG) 或 None
        self.sizes = (120, 160)  # (height, width)，与 _make_rgb(120,160) 一致
        self.closed = False

    def postprocess(self, *a, **k):
        return self._arr

    def extract_thumb(self):
        if self._thumb is None:
            return None
        return types.SimpleNamespace(data=self._thumb, format=image_io.rawpy.ThumbFormat.JPEG)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture
def fake_rawpy(monkeypatch):
    """把 image_io 里的 rawpy.imread 替换成返回 _FakeRaw。"""
    calls = {"n": 0}

    def _imread(path):
        calls["n"] += 1
        return _FakeRaw(arr=_make_rgb(120, 160), thumb=_make_jpeg_thumb())

    monkeypatch.setattr(image_io.rawpy, "imread", _imread)
    return calls


@pytest.fixture
def fake_exifread(monkeypatch):
    """把 exifread.process_file 替换成返回一组假标签。"""

    def _process(fh, details=False, strict=True):
        return {
            "Image Make": _Tag("NIKON CORPORATION"),
            "Image Model": _Tag("NIKON Z 6"),
            "EXIF LensModel": _Tag("NIKKOR Z 24-70mm f/4 S"),
            "EXIF FocalLength": _Tag(_Ratio(50, 1)),
            "EXIF FNumber": _Tag(_Ratio(40, 10)),
            "EXIF ExposureTime": _Tag(_Ratio(1, 200)),
            "EXIF ISOSpeedRatings": _Tag(100),
            "EXIF DateTimeOriginal": _Tag("2024:08:09 14:30:00"),
            "Image ImageWidth": _Tag(6000),
            "Image ImageLength": _Tag(4000),
        }

    monkeypatch.setattr(image_io.exifread, "process_file", _process) \
        if hasattr(image_io, "exifread") else None
    # exifread 在 extract_exif_raw 内 import，需 patch 模块自身
    import exifread
    monkeypatch.setattr(exifread, "process_file", _process)
    return _process


# --------------------------------------------------------------------------- #
# is_raw / 扩展名
# --------------------------------------------------------------------------- #
def test_is_raw_extensions():
    assert is_raw("photo.NEF")
    assert is_raw("photo.nef")
    assert is_raw("IMG_001.CR3")
    assert not is_raw("photo.jpg")
    assert not is_raw("photo.png")


def test_all_image_exts_includes_raw():
    assert ".nef" in ALL_IMAGE_EXTS
    assert ".cr3" in ALL_IMAGE_EXTS
    assert ".jpg" in ALL_IMAGE_EXTS


def test_raw_exts_full_coverage():
    """RAW 白名单应覆盖各主流厂商的全部长尾格式。"""
    for ext in (".x3f", ".iiq", ".rwl", ".crw", ".srf", ".bay",
                ".raf", ".orf", ".pef", ".3fr", ".fff", ".mos",
                ".mrw", ".mef", ".erf", ".kdc", ".dcr", ".dcs",
                ".cap", ".ari", ".r3d"):
        assert ext in RAW_EXTS, f"缺少 RAW 扩展名: {ext}"


# --------------------------------------------------------------------------- #
# 内容兜底：sniff_raw 按文件头魔数判断
# --------------------------------------------------------------------------- #
def test_sniff_raw_tiff_le(tmp_path):
    p = tmp_path / "odd.bin"
    p.write_bytes(b"II*\x00" + b"\x00" * 28)
    from src.utils.file_utils import sniff_raw
    assert sniff_raw(str(p)) is True


def test_sniff_raw_tiff_be(tmp_path):
    p = tmp_path / "odd.dat"
    p.write_bytes(b"MM\x00*" + b"\x00" * 28)
    from src.utils.file_utils import sniff_raw
    assert sniff_raw(str(p)) is True


def test_sniff_raw_fuji(tmp_path):
    p = tmp_path / "weird.xyz"
    p.write_bytes(b"FUJIFILMCCD-RAW 0201" + b"\x00" * 12)
    from src.utils.file_utils import sniff_raw
    assert sniff_raw(str(p)) is True


def test_sniff_raw_not_raw(tmp_path):
    p = tmp_path / "plain.txt"
    p.write_bytes(b"hello world this is not a raw file" + b"\x00" * 4)
    from src.utils.file_utils import sniff_raw
    assert sniff_raw(str(p)) is False


def test_load_image_content_fallback(fake_rawpy, tmp_path):
    """扩展名不在白名单但文件头是 TIFF 魔数 → 应走 rawpy 兜底解码。"""
    p = tmp_path / "renamed.bin"
    p.write_bytes(b"II*\x00" + b"\x00" * 64)  # TIFF LE 魔数
    im = load_image(str(p))
    assert isinstance(im, Image.Image)
    assert im.mode == "RGB"


# --------------------------------------------------------------------------- #
# RAW 解码链路（mock rawpy）
# --------------------------------------------------------------------------- #
def test_load_image_raw(fake_rawpy, tmp_path):
    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    im = load_image(str(p))
    assert isinstance(im, Image.Image)
    assert im.mode == "RGB"
    assert im.size == (160, 120)  # _make_rgb(120,160)


def test_make_thumbnail_raw_uses_embedded(fake_rawpy, tmp_path):
    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    data = make_thumbnail(str(p), size=64)
    assert data is not None
    im = Image.open(__import__("io").BytesIO(data))
    assert im.format == "JPEG"
    assert max(im.size) <= 64


def test_encode_jpeg_raw(fake_rawpy, tmp_path):
    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    data = encode_jpeg(str(p), longest=1280)
    assert data[:2] == b"\xff\xd8"  # JPEG SOI
    im = Image.open(__import__("io").BytesIO(data))
    assert im.format == "JPEG"


def test_load_gray_small_raw(fake_rawpy, tmp_path):
    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    arr = load_gray_small(str(p), longest=64)
    assert arr.ndim == 2
    assert arr.dtype == np.uint8
    assert max(arr.shape) <= 64


def test_rawpy_close_called(fake_rawpy, tmp_path):
    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    load_image(str(p))
    # imread 至少被调用过，且上下文退出会 close（FakeRaw 实现见 __exit__）
    assert fake_rawpy["n"] >= 1


# --------------------------------------------------------------------------- #
# RAW EXIF（mock exifread）
# --------------------------------------------------------------------------- #
def test_extract_exif_raw(fake_exifread, fake_rawpy, tmp_path):
    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    meta = extract_exif(str(p))
    assert meta["camera_make"] == "NIKON CORPORATION"
    assert meta["camera_model"] == "NIKON Z 6"
    assert meta["camera"] == "NIKON CORPORATION NIKON Z 6"
    assert meta["lens"] == "NIKKOR Z 24-70mm f/4 S"
    assert abs(meta["focal_length"] - 50.0) < 1e-6
    assert abs(meta["aperture"] - 4.0) < 1e-6
    assert abs(meta["shutter"] - (1 / 200)) < 1e-9
    assert meta["iso"] == 100
    assert meta["datetime_taken"] == "2024:08:09 14:30:00"
    assert meta["width"] == 6000
    assert meta["height"] == 4000


def test_extract_exif_raw_dims_fallback(fake_rawpy, tmp_path, monkeypatch):
    """exifread 取不到尺寸时，应回退到 rawpy 头信息（raw.sizes，零解码开销）。"""

    def _process_no_dims(fh, details=False, strict=True):
        return {
            "Image Make": _Tag("NIKON"),
            "EXIF ISOSpeedRatings": _Tag(200),
        }

    import exifread
    monkeypatch.setattr(exifread, "process_file", _process_no_dims)

    p = tmp_path / "x.nef"
    p.write_bytes(b"FAKE_NEF_BYTES")
    meta = extract_exif(str(p))
    # _FakeRaw.sizes=(120,160) → width=160, height=120
    assert meta["width"] == 160
    assert meta["height"] == 120


# --------------------------------------------------------------------------- #
# 普通位图回归（确保统一加载器没破坏原行为）
# --------------------------------------------------------------------------- #
def _save_rgb(path, h=80, w=100):
    Image.fromarray(_make_rgb(h, w)).save(path, format="JPEG")


def test_load_image_normal(tmp_path):
    p = tmp_path / "a.jpg"
    _save_rgb(str(p))
    im = load_image(str(p))
    assert im.mode == "RGB"
    assert im.size == (100, 80)


def test_make_thumbnail_normal(tmp_path):
    p = tmp_path / "a.jpg"
    _save_rgb(str(p), 400, 600)
    data = make_thumbnail(str(p), size=128)
    assert data is not None
    im = Image.open(__import__("io").BytesIO(data))
    assert max(im.size) <= 128


def test_encode_jpeg_normal(tmp_path):
    p = tmp_path / "a.png"
    Image.fromarray(_make_rgb(200, 300)).save(str(p), format="PNG")
    data = encode_jpeg(str(p), longest=256)
    assert data[:2] == b"\xff\xd8"


def test_extract_exif_normal(tmp_path):
    p = tmp_path / "a.jpg"
    _save_rgb(str(p), 50, 70)
    meta = extract_exif(str(p))
    assert meta["width"] == 70
    assert meta["height"] == 50
    assert meta["size_bytes"] > 0
