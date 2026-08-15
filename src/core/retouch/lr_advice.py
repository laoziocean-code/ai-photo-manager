"""Lightroom 修图建议：结构归一化 + 中文展示 + 可复制参数。

AI 返回 lr_advice（JSON 对象），这里负责：
- normalize_lr：补全缺失键，保证下游不 KeyError。
- format_lr：整理为适合界面展示的多行中文文本（风格/说明等散文）。
- lr_params：数值型参数列表（曝光度/高光/阴影/色温），供报告表格化展示。
- lr_copy_text：可直接复制粘贴进 Lightroom 的参数文本块。
"""
from typing import Any, Dict, List

# Lightroom「基本」面板滑块：键名 → (中文显示名, 数值类型)
_LR_PARAM_LABELS = [
    ("exposure", "曝光度", "float"),
    ("highlights", "高光", "int"),
    ("shadows", "阴影", "int"),
    ("temperature", "色温", "int"),
]


def _fmt_value(v: Any, kind: str) -> str:
    if kind == "float":
        return f"{v:+.2f}"
    return f"{v:+d}"


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


def lr_params(lr: Dict[str, Any]) -> List[Dict[str, str]]:
    """数值型参数列表：[{label, value}]，仅包含非零项。"""
    lr = normalize_lr(lr)
    out = []
    for key, label, kind in _LR_PARAM_LABELS:
        v = lr[key]
        if v:
            out.append({"label": label, "value": _fmt_value(v, kind)})
    return out


def lr_copy_text(lr: Dict[str, Any]) -> str:
    """可直接复制进 Lightroom 的参数块（一行一项，数值带符号）。"""
    lr = normalize_lr(lr)
    lines = []
    if lr["style"]:
        lines.append(f"风格：{lr['style']}")
    for key, label, kind in _LR_PARAM_LABELS:
        v = lr[key]
        if v:
            lines.append(f"{label} {_fmt_value(v, kind)}")
    if lr["hsl"]:
        lines.append(f"HSL/颜色：{lr['hsl']}")
    return "\n".join(lines)


def lr_note(lr: Dict[str, Any]) -> str:
    """调整理由（散文说明）。"""
    lr = normalize_lr(lr)
    return (lr.get("explanation") or "").strip()


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
