"""Lightroom 修图建议：结构归一化 + 中文展示。

AI 返回 lr_advice（JSON 对象），这里负责：
- normalize_lr：补全缺失键，保证下游不 KeyError。
- format_lr：整理为适合报告/界面展示的多行中文文本。
"""
from typing import Any, Dict


def normalize_lr(lr: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "style": "", "exposure": 0, "highlights": 0,
        "shadows": 0, "temperature": 0, "hsl": "", "explanation": "",
    }
    if not isinstance(lr, dict):
        return base
    merged = {**base, **lr}
    try:
        merged["exposure"] = float(merged["exposure"])
    except (TypeError, ValueError):
        merged["exposure"] = 0.0
    for k in ("highlights", "shadows", "temperature"):
        try:
            merged[k] = int(merged[k])
        except (TypeError, ValueError):
            merged[k] = 0
    return merged


def format_lr(lr: Dict[str, Any]) -> str:
    lr = normalize_lr(lr)
    if not any([lr["style"], lr["exposure"], lr["highlights"],
                lr["shadows"], lr["temperature"], lr["hsl"], lr["explanation"]]):
        return "（暂无明显调整建议）"
    lines = []
    if lr["style"]:
        lines.append(f"风格：{lr['style']}")
    if lr["exposure"]:
        lines.append(f"曝光：{lr['exposure']:+.2f}")
    if lr["highlights"]:
        lines.append(f"高光：{lr['highlights']:+d}")
    if lr["shadows"]:
        lines.append(f"阴影：{lr['shadows']:+d}")
    if lr["temperature"]:
        lines.append(f"色温：{lr['temperature']:+d}")
    if lr["hsl"]:
        lines.append(f"HSL：{lr['hsl']}")
    if lr["explanation"]:
        lines.append(f"说明：{lr['explanation']}")
    return "\n".join(lines)
