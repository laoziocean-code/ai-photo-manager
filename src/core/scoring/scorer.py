"""8 维评分 → 加权总分，并给出等级。

维度与权重（可在界面/配置文件调整）：
composition 构图 / lighting 光影 / color 色彩 / sharpness 清晰度 /
subject 主体突出度 / emotion 情绪感染力 / story 故事感 / publish_value 发布价值。
"""
from typing import Any, Dict

WEIGHTS: Dict[str, float] = {
    "composition": 0.15,
    "lighting": 0.15,
    "color": 0.13,
    "sharpness": 0.12,
    "subject": 0.13,
    "emotion": 0.12,
    "story": 0.10,
    "publish_value": 0.10,
}

# 等级区间（含下界），从高到低匹配
_GRADES = [
    ("S", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 0),
]


def compute_total(scores: Dict[str, Any]) -> float:
    """加权汇总，返回 0-100 的两位小数分数。"""
    total = 0.0
    for k, w in WEIGHTS.items():
        v = scores.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.0
        v = max(0.0, min(100.0, v))
        total += v * w
    return round(total, 2)


def grade(total: float) -> str:
    for name, lower in _GRADES:
        if total >= lower:
            return name
    return "D"
