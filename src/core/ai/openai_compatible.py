"""OpenAI 兼容适配器（覆盖 GPT / Gemini / GLM / 任意 OpenAI 兼容端点）。

实现 VisionModel 契约：analyze(image_path, prompt) -> dict（已解析）。
"""
import base64
from typing import Any, Dict

from openai import OpenAI

from src.core.ai.response_parser import parse_analysis
from src.core.image_io import encode_jpeg


class OpenAICompatibleModel:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.model = model
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def _data_url(self, path: str) -> str:
        # 统一解码为 JPEG（RAW/NEF 无法直接被视觉模型读取）
        b64 = base64.b64encode(encode_jpeg(path, longest=1280)).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def analyze(self, image_path: str, prompt: str) -> Dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": self._data_url(image_path)}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=2000,
            temperature=0.4,
        )
        return parse_analysis(resp.choices[0].message.content)
