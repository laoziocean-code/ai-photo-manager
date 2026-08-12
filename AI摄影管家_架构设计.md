# AI摄影管家 — 产品与技术架构设计（第一版 MVP）

> 文档目标：在动手写业务代码前，先把产品架构、技术架构、目录结构、开发计划与关键技术决策对齐。
> 设计原则：**稳定性 > 易维护 > 可打包 > 用户体验**。以真实商业软件标准推进。

---

## 一、产品架构

### 1.1 一句话定位
模拟一位专业摄影师：帮用户从海量照片（如 1000 张）中筛出值得发布的少数精品（如 Top 10），并给出**可执行的修图参数 + 发布方案**。

### 1.2 核心用户旅程
```
[配置 API Key] → [拖入照片文件夹] → [本地预处理筛选] → [AI 视觉评分]
   → [Top 精选 + 修图建议 + 发布建议] → [HTML 摄影报告 + 文件导出]
```

### 1.3 功能模块地图
- **配置中心**：API Key（本地加密）、视觉模型选择、输出目录。
- **导入中心**：文件夹 / 拖拽导入、格式过滤、EXIF 读取。
- **预处理引擎（本地，零 API 成本）**：Hash 去重、相似检测、模糊检测、过曝/欠曝、分辨率过滤。
- **AI 评分引擎**：8 维评分 + 摄影师点评（优点/缺点/建议）。
- **精选引擎**：综合排序 → Top N → 复制导出 `AI精选/`。
- **后期引擎**：Lightroom 参数 + 风格 + 解释。
- **报告引擎**：杂志风 HTML（缩略图 / 评分 / 点评 / 修图建议）。
- **（附加）分类 / 发布建议 / 人像专项**：并入同一次 AI 调用。

### 1.4 数据处理流
```
源照片
  → 索引 + EXIF 提取
  → 本地预处理过滤（产出「候选集」与「废片集」，省 API 成本）
  → AI 评分（仅候选集）
  → 排序精选（Top N）
  → 后期/发布文案生成
  → HTML 报告 + 文件导出
```

> 关键设计：**先本地过滤再调 AI**。1000 张里先淘汰重复/模糊/废片，只剩几百张进 AI，显著省钱提速。

---

## 二、技术架构

### 2.1 技术栈
| 用途 | 选型 |
|---|---|
| 语言 | Python 3.11+（推荐 3.11，包兼容性最佳） |
| GUI | **PyQt6 或 PySide6**（见决策 1） |
| 图像处理 | Pillow、OpenCV（`opencv-python-headless`）、imagehash |
| EXIF | Pillow + exifread（RAW 延后用 pyexiftool） |
| AI 接口 | `openai` SDK（OpenAI 兼容）、`anthropic` SDK（可选） |
| 报告 | Jinja2 模板 |
| 加密 | `cryptography`（Fernet） |
| 并发 | PyQt 信号/槽 + QThread / QThreadPool |
| 配置 | QSettings / JSON |
| 打包 | PyInstaller |

### 2.2 分层架构
```
表现层 (PyQt GUI + QSS 主题)
   ↓
控制层 (Controllers / 信号槽，串联各模块)
   ↓
业务核心层 (core/)
   ├─ preprocessing   本地预处理（无需 API，省成本）
   ├─ ai              视觉模型抽象 + 适配器
   ├─ scoring         8 维评分汇总
   ├─ selection       Top N 精选
   ├─ retouch         Lightroom 建议
   └─ report          HTML 报告
   ↓
基础设施层 (utils/ crypto, logger, file_io；config/ 设置与模型预设)
```

### 2.3 AI 接入设计（核心可扩展性）
统一抽象 `VisionModel` 接口：
```python
class VisionModel(Protocol):
    def analyze(self, image_path: str, prompt: str) -> dict: ...
```
适配器实现：
- `OpenAICompatibleModel`：通用 OpenAI 兼容端点，覆盖 **GPT Vision / Gemini（OpenAI 兼容模式）/ GLM-4.1V / 自建兼容端点**。
- `AnthropicModel`（可选）：Claude 原生（若需）。

通过 `config/models_config.py` 动态注册预设；**新增模型 = 加一个适配器 + 一条预设**，不动主流程。

AI 输出：强制 JSON（`response_format=json_object` 或 function calling，或 prompt 约束 + 容错解析），统一经 `response_parser` 校验与补全，保证字段缺失时不崩。

---

## 三、关键技术决策（需你拍板）

### 决策 1：GUI 框架许可（商用关键）
- **PyQt6**：GPLv3。闭源分发 EXE 需向 Riverbank 购买商业许可，否则违反许可。
- **PySide6**：LGPL，可**免费闭源商用**；API 与 PyQt6 约 95% 一致，切换成本极低。
- **建议**：商用分发选 **PySide6**；若项目开源或已购许可则用 PyQt6。代码层用 Qt 抽象，二者可互换。

### 决策 2：API Key 加密
- 本地加密存储：`cryptography.Fernet`，密钥由「机器指纹（MAC/硬盘序列号）+ 盐」派生；配置存于用户目录（非项目内）。
- 不联网、不上传、不校验；换机器不可直接复用（即安全设计）。
- 备选：Windows 凭据管理器（keyring），便携性略差。

### 决策 3：RAW 支持
- **v1**：jpg / jpeg / png / webp（Pillow/OpenCV 直读，零额外依赖）。
- RAW（cr2/nef/arw…）：需 `rawpy` 提取预览 + `pyexiftool` 读 EXIF，依赖大、EXE 体积显著增加。
- **建议**：v1.1 再做；图像加载器预留 `RawLoader` 接口，不阻塞主线。

### 决策 4：打包形态
- 开发迭代用 `--onedir`（目录式，启动快）；最终分发用 `--onefile` 单 EXE（启动稍慢，便于分享）。
- 备选 Nuitka（更小更快但编译慢）。
- 注意：cv2 + PyQt 会使 EXE 体积约 **300–500 MB**，需在 README 说明。

---

## 四、文件目录结构

```
AI摄影管家/
├── README.md                      # 使用说明 + 打包说明
├── requirements.txt
├── build_exe.spec                 # PyInstaller 配置
├── build.py                       # 构建助手
├── src/
│   ├── main.py                    # 入口
│   ├── app/
│   │   ├── main_window.py         # 主窗口（首页/分析/报告 切换）
│   │   ├── widgets/
│   │   │   ├── home_page.py       # 首页：名称/Key/模型/导入/输出/开始
│   │   │   ├── settings_dialog.py # API Key 配置弹窗
│   │   │   ├── analysis_page.py   # 分析进度与结果列表
│   │   │   ├── report_page.py     # 报告预览/打开
│   │   │   └── thumbnail_card.py  # 照片卡片（缩略图+评分）
│   │   ├── styles/
│   │   │   └── theme.qss          # 摄影质感深色主题
│   │   └── controllers/
│   │       └── analysis_controller.py  # 串联核心模块 + 线程管理
│   ├── config/
│   │   ├── settings.py            # 设置管理（加密 Key、输出目录）
│   │   └── models_config.py       # 视觉模型预设（GPT/Gemini/Claude/GLM/自定义）
│   ├── core/
│   │   ├── image_io.py            # 加载、缩略图、EXIF
│   │   ├── preprocessing/
│   │   │   ├── deduplication.py   # MD5 精确去重 + pHash 相似检测
│   │   │   ├── blur_detect.py     # Laplacian 方差
│   │   │   ├── exposure_detect.py # 直方图过曝/欠曝
│   │   │   └── quality_filter.py  # 编排本地过滤 → 候选集/废片集
│   │   ├── ai/
│   │   │   ├── base_model.py       # VisionModel 抽象
│   │   │   ├── openai_compatible.py
│   │   │   ├── anthropic_model.py  # 可选
│   │   │   ├── prompt_templates.py
│   │   │   └── response_parser.py  # JSON 校验/补全/容错
│   │   ├── scoring/
│   │   │   └── scorer.py          # 8 维 → 加权总分
│   │   ├── selection/
│   │   │   └── top_selector.py    # 排序 + Top N + 复制导出
│   │   ├── retouch/
│   │   │   └── lr_advice.py       # Lightroom 参数解析与解释
│   │   └── report/
│   │       ├── html_report.py
│   │       └── templates/
│   │           └── report_template.html  # 杂志风模板
│   ├── utils/
│   │   ├── crypto.py              # API Key 加密/解密
│   │   ├── logger.py
│   │   └── file_utils.py          # 长路径、中文路径处理
│   └── assets/
│       ├── icons/
│       └── logo.png
├── tests/
│   ├── test_preprocessing.py
│   ├── test_scoring.py
│   └── test_response_parser.py
└── docs/
    └── architecture.md            # 本文件
```

> 配置独立：`config/` 与 `utils/crypto.py` 分离，后续加模型只需动 `models_config.py` + 一个适配器。

---

## 五、开发计划（五步 + 内部里程碑）

- **Step 2 骨架**：脚手架 + 配置/日志/主题基础设施 + 空模块占位，跑通 `python -m src.main`（空窗口），不实现业务逻辑。
- **Step 3.1 配置与加密**：settings + crypto，Key 加密落盘。
- **Step 3.2 导入 + EXIF**：拖拽/选择文件夹、格式过滤、EXIF 提取。
- **Step 3.3 本地预处理**：去重 / 相似 / 模糊 / 曝光 / 分辨率，产出候选集。
- **Step 3.4 AI 评分**：VisionModel 抽象 + 适配器 + 8 维 JSON 解析。
- **Step 3.5 Top N 精选 + 导出**：排序、复制 `AI精选/`。
- **Step 3.6 后期 / 发布 / 分类（+ 人像）**：Lightroom 参数、发布文案、分类。
- **Step 3.7 HTML 报告**：杂志风模板。
- **Step 3.8 GUI 集成**：首页 / 设置 / 分析 / 报告 四页联调。
- **Step 4 测试**：单元测试 + 少量样例照片端到端跑通。
- **Step 5 打包**：PyInstaller → `AI摄影管家.exe` + README。

---

## 六、三大附加功能评估

| 功能 | 评估 | 建议 |
|---|---|---|
| 功能1 AI 照片分类（人像/风景/建筑/星空/美食/旅行） | 一次 AI 调用多字段输出，几乎零额外成本 | **纳入** |
| 功能2 发布建议（朋友圈/小红书/作品集 + 标题/简介/标签） | 小红书/朋友圈场景强相关，价值高 | **纳入** |
| 功能3 人像专项（表情/眼神/姿态/背景/肤色） | 仅人像类触发，省 token；专业溢价高 | **纳入（条件触发）** |

三者均可并入**同一次 AI 请求**的 JSON 输出（增加 `category` / `publish` / `portrait` 字段），控制成本。

---

## 七、风险与注意
- **API 成本与限流**：并发控制 + 失败重试 + 断点续跑（已分析过的照片缓存结果）。
- **中文 / 超长路径**：Windows 统一用 `\\?\` 前缀处理。
- **EXIF 时区混乱**：统一按本地时区展示。
- **大文件夹内存**：缩略图懒加载、流式处理，不在内存堆全部原图。
- **EXE 体积**：cv2 + PyQt 约 300–500 MB，README 明示。

---

## 八、下一步（Step 2 预览）
搭建骨架将产出：**可运行的空窗口 + 完整目录结构 + 配置/日志/主题基础设施**，跑通 `python -m src.main`，但**不实现任何业务逻辑**。待你确认本设计与两项决策后启动。
