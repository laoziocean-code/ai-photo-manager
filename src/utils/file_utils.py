"""文件与路径工具：长路径、中文路径、图片枚举。

RAW 支持策略（覆盖「所有相机 RAW 格式」）：
1. 扩展名白名单 `RAW_EXTS`：收录 LibRaw 支持的全部主流与长尾厂商格式。
2. 内容兜底 `sniff_raw(path)`：当扩展名不在白名单（或被改名）时，按文件头
   魔数判断是否为 RAW（TIFF 字节序 / 富士 FUJIFILMCCD-RAW / Phase One 等），
   交由 rawpy 尝试解码，做到「能读就读」。
"""
import os
from pathlib import Path

# 普通位图
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# 相机 RAW —— 需 rawpy（基于 LibRaw）解码。
# 收录 LibRaw 官方支持的全部厂商原始格式，做到「所有 RAW 格式」全覆盖。
RAW_EXTS = {
    # 尼康 Nikon
    ".nef", ".nrw",
    # 佳能 Canon
    ".crw", ".cr2", ".cr3",
    # 索尼 Sony
    ".arw", ".srf", ".sr2", ".srw",
    # Adobe 数码负片（多机型通用）
    ".dng",
    # 松下 Panasonic / 徕卡 Leica
    ".raw", ".rw2", ".rwl",
    # 富士 Fujifilm
    ".raf",
    # 奥林巴斯 Olympus
    ".orf",
    # 宾得 Pentax
    ".pef",
    # 哈苏 Hasselblad
    ".3fr", ".fff",
    # 飞思 Phase One / Leaf
    ".iiq", ".cap", ".mos",
    # 玛米亚 Mamiya
    ".mef",
    # 美能达 Minolta
    ".mrw",
    # 爱普生 Epson
    ".erf",
    # 柯达 Kodak
    ".kdc", ".dcr", ".dcs", ".drf",
    # 适马 Sigma
    ".x3f",
    # 卡西欧 Casio
    ".bay",
    # Sinar
    ".cs1",
    # RED / ARRI 电影机
    ".r3d", ".ari",
    # 其它长尾（LibRaw 历史支持）
    ".j6i", ".kc2", ".mdc", ".nut", ".pxn", ".qtk", ".stx",
}
ALL_IMAGE_EXTS = IMAGE_EXTS | RAW_EXTS

# 文件头魔数（用于扩展名不在白名单时的内容兜底判断）
# 多数 RAW 基于 TIFF（字节序标记 0x49492A00 "II*\0" 或 0x4D4D002A "MM\0*"），
# 富士 RAF 有独立魔数，Phase One IIQ 也是 TIFF 变体。
_TIFF_LE = b"II*\x00"      # little-endian TIFF
_TIFF_BE = b"MM\x00*"      # big-endian TIFF
_FUJI_MAGIC = b"FUJIFILMCCD-RAW"  # 富士 RAF


def normalize_path(p: str) -> str:
    """规范化并加 Windows 长路径前缀，规避 260 字符限制与中文路径问题。"""
    p = os.path.abspath(os.path.normpath(p))
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + p
    return p


def sniff_raw(path: str) -> bool:
    """按文件头魔数判断是否「可能」是 RAW（扩展名兜底，零依赖、仅读前 32 字节）。

    用于扩展名被改名 / 不在白名单时的兜底：返回 True 时建议交由 rawpy 尝试解码。
    注意：普通 TIFF 也会命中 TIFF 魔数，因此本函数仅作「值得让 rawpy 试一下」的
    信号，不保证一定能解码。
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(32)
    except OSError:
        return False
    if not head:
        return False
    if head.startswith(_FUJI_MAGIC):
        return True
    # TIFF 字节序标记（覆盖 CR2/NEF/ARW/DNG/ORF/RW2/IIQ/PEF 等 TIFF 变体）
    if head[:4] == _TIFF_LE or head[:4] == _TIFF_BE:
        return True
    return False


def list_images(folder: str):
    """递归枚举文件夹下所有受支持图片（含 RAW 白名单）。"""
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
