"""视觉模型预设（OpenAI 兼容接口设计，便于扩展）。

新增模型：在此列表追加一项 + 在 src/core/ai 下提供对应适配器即可，无需改动主流程。

注：智谱（GLM）视觉模型通过 OpenAI 兼容端点接入，base_url 固定为
https://open.bigmodel.cn/api/paas/v4 。当前在役视觉模型 id 主要为
glm-4v-plus（多模态旗舰）/ glm-4v（标准）/ glm-4v-flash（免费）。
用户所说的「GLM-V4」对应此处预设，默认取 glm-4v-plus；若想换具体 id，
可在首页「模型名（可覆盖）」输入框填写。
"""
MODEL_PRESETS = [
    {
        "id": "glm-vision",
        "name": "GLM-V4 (智谱视觉)",
        "provider": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4v-plus",
        "needs_api_key": True,
    },
    {
        "id": "gpt-vision",
        "name": "GPT Vision (OpenAI)",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "needs_api_key": True,
    },
    {
        "id": "gemini-vision",
        "name": "Gemini Vision",
        "provider": "openai",  # Gemini 提供 OpenAI 兼容端点
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
        "needs_api_key": True,
    },
    {
        "id": "claude-vision",
        "name": "Claude Vision (Anthropic)",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-3-5-sonnet-latest",
        "needs_api_key": True,
    },
    {
        "id": "custom",
        "name": "自定义兼容模型",
        "provider": "openai",
        "base_url": "",
        "default_model": "",
        "needs_api_key": True,
    },
]


def get_preset(model_id: str):
    for p in MODEL_PRESETS:
        if p["id"] == model_id:
            return p
    return MODEL_PRESETS[0]
