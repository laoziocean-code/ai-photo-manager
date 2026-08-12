"""视觉模型抽象接口（Step 3 实现）。

统一契约：给定图片路径与提示词，返回 dict（JSON）。
新增模型只需实现一个适配器 + 在 models_config 追加预设。
"""
from typing import Any, Dict, Protocol


class VisionModel(Protocol):
    def analyze(self, image_path: str, prompt: str) -> Dict[str, Any]:
        ...
