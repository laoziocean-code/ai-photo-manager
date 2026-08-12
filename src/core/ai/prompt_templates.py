"""AI 提示词模板：评分 / 点评 / 修图 / 分类 / 发布 / 人像。

设计要点：
- 一次调用输出全部字段，显著节省 API 成本（多维度合并请求）。
- 强制 JSON 输出，降低解析难度；字段缺省由 response_parser 容错补全。
"""

_SCORE_DIMS = [
    ("composition", "构图"),
    ("lighting", "光影"),
    ("color", "色彩"),
    ("sharpness", "清晰度"),
    ("subject", "主体突出度"),
    ("emotion", "情绪感染力"),
    ("story", "故事感"),
    ("publish_value", "发布价值"),
]

_CATEGORIES = "人像|风景|建筑|星空|美食|旅行|其他"

_PROMPT = """你是一位资深专业摄影师与图片编辑。请分析这张照片，并以严格的 JSON 给出评判。

要求：
1. 只输出一个 JSON 对象，不要包含任何额外说明或 Markdown 代码块标记。
2. scores 中每个维度为 0-100 的整数，8 个维度必填。
3. lr_advice、publish 为对象；portrait 仅当 category 为「人像」时填写对象，否则填 null。

JSON 结构如下：
{
  "scores": {
    "composition": 0,   // 构图
    "lighting": 0,      // 光影
    "color": 0,         // 色彩
    "sharpness": 0,     // 清晰度
    "subject": 0,       // 主体突出度
    "emotion": 0,       // 情绪感染力
    "story": 0,         // 故事感
    "publish_value": 0  // 发布价值
  },
  "review": "摄影师点评（中文，2-3 句，指出亮点与可改进点）",
  "lr_advice": {
    "style": "推荐修图风格（中文短语，如『胶片清新』『暗调电影感』）",
    "exposure": 0,      // 曝光补偿，范围 -2~2，可小数，正为加亮
    "highlights": 0,    // 高光，整数 -100~100
    "shadows": 0,       // 阴影，整数 -100~100
    "temperature": 0,   // 色温，整数 -100~100，正为偏暖
    "hsl": "简要 HSL/色调分离建议（中文）",
    "explanation": "为什么这样调整（中文）"
  },
  "category": "人像|风景|建筑|星空|美食|旅行|其他",
  "publish": {
    "best_platform": "朋友圈|小红书|作品集",
    "title": "推荐标题",
    "description": "推荐简介（中文，1-2 句）",
    "tags": ["标签1", "标签2"]
  },
  "portrait": null  // 或 { "expression":"...", "eyes":"...", "pose":"...", "background":"...", "skin":"..." }
}

维度定义：
- composition 构图：三分法/引导线/留白/平衡。
- lighting 光影：光质、方向、反差、层次。
- color 色彩：色温统一、配色和谐、饱和度。
- sharpness 清晰度：对焦准确、细节保留、噪点控制。
- subject 主体突出度：主体是否明确、干扰是否少。
- emotion 情绪感染力：能否引发观者共鸣。
- story 故事感：画面是否传达叙事或氛围。
- publish_value 发布价值：综合传播/收藏价值。

请严格按上述结构输出。"""


def scoring_prompt() -> str:
    return _PROMPT


def score_dimension_names():
    return _SCORE_DIMS


def categories() -> str:
    return _CATEGORIES
