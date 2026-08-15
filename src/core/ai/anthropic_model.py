"""Anthropic 适配器（Claude 原生视觉接口）。

实现 VisionModel 契约：analyze(image_path, prompt) -> dict（已解析）。
"""
import base64
from typing import Any, Dict, Optional

from anthropic import Anthropic

from src.core.ai.response_parser import parse_analysis
from src.core.image_io import encode_jpeg


class AnthropicModel:
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        self.model = model
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = Anthropic(**kwargs)
        self._usage = {"input_tokens": 0, "output_tokens": 0}

    @property
    def usage(self) -> Dict[str, int]:
        """累计 token 用量（跨多次调用累加），供报告统计。"""
        return dict(self._usage)

    def _source(self, path: str) -> Dict[str, Any]:
        # 统一解码为 JPEG（RAW/NEF 无法直接被视觉模型读取）
        data = base64.b64encode(encode_jpeg(path, longest=1280)).decode("ascii")
        return {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": data,
        }

    def analyze(self, image_path: str, prompt: str) -> Dict[str, Any]:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": self._source(image_path)},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        try:
            u = resp.usage
            if u is not None:
                self._usage["input_tokens"] += int(getattr(u, "input_tokens", 0) or 0)
                self._usage["output_tokens"] += int(getattr(u, "output_tokens", 0) or 0)
        except Exception:
            pass
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return parse_analysis(text)
