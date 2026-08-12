from src.core.ai.response_parser import format_publish, parse_analysis

RAW_FENCED = """```json
{
 "scores":{"composition":80,"lighting":70,"color":60,"sharpness":90,"subject":85,"emotion":75,"story":65,"publish_value":88},
 "review":"好照片",
 "lr_advice":{"style":"胶片","exposure":0.3,"highlights":-20,"shadows":15,"temperature":5,"hsl":"暖色","explanation":"平衡"},
 "category":"风景",
 "publish":{"best_platform":"小红书","title":"t","description":"d","tags":["a","b"]},
 "portrait":null
}
```"""


def test_parse_full():
    d = parse_analysis(RAW_FENCED)
    assert d["scores"]["composition"] == 80
    assert d["category"] == "风景"
    assert d["publish"]["tags"] == ["a", "b"]
    assert d["portrait"] is None


def test_parse_missing_fields_get_defaults():
    d = parse_analysis('{"scores":{"composition":50}}')
    for k in ["lighting", "color", "sharpness", "subject", "emotion", "story", "publish_value"]:
        assert k in d["scores"]
    assert d["category"] == "其他"
    assert "review" in d
    assert d["lr_advice"]["style"] == ""


def test_parse_invalid_json_safe():
    d = parse_analysis("not json at all")
    assert d["scores"]["composition"] == 0
    assert d["category"] == "其他"


def test_format_publish():
    s = format_publish({"best_platform": "小红书", "title": "t", "description": "d", "tags": ["x"]})
    assert "小红书" in s and "x" in s
