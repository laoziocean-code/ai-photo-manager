"""AI JSON 输出校验与容错解析。

职责：
- 从模型返回文本中抽取 JSON（兼容 ```json 代码块、前后多余文字）。
- 校验 8 维评分必填且落在 0-100，缺失/越界以 0 或最近边界补全。
- 补全 lr_advice / publish / category / portrait 的默认结构，避免后续流程因 KeyError 崩溃。
"""
import json
import re
from typing import Any, Dict

SCORE_KEYS = [
    "composition", "lighting", "color", "sharpness",
    "subject", "emotion", "story", "publish_value",
]
CATEGORY_VALUES = {"人像", "风景", "建筑", "星空", "美食", "旅行", "其他"}


def _extract_json(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = raw.strip()
    # 尝试 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # 退而求其次：截取首个 { 到末个 }
    if "{" in text and "}" in text:
        start, end = text.find("{"), text.rfind("}")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return {}


def _clamp_score(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, f))


def _default_lr() -> Dict[str, Any]:
    return {
        "style": "", "exposure": 0, "highlights": 0,
        "shadows": 0, "temperature": 0, "hsl": "", "explanation": "",
    }


def _default_publish() -> Dict[str, Any]:
    return {"best_platform": "", "title": "", "description": "", "tags": []}


def parse_analysis(raw: str) -> Dict[str, Any]:
    data = _extract_json(raw)
    if not isinstance(data, dict):
        data = {}

    scores = data.get("scores", {}) if isinstance(data.get("scores"), dict) else {}
    clean_scores = {k: _clamp_score(scores.get(k)) for k in SCORE_KEYS}

    review = data.get("review")
    review = review if isinstance(review, str) else ""

    lr = data.get("lr_advice")
    if not isinstance(lr, dict):
        lr = _default_lr()
    else:
        lr = {**_default_lr(), **lr}

    category = data.get("category")
    if category not in CATEGORY_VALUES:
        category = "其他"

    pub = data.get("publish")
    if not isinstance(pub, dict):
        pub = _default_publish()
    else:
        pub = {**_default_publish(), **pub}
        if not isinstance(pub.get("tags"), list):
            pub["tags"] = []

    portrait = data.get("portrait")
    if category != "人像":
        portrait = None
    elif not isinstance(portrait, dict):
        portrait = {
            "expression": "", "eyes": "", "pose": "",
            "background": "", "skin": "",
        }

    return {
        "scores": clean_scores,
        "review": review,
        "lr_advice": lr,
        "category": category,
        "publish": pub,
        "portrait": portrait,
    }


def format_publish(pub: Dict[str, Any]) -> str:
    if not pub:
        return ""
    parts = []
    if pub.get("best_platform"):
        parts.append(f"平台：{pub['best_platform']}")
    if pub.get("title"):
        parts.append(f"标题：{pub['title']}")
    if pub.get("description"):
        parts.append(f"简介：{pub['description']}")
    tags = pub.get("tags") or []
    if tags:
        parts.append("标签：" + " ".join(f"#{t}" for t in tags))
    return "\n".join(parts)
