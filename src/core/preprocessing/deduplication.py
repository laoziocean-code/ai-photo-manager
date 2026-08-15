"""去重与相似检测。

- 精确去重：文件 MD5 完全一致。
- 相似检测：感知哈希（pHash）Hamming 距离，低于阈值视为同一场景的不同拍。

pHash 用纯 numpy 实现 DCT-II（与 imagehash.phash 算法一致），
避免引入 scipy / PyWavelets 依赖，显著减小打包体积。
"""
import hashlib

import numpy as np

from src.core.image_io import load_image

# 去重档位（5 档强度 + 关闭）。键为 UI 展示名，值为 pHash Hamming 距离阈值
# （越低越严格，只有极相似的才判重；越高越宽松，更多连拍/同场景会被去重）。
DEDUP_LEVELS = {
    "关闭": None,   # 不做相似去重（精确 MD5 去重仍会执行）
    "极严": 3,
    "严格": 5,
    "标准": 8,      # 默认
    "宽松": 12,
    "极宽": 18,
}
DEFAULT_DEDUP_LEVEL = "标准"


class PHash:
    """轻量感知哈希（替代 imagehash.ImageHash）。

    支持 -（Hamming 距离）、==、str()，算法与 imagehash.phash 一致。
    """
    __slots__ = ("_bits",)

    def __init__(self, bits):
        self._bits = np.asarray(bits, dtype=bool).flatten()

    def __sub__(self, other) -> int:
        return int(np.count_nonzero(self._bits != other._bits))

    def __eq__(self, other) -> bool:
        if not isinstance(other, PHash):
            return NotImplemented
        return self.__sub__(other) == 0

    def __hash__(self) -> int:
        return hash(self._bits.tobytes())

    def __str__(self) -> str:
        return "".join("1" if b else "0" for b in self._bits)


def _dct2(a: np.ndarray) -> np.ndarray:
    """2D DCT-II（未归一化），等价 scipy.fftpack.dct(type=2, norm=None)。"""
    n = a.shape[0]
    idx = np.arange(n)
    k = idx[:, None]
    c = 2.0 * np.cos(np.pi * k * (2 * idx + 1) / (2 * n))
    return c @ a @ c.T


def resolve_dedup_threshold(options: dict) -> int | None:
    """从 options 解析去重阈值；返回 None 表示不做相似去重。

    优先读 dedup_level；兼容旧的 phash_threshold 直填阈值。
    """
    level = options.get("dedup_level")
    if level is None:
        pt = options.get("phash_threshold")
        return int(pt) if pt is not None else DEDUP_LEVELS[DEFAULT_DEDUP_LEVEL]
    return DEDUP_LEVELS.get(level, DEDUP_LEVELS[DEFAULT_DEDUP_LEVEL])


def compute_md5(path: str, chunk: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def compute_phash(path: str, hash_size: int = 8) -> PHash:
    """返回 PHash 对象（支持 - 运算符求 Hamming 距离）。

    与 imagehash.phash 算法一致：灰度 → 缩放到 (hash_size*4)² → DCT-II →
    取低频 hash_size² 系数与中位数比较成布尔位。
    像素加载统一走 image_io.load_image，RAW（NEF 等）也能正确计算。
    """
    from PIL import Image
    im = load_image(path)
    try:
        gray = im.convert("L").resize((hash_size * 4, hash_size * 4), Image.LANCZOS)
        pixels = np.asarray(gray, dtype=np.float64)
        dct = _dct2(pixels)
        low = dct[:hash_size, :hash_size]
        med = float(np.median(low))
        return PHash(low > med)
    finally:
        im.close()


def find_groups(records, threshold: int = 8):
    """对 records（含 'phash' PHash）做相似聚类。

    返回若干分组，每组是 records 的下标列表；Hamming 距离 <= threshold 归为一组。
    """
    valid = [i for i, r in enumerate(records) if getattr(r, "phash", None) is not None]
    groups = []
    used = set()
    n = len(valid)
    for a in range(n):
        i = valid[a]
        if i in used:
            continue
        grp = [i]
        used.add(i)
        for b in range(a + 1, n):
            j = valid[b]
            if j in used:
                continue
            if (records[i].phash - records[j].phash) <= threshold:
                grp.append(j)
                used.add(j)
        groups.append(grp)
    return groups
