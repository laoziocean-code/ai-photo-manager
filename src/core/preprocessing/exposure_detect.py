"""过曝/欠曝检测（灰度直方图分析）。

依据整图平均亮度 + 暗部/亮部像素占比判定；严重欠曝/过曝会被本地预处理直接淘汰。
"""
import numpy as np

from src.core.image_io import load_gray_small

try:
    import cv2
except Exception:
    cv2 = None


def exposure_stats(path: str) -> dict:
    """返回 {mean, under, over, verdict}；失败返回安全默认。

    under/over 为暗(<-25)/亮(>230)像素占比；verdict ∈
    正常/欠曝/过曝/严重欠曝/严重过曝/未知。
    像素加载统一走 image_io.load_gray_small，RAW（NEF 等）也能正确判曝光。
    """
    try:
        arr = load_gray_small(path, longest=512)
        mean = float(arr.mean())
        under = float((arr < 25).mean())
        over = float((arr > 230).mean())
        if under > 0.45 and mean < 70:
            verdict = "严重欠曝"
        elif over > 0.45 and mean > 185:
            verdict = "严重过曝"
        elif under > 0.25:
            verdict = "欠曝"
        elif over > 0.25:
            verdict = "过曝"
        else:
            verdict = "正常"
        return {
            "mean": round(mean, 1),
            "under": round(under, 3),
            "over": round(over, 3),
            "verdict": verdict,
        }
    except Exception:
        return {"mean": 0.0, "under": 0.0, "over": 0.0, "verdict": "未知"}


def classify_exposure(path: str) -> str:
    return exposure_stats(path)["verdict"]
