"""文件与路径工具：长路径、中文路径、图片枚举。"""
import os
from pathlib import Path

# 普通位图
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
# 相机 RAW（NEF 为主，顺带覆盖主流机型以免日后扩展）—— 需 rawpy 解码
RAW_EXTS = {
    ".nef", ".nrw",            # 尼康 Nikon
    ".cr2", ".cr3",            # 佳能 Canon
    ".arw", ".sr2", ".srw",    # 索尼 Sony
    ".dng",                    # 数码负片（Adobe / 多机型）
    ".rw2",                    # 松下 Panasonic
    ".raf",                    # 富士 Fujifilm
    ".orf",                    # 奥林巴斯 Olympus
    ".pef",                    # 宾得 Pentax
    ".3fr", ".fff",            # 哈苏 Hasselblad
    ".erf",                    # 爱普生 Epson
    ".mef", ".mrw",            # 玛米亚 / 美能达
    ".kdc", ".dcr", ".mos",    # 柯达 / 柯尼卡美能达
}
ALL_IMAGE_EXTS = IMAGE_EXTS | RAW_EXTS


def normalize_path(p: str) -> str:
    """规范化并加 Windows 长路径前缀，规避 260 字符限制与中文路径问题。"""
    p = os.path.abspath(os.path.normpath(p))
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + p
    return p


def list_images(folder: str):
    """递归枚举文件夹下所有受支持图片。"""
    folder = normalize_path(folder)
    result = []
    for root, _, files in os.walk(folder):
        for f in files:
            if Path(f).suffix.lower() in ALL_IMAGE_EXTS:
                result.append(os.path.join(root, f))
    return result


def safe_filename(name: str) -> str:
    for c in '<>:"/\\|?*':
        name = name.replace(c, "_")
    return name
