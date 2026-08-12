"""视觉模型工厂：根据预设 + API Key 构造 VisionModel 实例。

新增模型只需在 models_config.MODEL_PRESETS 追加一项，并在本工厂分支中
对应 provider 即可，主流程无需改动。
"""
from typing import Any

from src.config.models_config import get_preset
from src.core.ai.anthropic_model import AnthropicModel
from src.core.ai.openai_compatible import OpenAICompatibleModel


def build_model(
    model_id: str,
    api_key: str,
    base_url_override: str = "",
    model_override: str = "",
) -> Any:
    preset = get_preset(model_id)
    base = base_url_override or preset.get("base_url", "")
    model = model_override or preset.get("default_model", "")
    if preset.get("provider") == "anthropic":
        return AnthropicModel(api_key=api_key, model=model, base_url=base or None)
    return OpenAICompatibleModel(base_url=base, api_key=api_key, model=model)
