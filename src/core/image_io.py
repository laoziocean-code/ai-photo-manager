"""图像读取、缩略图、EXIF 提取，统一支持普通位图与相机 RAW（NEF 等）。

普通位图走 Pillow；RAW（.nef/.cr2/.arw/.dng ...）走 rawpy（基于 LibRaw）解码。
所有异常被吞掉并以安全值返回，保证批量处理不中断。
rawpy 缺失时自动回退：RAW 文件将无法解码（返回 None/空），但普通位图流程不受影响。
"""
import os
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image, ExifTags

try:
    import rawpy
except Exception:  # 某些环境未装 rawpy，降级处理
    rawpy = None

from src.utils.file_utils import RAW_EXTS

# 我们关心的 EXIF 标签 → 内部字段名（普通位图，Pillow 路径）
_EXIF_MAP = {
    "Make": "camera_make",
    "Model": "camera_model",
    "LensModel": "lens",
    "FocalLength": "focal_length",
    "FNumber": "aperture",
    "ExposureTime": "shutter",
    "ISO": "iso",
    "DateTimeOriginal": "datetime_taken",
}
_RATIONAL_TAGS = {"FocalLength", "FNumber", "ExposureTime"}

# RAW（exifread）标签映射： (exifread 标签名, 内部字段名, 数值类型)
# kind ∈ {"str", "int", "ratio"}
_EXIFREAD_MAP = [
    ("Image Make", "camera_make", "str"),
    ("Image Model", "camera_model", "str"),
    ("EXIF LensModel", "lens", "str"),
    ("EXIF FocalLength", "focal_length", "ratio"),
    ("EXIF FNumber", "aperture", "ratio"),
    ("EXIF ExposureTime", "shutter", "ratio"),
    ("EXIF ISOSpeedRatings", "iso", "int"),
    ("EXIF DateTimeOriginal", "datetime_taken", "str"),
]


@dataclass
class ImageMeta:
    path: str
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    exif: Dict[str, Any] = field(default_factory=dict)


def is_raw(path: str) -> bool:
    """判断是否为相机 RAW 文件（需 rawpy 解码）。"""
    return Path(path).suffix.lower() in RAW_EXTS


def _to_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# RAW 解码辅助
# --------------------------------------------------------------------------- #
def _raw_open(path: str):
    """返回一个已打开的 rawpy RawPy 对象（上下文管理器）；无 rawpy 时返回 None。"""
    if rawpy is None:
        return None
    try:
        return rawpy.imread(path)
    except Exception:
        return None


def _rgb_from_raw(raw) -> Optional[np.ndarray]:
    """把 RawPy 对象转成 RGB numpy 数组；失败返回 None。"""
    try:
        # half_size 减半分辨率即可满足缩略图/AI 分析，省内存
        params = rawpy.Params(
            half_size=True,
            use_camera_wb=True,
            output_color=rawpy.ColorSpace.sRGB,
            no_auto_bright=False,
        )
        return raw.postprocess(params=params)
    except Exception:
        try:
            return raw.postprocess(params=rawpy.Params(use_camera_wb=True))
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# EXIF 提取
# --------------------------------------------------------------------------- #
def extract_exif(path: str) -> Dict[str, Any]:
    """返回包含尺寸与拍摄参数的 dict；失败返回安全空值。"""
    if is_raw(path):
        return _extract_exif_raw(path)
    return _extract_exif_pillow(path)


def _extract_exif_pillow(path: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    try:
        with Image.open(path) as im:
            meta["width"] = im.width
            meta["height"] = im.height
            meta["size_bytes"] = os.path.getsize(path)
            raw = im.getexif()
            for tid, val in raw.items():
                tag = ExifTags.TAGS.get(tid, str(tid))
                if tag in _EXIF_MAP:
                    meta[_EXIF_MAP[tag]] = (
                        _to_float(val) if tag in _RATIONAL_TAGS else str(val)
                    )
            # Exif 子 IFD（0x8769）：含 DateTimeOriginal / LensModel 等
            try:
                ifd = raw.get_ifd(0x8769)
                for tid, val in ifd.items():
                    tag = ExifTags.TAGS.get(tid, str(tid))
                    if tag in _EXIF_MAP:
                        meta[_EXIF_MAP[tag]] = (
                            _to_float(val) if tag in _RATIONAL_TAGS else str(val)
                        )
            except Exception:
                pass
    except Exception:
        return meta

    cam = " ".join(str(meta.get(k, "")) for k in ("camera_make", "camera_model")).strip()
    if cam:
        meta["camera"] = cam
    return meta


def _exifread_num(tag, kind: str) -> Any:
    """从 exifread 标签对象中提取数值/字符串。"""
    if tag is None:
        return None
    try:
        vals = getattr(tag, "values", None)
        if kind == "str":
            printable = getattr(tag, "printable", None)
            s = str(printable if printable is not None else tag).strip()
            return s or None
        if vals:
            r = vals[0]
            if hasattr(r, "den"):
                return float(r.num) / float(r.den) if r.den else float(r.num)
            return float(r) if kind == "ratio" else int(r)
        return float(str(tag))
    except Exception:
        return None


def _extract_exif_raw(path: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"width": 0, "height": 0, "size_bytes": 0}
    try:
        meta["size_bytes"] = os.path.getsize(path)
    except Exception:
        pass

    w = h = None
    try:
        import exifread
        with open(path, "rb") as fh:
            tags = exifread.process_file(fh, details=False, strict=True)
        for src, dst, kind in _EXIFREAD_MAP:
            v = _exifread_num(tags.get(src), kind)
            if v is not None:
                meta[dst] = v
        # 传感器尺寸（用于分辨率过滤）：优先 IFD0 的 ImageWidth/ImageLength
        w = _exifread_num(tags.get("Image ImageWidth"), "int")
        h = _exifread_num(tags.get("Image ImageLength"), "int")
    except Exception:
        pass

    # 尺寸回退：exifread 取不到时用 rawpy 解码一帧（开销较大，仅兜底）
    if not w or not h:
        raw = _raw_open(path)
        if raw is not None:
            try:
                arr = raw.postprocess()
                h, w = arr.shape[:2]
            except Exception:
                pass
            try:
                raw.close()
            except Exception:
                pass

    if w:
        meta["width"] = w
    if h:
        meta["height"] = h

    cam = " ".join(str(meta.get(k, "")) for k in ("camera_make", "camera_model")).strip()
    if cam:
        meta["camera"] = cam
    return meta


# --------------------------------------------------------------------------- #
# 像素加载
# --------------------------------------------------------------------------- #
def load_image(path: str) -> Image.Image:
    """加载为 RGB PIL 图像（普通位图或解码后的 RAW）。"""
    if is_raw(path):
        raw = _raw_open(path)
        if raw is not None:
            try:
                arr = _rgb_from_raw(raw)
                if arr is not None:
                    return Image.fromarray(arr)
            finally:
                try:
                    raw.close()
                except Exception:
                    pass
        raise ValueError(f"无法解码 RAW 文件：{path}（可能缺少 rawpy 或文件损坏）")
    return Image.open(path).convert("RGB")


def load_gray_small(path: str, longest: int = 512) -> np.ndarray:
    """统一加载灰度小图（最长边 <= longest），供模糊/曝光检测使用。

    RAW 优先用内嵌 JPEG 缩略图（极快），缺失时降级到解码。
    """
    if is_raw(path) and rawpy is not None:
        raw = _raw_open(path)
        im = None
        if raw is not None:
            try:
                thumb = raw.extract_thumb()
                if thumb is not None and getattr(thumb, "format", None) == rawpy.ThumbFormat.JPEG:
                    im = Image.open(BytesIO(thumb.data))
                else:
                    arr = _rgb_from_raw(raw)
                    if arr is not None:
                        im = Image.fromarray(arr)
            except Exception:
                im = None
            finally:
                try:
                    raw.close()
                except Exception:
                    pass
        if im is None:
            return _gray_pillow(path, longest)
        im = im.convert("L")
        w, h = im.size
        scale = min(1.0, longest / max(w, h))
        if scale < 1.0:
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        return np.array(im, dtype=np.uint8)
    return _gray_pillow(path, longest)


def _gray_pillow(path: str, longest: int = 512) -> np.ndarray:
    with Image.open(path) as im:
        im = im.convert("L")
        w, h = im.size
        scale = min(1.0, longest / max(w, h))
        if scale < 1.0:
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        return np.array(im, dtype=np.uint8)


def make_thumbnail(path: str, size: int = 512) -> Optional[bytes]:
    """返回 JPEG 缩略图字节（用于报告内嵌/界面展示）；失败返回 None。

    RAW 优先使用内嵌 JPEG 缩略图（零解码开销），否则解码后缩放。
    """
    if is_raw(path) and rawpy is not None:
        return _thumb_raw(path, size)
    try:
        with Image.open(path) as im:
            im.thumbnail((size, size))
            buf = BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return None


def _thumb_raw(path: str, size: int = 512) -> Optional[bytes]:
    raw = _raw_open(path)
    if raw is None:
        return None
    try:
        thumb = raw.extract_thumb()
        if thumb is not None and getattr(thumb, "format", None) == rawpy.ThumbFormat.JPEG:
            with Image.open(BytesIO(thumb.data)) as im:
                im.thumbnail((size, size))
                buf = BytesIO()
                im.convert("RGB").save(buf, format="JPEG", quality=85)
                return buf.getvalue()
        # 无内嵌缩略图：解码后缩放
        arr = _rgb_from_raw(raw)
        if arr is None:
            return None
        im = Image.fromarray(arr)
        im.thumbnail((size, size))
        buf = BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return None
    finally:
        try:
            raw.close()
        except Exception:
            pass


def encode_jpeg(path: str, longest: int = 1280) -> bytes:
    """把任意受支持图片（含 RAW）编码为用于发送给视觉模型的 JPEG 字节。

    视觉模型无法读取 RAW 原文件，必须在此统一解码为 JPEG。
    """
    im = load_image(path)
    im = im.convert("RGB")
    w, h = im.size
    scale = min(1.0, longest / max(w, h))
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# 中文展示
# --------------------------------------------------------------------------- #
_HUMAN_KEYS = [
    ("camera", "相机"),
    ("lens", "镜头"),
    ("iso", "ISO"),
    ("aperture", "光圈"),
    ("shutter", "快门"),
    ("focal_length", "焦距"),
    ("datetime_taken", "拍摄时间"),
]


def humanize_exif(meta: Dict[str, Any]) -> Dict[str, str]:
    """把数值型 EXIF 整理成中文展示串。"""
    out: Dict[str, str] = {}
    if not meta:
        return out
    if meta.get("camera"):
        out["相机"] = meta["camera"]
    if meta.get("lens"):
        out["镜头"] = meta["lens"]
    if meta.get("iso"):
        out["ISO"] = str(meta["iso"])
    if meta.get("aperture"):
        out["光圈"] = f"f/{float(meta['aperture']):.1f}"
    if meta.get("shutter"):
        s = float(meta["shutter"])
        out["快门"] = f"1/{round(1 / s)}s" if s < 1 else f"{s:.1f}s"
    if meta.get("focal_length"):
        out["焦距"] = f"{float(meta['focal_length']):.0f}mm"
    if meta.get("datetime_taken"):
        out["拍摄时间"] = str(meta["datetime_taken"])
    return out
