"""统一的照片记录数据结构（贯穿预处理 → AI → 精选 → 报告）。

一个 PhotoRecord 承载从磁盘读取到最终输出的全部信息：
- 基础：路径、尺寸、EXIF
- 本地预处理：md5 / phash / 模糊度 / 曝光 / 分辨率 / 状态
- AI：解析后的评分与建议
- 汇总：总分
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.core.image_io import ImageMeta


@dataclass
class PhotoRecord:
    path: str
    meta: ImageMeta = field(default_factory=lambda: ImageMeta(path=""))

    md5: str = ""
    phash: Any = None          # imagehash.ImageHash 对象（运行时用）
    phash_str: str = ""

    blur: float = 0.0
    is_blurry: bool = False
    exposure: Dict[str, Any] = field(default_factory=dict)  # mean/under/over/verdict
    resolution_ok: bool = True

    status: str = "pending"    # pending | candidate | rejected
    reject_reason: str = ""

    # 去重归属：被去重照片记录所在组号与保留代表的路径（用于报告展示）
    dup_group: int = -1        # -1 表示不属于任何去重组
    dup_of: str = ""           # 保留代表文件的路径；空表示它自己是代表

    # AI 分析产物（由 response_parser 解析后的 dict）
    ai: Dict[str, Any] = field(default_factory=dict)
    total_score: float = 0.0

    @property
    def name(self) -> str:
        import os
        return os.path.basename(self.path)
