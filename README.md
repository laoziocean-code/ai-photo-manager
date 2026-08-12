<div align="center">

# 📸 AI 摄影管家 (AI Photo Manager)

*帮你在成千上万张照片里，自动挑出真正的好照片，并给出专业摄影点评、评分与后期建议。*

![logo](src/assets/logo.png)

**本地预处理 · AI 视觉评分 · 智能精选 · 摄影报告**

[English](#english) · 简体中文

</div>

---

> 📖 **完整使用指南请见 [使用说明.md](使用说明.md)** —— 覆盖安装、API Key 配置、使用步骤、FAQ 等。

## ✨ 功能特性

- **本地预处理（零 API 成本）**：Hash 去重、感知哈希相似检测、模糊/过曝/欠曝/低分辨率过滤，全部在本地完成。
- **AI 视觉评分**：8 维度打分（构图 / 光影 / 色彩 / 清晰度 / 主体 / 情绪 / 故事 / 发布价值）+ 拟人化摄影师点评。
- **Top 精选导出**：自动生成 `AI精选/` 目录，附带每幅照片的推荐理由。
- **Lightroom 后期建议**：给出可调参数 + 风格方向 + 解释说明。
- **附加能力**：AI 分类、发布平台建议、人像专项分析。
- **HTML 杂志风报告**：一键生成可分享的精美摄影分析报告。
- **RAW / NEF 支持**：通过 rawpy 直接读取相机原始格式并提取预览。
- **多模型适配**：内置智谱 GLM-V4、OpenAI GPT、Google Gemini、Anthropic Claude 等视觉模型，也支持任意 OpenAI 兼容端点。

## 🖼️ 支持的视觉模型

| 预设 | Provider | 默认模型 |
| --- | --- | --- |
| GLM-V4（智谱视觉） | OpenAI 兼容 | `glm-4v-plus` |
| GPT Vision（OpenAI） | OpenAI | `gpt-4o` |
| Gemini Vision | OpenAI 兼容 | `gemini-2.0-flash` |
| Claude Vision（Anthropic） | Anthropic | `claude-3-5-sonnet-latest` |
| 自定义兼容模型 | OpenAI 兼容 | 你自行填写 `base_url` 与模型名 |

> 默认使用智谱 GLM-V4（`glm-4v-plus`）。你也可以在首页「模型名（可覆盖）」中直接填写其他模型 id。

## 📦 安装与运行（从源码）

> 需要 **Python 3.13+** 与 **Windows**（GUI 基于 PySide6，打包 EXE 面向 Windows）。

```bash
# 1. 克隆仓库
git clone https://github.com/<你的用户名>/ai-photo-manager.git
cd ai-photo-manager

# 2. 创建虚拟环境并安装依赖
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. 启动
python -m src.main
```

## 🔑 配置 API Key

1. 在首页（或「设置」）选择视觉模型预设。
2. 填入对应服务商的 API Key。Key 仅通过本地加密（cryptography）写入系统 `QSettings`，**不会上传任何服务器**。
3. 你只需承担所选大模型服务商的 API 调用费用。

## 📁 使用流程

1. **选择文件夹**：拖入或选择你的照片目录（支持 JPG/PNG/RAW/NEF 等）。
2. **设置参数**：精选数量（3–50，可直接输入或用上下箭头）、去重档位（标准/严格等）。
3. **开始分析**：本地先做预处理，再调用视觉模型评分。
4. **查看结果**：
   - 首页看进度与 ETA；
   - 「分析报告」页查看精选照片、评分雷达与摄影师点评；
   - 一键导出 `AI精选/` 目录与 HTML 报告。
5. **完成后**：可选「完成提醒」与「分析结束自动关机」。

## 🏗️ 打包为 Windows 单文件 EXE

```bash
pip install pyinstaller
python build.py
```

产物位于 `dist/AI摄影管家.exe`（单文件，因内置 cv2 / PySide6，体积约 150–500 MB）。
图标与版本信息由 `build_exe.spec` 与 `version_info.txt` 控制。

## 🧪 运行测试

```bash
pip install pytest
pytest
```

## 📂 项目结构

```
ai-photo-manager/
├── src/
│   ├── main.py                 # 应用入口（图标/样式加载）
│   ├── app/                    # UI 层（窗口/页面/控件/后台任务）
│   │   ├── main_window.py
│   │   ├── widgets/            # 首页 / 分析 / 报告 / 设置
│   │   ├── workers/            # 分析、连通性检测线程
│   │   └── styles/             # 主题 QSS
│   ├── config/                 # 模型预设、设置管理
│   ├── core/                   # 业务逻辑
│   │   ├── ai/                 # 视觉模型适配器（OpenAI / Anthropic）
│   │   ├── preprocessing/      # 去重 / 模糊 / 曝光 / 质量过滤
│   │   ├── scoring/            # 评分
│   │   ├── selection/          # Top 精选
│   │   ├── report/             # HTML 报告
│   │   └── retouch/            # Lightroom 建议
│   └── utils/                  # 加密 / 文件 / 日志
├── tests/                      # pytest 测试
├── build.py / build_exe.spec   # PyInstaller 打包
├── requirements.txt
└── version_info.txt            # Windows 版本信息
```

## 🛠️ 技术栈

- **GUI**：PySide6（Qt 6，LGPL，可免费闭源商用）
- **图像处理**：OpenCV、Pillow、imagehash、rawpy、NumPy
- **AI 调用**：OpenAI Python SDK、Anthropic SDK（统一 OpenAI 兼容抽象）
- **报告**：Jinja2 模板
- **加密**：cryptography（API Key 本地加密）
- **打包**：PyInstaller

## 📄 许可证

本项目以 [MIT License](LICENSE) 开源。

## ⚠️ 免责声明

- 本项目仅为摄影辅助工具，AI 评分与建议仅供参考，不构成专业摄影或法律意见。
- API Key 由用户自行申请并承担费用；请妥善保管，不要提交到公开仓库。
- 作者不对因使用本软件造成的任何数据丢失或损失负责；处理重要照片前请备份。

---

## English

**AI Photo Manager** is a desktop app that helps you automatically pick the best photos from a large library, and provides professional photography critique, scoring, and post-processing advice.

- **Local preprocessing** (hash dedup, perceptual-hash similarity, blur/over/under-exposure/low-resolution filtering) — zero API cost.
- **AI vision scoring** across 8 dimensions + human-like photographer comments.
- **Top-N selection export** with reasons; **Lightroom advice**; **magazine-style HTML report**.
- **RAW/NEF** support via rawpy; **multi-model** (Zhipu GLM-V4, OpenAI GPT, Google Gemini, Anthropic Claude, or any OpenAI-compatible endpoint).
- GUI built with **PySide6**; packaged as a single-file Windows EXE via PyInstaller.

See the Chinese section above for install/run/pack instructions. Licensed under [MIT](LICENSE).
