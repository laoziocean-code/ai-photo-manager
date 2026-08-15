<div align="center">

# 📸 AI 摄影管家 (AI Photo Manager)

*帮你在成千上万张照片里，自动挑出真正的好照片，并给出专业摄影点评、评分与后期建议。*

![logo](src/assets/logo.png)

**本地预处理 · AI 视觉评分 · 智能精选 · 摄影报告 · 多平台（Windows / macOS / 手机）**

[English](#english) · 简体中文

</div>

---

> 📖 **完整使用指南请见 [使用说明.md](使用说明.md)** —— 覆盖各平台安装、API Key 配置、使用步骤、FAQ 等。

## ✨ 功能特性

- **本地预处理（零 API 成本）**：Hash 去重、感知哈希相似检测、模糊/过曝/欠曝/低分辨率过滤，全部在本地完成。
- **AI 视觉评分**：8 维度打分（构图 / 光影 / 色彩 / 清晰度 / 主体 / 情绪 / 故事 / 发布价值）+ 拟人化摄影师点评。
- **Top 精选导出**：自动生成 `AI精选/` 目录，附带每幅照片的推荐理由。
- **Lightroom 后期建议**：给出可调参数 + 风格方向 + 解释说明。
- **附加能力**：AI 分类、发布平台建议、人像专项分析。
- **HTML 杂志风报告**：一键生成可分享的精美摄影分析报告。
- **全格式 RAW 支持**：通过 rawpy（LibRaw）读取**所有主流相机 RAW**（NEF/CR2/CR3/ARW/DNG/RW2/RAF/ORF/PEF/X3F/IIQ/RWL 等全部厂商格式），并带文件头魔数兜底——扩展名被改也能识别。
- **多平台**：Windows / macOS 桌面客户端（PySide6），以及手机版（手机浏览器访问，后端复用全部核心逻辑）。
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

## 📦 安装与运行

> 桌面版需要 **Python 3.13+**；手机版需要一台电脑作后端 + 手机浏览器。

### Windows（桌面版）

```bash
git clone https://github.com/laoziocean-code/ai-photo-manager.git
cd ai-photo-manager
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

### macOS（桌面版）

```bash
git clone https://github.com/laoziocean-code/ai-photo-manager.git
cd ai-photo-manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt        # rawpy / PySide6 / opencv 均有 macOS 预编译 wheel
python -m src.main
```

> macOS 上首次启动若提示「无法验证开发者」，在「访达」右键 App →「打开」即可。核心代码已跨平台兼容（路径处理自动区分系统）。

### 手机版（Web / 浏览器访问）

手机版以「手机浏览器前端 + 电脑后端」方式运行，后端复用桌面版全部 Python 核心逻辑，功能与桌面版同等。手机与电脑需在同一 Wi-Fi 局域网。

```bash
# 在电脑上（Windows / macOS 均可）
pip install -r requirements.txt        # 已含 flask
python mobile/run_mobile.py
```

启动后会打印访问地址，例如 `http://192.168.1.10:8778`，用手机浏览器打开即可。详见 [使用说明.md](使用说明.md) 第 10 节。

## 🔑 配置 API Key

1. 在桌面版首页（或「设置」）/ 手机版「配置」页选择视觉模型预设。
2. 填入对应服务商的 API Key。Key 仅通过本地加密（cryptography）写入系统配置，**不会上传任何服务器**。
3. 你只需承担所选大模型服务商的 API 调用费用。

## 📁 使用流程

1. **导入照片**：桌面版拖入或选择文件夹；手机版在浏览器选照片上传。支持 JPG/PNG/WEBP/TIFF/BMP 及所有相机 RAW。
2. **设置参数**：精选数量（3–50）、去重档位（标准/严格）。
3. **开始分析**：本地先做预处理，再调用视觉模型评分。
4. **查看结果**：进度与 ETA；精选照片、评分与点评；一键导出 `AI精选/` 目录与 HTML 报告。
5. **完成后**：桌面版可选「完成提醒」与「分析结束自动关机」。

## 🏗️ 打包为单文件应用

### Windows（EXE）

```bash
pip install pyinstaller
python build.py
```

产物 `dist/AI摄影管家.exe`（单文件，约 150–500 MB）。

### macOS（.app）

```bash
pip install pyinstaller
python build_mac.py
```

产物 `dist/AI摄影管家.app`。首次打开需右键 →「打开」。如需分发给他人，建议用 Apple Developer 证书签名并公证。

> 手机版无需打包，运行 `python mobile/run_mobile.py` 即作为 Web 服务对外提供。

## 🧪 运行测试

```bash
pip install pytest
pytest
```

## 📂 项目结构

```
ai-photo-manager/
├── src/
│   ├── main.py                 # 桌面应用入口
│   ├── app/                    # UI 层（窗口/页面/控件/后台任务）
│   ├── config/                 # 模型预设、设置管理
│   ├── core/                   # 业务逻辑（跨平台，桌面/手机共用）
│   │   ├── ai/                 # 视觉模型适配器
│   │   ├── preprocessing/      # 去重 / 模糊 / 曝光 / 质量过滤
│   │   ├── scoring/            # 评分
│   │   ├── selection/          # Top 精选
│   │   ├── report/             # HTML 报告
│   │   └── retouch/            # Lightroom 建议
│   └── utils/                  # 加密 / 文件 / 日志（含 RAW 全格式 + 内容兜底）
├── mobile/                     # 手机版（Flask 后端 + 移动端前端）
│   ├── backend.py              # 复用 src/core 的 Web API
│   ├── run_mobile.py           # 启动入口
│   ├── templates/index.html    # 移动端单页应用
│   └── static/                 # 样式与前端逻辑
├── tests/                      # pytest 测试
├── build.py / build_exe.spec   # Windows PyInstaller 打包
├── build_mac.py / build_mac.spec  # macOS PyInstaller 打包
├── requirements.txt
└── version_info.txt            # Windows 版本信息
```

## 🛠️ 技术栈

- **桌面 GUI**：PySide6（Qt 6，LGPL，跨平台，可免费闭源商用）
- **手机版**：Flask（后端复用桌面版核心）+ 原生 HTML/JS（移动端单页应用）
- **图像处理**：OpenCV、Pillow、imagehash、rawpy（LibRaw，全格式 RAW）、NumPy
- **AI 调用**：OpenAI Python SDK、Anthropic SDK（统一 OpenAI 兼容抽象）
- **报告**：Jinja2 模板
- **加密**：cryptography（API Key 本地加密）
- **打包**：PyInstaller（Windows EXE / macOS .app）

## 📄 许可证

本项目以 [MIT License](LICENSE) 开源。

## ⚠️ 免责声明

- 本项目仅为摄影辅助工具，AI 评分与建议仅供参考，不构成专业摄影或法律意见。
- API Key 由用户自行申请并承担费用；请妥善保管，不要提交到公开仓库。
- 手机版后端运行时，照片会通过局域网上传到电脑端处理；分析时照片内容会发送给你所选的模型服务商。在意隐私的照片请不要放入。
- 作者不对因使用本软件造成的任何数据丢失或损失负责；处理重要照片前请备份。

---

## English

**AI Photo Manager** helps you automatically pick the best photos from a large library, and provides professional photography critique, scoring, and post-processing advice.

- **Multi-platform**: Windows & macOS desktop (PySide6), plus a mobile web app (phone browser + on-computer backend sharing the same Python core).
- **Local preprocessing** (hash dedup, perceptual-hash similarity, blur/over/under-exposure/low-resolution filtering) — zero API cost.
- **AI vision scoring** across 8 dimensions + human-like photographer comments.
- **Top-N selection export** with reasons; **Lightroom advice**; **magazine-style HTML report**.
- **All RAW formats** via rawpy/LibRaw (NEF/CR2/CR3/ARW/DNG/RW2/RAF/ORF/PEF/X3F/IIQ/RWL …) with magic-number fallback for renamed files.
- **Multi-model** (Zhipu GLM-V4, OpenAI GPT, Google Gemini, Anthropic Claude, or any OpenAI-compatible endpoint).

See the Chinese section above for install/run/pack instructions per platform. Licensed under [MIT](LICENSE).
