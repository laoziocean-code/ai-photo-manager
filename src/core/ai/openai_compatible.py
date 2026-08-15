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
        self._usage = {"input_tokens": 0, "output_tokens": 0}

    @property
    def usage(self) -> Dict[str, int]:
        """累计 token 用量（跨多次调用累加），供报告统计。"""
        return dict(self._usage)

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
        try:
            u = resp.usage
            if u is not None:
                self._usage["input_tokens"] += int(getattr(u, "prompt_tokens", 0) or 0)
                self._usage["output_tokens"] += int(getattr(u, "completion_tokens", 0) or 0)
        except Exception:
            pass
        return parse_analysis(resp.choices[0].message.content)
