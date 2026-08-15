"""模糊检测（Laplacian 方差）。

原理：清晰图像边缘梯度大，灰度 Laplacian 的方差高；方差低通常意味着失焦/运动模糊。
为稳定阈值，统一缩放到最长边 512 再计算，使经验阈值（默认 80）跨分辨率可用。
"""
import numpy as np

from src.core.image_io import load_gray_small

try:
    import cv2
except Exception:  # 打包/测试环境可能尚未安装 cv2
    cv2 = None


def blur_score(path: str) -> float:
    """返回 Laplacian 方差；数值越高越清晰。

    读取/处理失败返回 999.0（视为「无法评估」，不判为模糊），避免个别
    RAW 缩略图/解码异常时把好照片误杀；真正失焦的图方差依然很低，照常淘汰。
    """
    try:
        arr = load_gray_small(path)
        if cv2 is None:
            # 无 cv2 时的轻量回退：用 numpy 求二阶差分方差
            gx = np.diff(arr.astype(np.float32), axis=1)
            gy = np.diff(arr.astype(np.float32), axis=0)
            lap = gx[:-1, :] + gy[:, :-1] - 2 * arr[:-1, :-1]
            return float(np.var(lap))
        lap = cv2.Laplacian(arr, cv2.CV_64F)
        return float(lap.var())
    except Exception:
        return 999.0


def is_blurry(path: str, threshold: float = 80.0) -> bool:
    return blur_score(path) < threshold
