"""端到端流水线测试（用 Mock 模型，无需真实 API / 网络）。

验证：本地预处理 → AI 解析（mock）→ 加权评分 → TopN 精选导出 → HTML 报告，
整套 AnalysisController.run 串联正确。
"""
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest
from PIL import Image

# 确保项目根在 sys.path（pytest 根 conftest 已加，这里双保险）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.controllers import analysis_controller
from src.core.ai.response_parser import parse_analysis


class FakeModel:
    def __init__(self):
        self._usage = {"input_tokens": 0, "output_tokens": 0}

    def analyze(self, image_path, prompt):
        # 直接返回已解析结构，模拟一次成功的视觉模型调用
        self._usage["input_tokens"] += 120
        self._usage["output_tokens"] += 60
        raw = (
            '{"scores":{"composition":82,"lighting":78,"color":70,"sharpness":88,'
            '"subject":80,"emotion":75,"story":66,"publish_value":85},'
            '"review":"光线与构图都不错，可再压一点高光。",'
            '"lr_advice":{"style":"胶片清新","exposure":0.2,"highlights":-15,'
            '"shadows":10,"temperature":8,"hsl":"橙色稍提","explanation":"平衡肤色"},'
            '"category":"人像","publish":{"best_platform":"小红书","title":"午后",'
            '"description":"安静的午后","tags":["人像","日常"]},'
            '"portrait":{"expression":"自然","eyes":"有神","pose":"放松",'
            '"background":"干净","skin":"通透"}}'
        )
        return parse_analysis(raw)

    @property
    def usage(self) -> dict:
        return dict(self._usage)


def _make_image(path, size=(2000, 1300), color=(120, 120, 120), noise=False):
    if noise:
        arr = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        Image.fromarray(arr).save(path)
    else:
        Image.new("RGB", size, color).save(path)


@pytest.fixture
def workdir():
    d = tempfile.mkdtemp()
    try:
        photos = os.path.join(d, "photos")
        out = os.path.join(d, "out")
        os.makedirs(photos)
        _make_image(os.path.join(photos, "good.jpg"), noise=True)
        _make_image(os.path.join(photos, "small.jpg"), size=(100, 100))   # 应被分辨率淘汰
        _make_image(os.path.join(photos, "dark.jpg"), color=(4, 4, 4))     # 应被曝光淘汰
        yield photos, out
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_pipeline_end_to_end(workdir, monkeypatch):
    photos, out = workdir
    monkeypatch.setattr(analysis_controller, "build_model", lambda *a, **k: FakeModel())

    from src.app.controllers.analysis_controller import AnalysisController
    from src.utils.file_utils import list_images

    paths = list_images(photos)
    ctrl = AnalysisController()
    summary = {}
    ctrl.run(
        paths, "gpt-vision", "fake-key", out, top_n=10,
        on_done=lambda s: summary.update(s),
    )

    results = summary.get("results", [])
    tier1 = summary.get("tier1", [])
    tier2 = summary.get("tier2", [])
    tier3 = summary.get("tier3", [])
    rejected = summary.get("rejected", [])

    # 好图进入候选并拿到 AI 评分
    assert any(r.name == "good.jpg" and r.total_score > 0 for r in results)
    # 小图 / 暗图被本地预处理淘汰
    assert any(r.name == "small.jpg" for r in rejected)
    assert any(r.name == "dark.jpg" for r in rejected)
    # 精选 + 三档总计
    assert len(tier1) + len(tier2) + len(tier3) >= 1
    assert len(tier1) >= 1
    # 统计信息：耗时 / AI 评分数 / Token / 节省人工时间
    assert summary.get("duration_sec", 0) >= 0
    assert summary.get("ai_count", 0) >= 1
    tokens = summary.get("tokens") or {}
    assert tokens.get("total", 0) >= 180  # 每张 120+60
    assert summary.get("saved_sec", 0) > 0
    assert summary.get("saved_time", "") != ""
    # 精选导出与报告
    assert os.path.isdir(os.path.join(out, "AI精选"))
    # 不再生成 xlsx 清单
    assert not os.path.exists(os.path.join(out, "AI精选", "精选清单.xlsx"))
    report = os.path.join(out, "摄影报告.html")
    assert os.path.exists(report)
    html = open(report, encoding="utf-8").read()
    assert "good.jpg" in html and "data:image/jpeg;base64" in html
    # 报告含统计信息
    assert "Token 消耗" in html
    assert "节省人工时间" in html
