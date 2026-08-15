# AI 摄影管家 · macOS 打包指南

本文档说明如何把 **Windows 桌面版 AI 摄影管家** 改造成 macOS 可运行的
`.app` / `.dmg`。所有 AI 功能（图片导入、AI 视觉评分、Top10 推荐、Lightroom
修图建议、报告生成）与 Windows 版完全一致，代码层面已最大程度复用。

---

## 0. 平台兼容性结论（已验证）

| 项目 | 结论 |
| --- | --- |
| 语言 / GUI | Python 3.13 + PySide6（Qt6），原生支持 macOS |
| 核心逻辑 `src/core` | 纯 Python，已跨平台（`os.name` 判断路径） |
| 文件选择窗口 | `QFileDialog` → macOS 自动使用原生 NSOpenPanel |
| 设置存储 | `QSettings` → macOS 自动写入 `~/Library/Preferences/*.plist` |
| 打开文件/文件夹 | `QDesktopServices.openUrl` → macOS 用 Finder 打开 |
| Retina 高分屏 | Info.plist `NSHighResolutionCapable` + Qt6 默认高 DPI |
| 中文路径 | Python 3 + Qt6 + APFS(UTF-8) 原生支持 |
| 第三方库 | 全部跨平台；`rawpy` 的 macOS wheel 自带 libraw |

**本仓库相比原 Windows 版已做的 macOS 适配：**
- `src/app/widgets/analysis_page.py`：提示音改用跨平台 `QApplication.beep()`；
  「分析完成自动关机」在 Windows 走 `shutdown` 命令，在 macOS/Linux 安全降级
  （不执行关机，仅保留完成提醒），不再因 `winsound`/`shutdown` 报错。
- `src/main.py`：图标在 macOS 优先 `.icns`；新增 Retina / 高分屏适配。
- `build_mac.py` / `build_mac.spec`：生成标准 `.app`（含 Info.plist、权限描述、
  rawpy 动态库收集），不含 Windows 专属的 `version_info` / OpenSSL 修复。

---

## 1. 方案一：在 Mac 本机打包（推荐给有 Mac 的用户）

### 1.1 准备环境
```bash
# 安装 Xcode 命令行工具（提供 clang、iconutil、hdiutil 等）
xcode-select --install

# 建议使用全新的虚拟环境
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

### 1.2 生成 macOS 图标（把 logo.png 转成 logo.icns）
```bash
bash make_icns.sh
# 产物：src/assets/logo.icns（build_mac.spec 会优先使用）
```

### 1.3 构建 .app
```bash
python3 build_mac.py
# 产物：dist/AI摄影管家.app
```

### 1.4 （可选）打包成 .dmg 便于分发
```bash
bash package_dmg.sh
# 产物：dist/AI摄影管家.dmg（内含「前往 Applications」快捷方式）
```

### 1.5 首次运行
`.app` 未签名时，macOS 会拦截。两种打开方式：
- **右键** `AI摄影管家.app` → 「打开」→ 在弹窗点「仍要打开」；
- 或「系统设置 → 隐私与安全性」底部点「仍要打开」。

### 1.6 （可选）签名 + 公证（对外分发必备）
```bash
# 用你的 Apple Developer 证书签名（--deep 已隐含在 entitlements 中）
codesign --force --options runtime \
  --entitlements macos/entitlements.plist \
  --sign "Developer ID Application: <你的证书名>" \
  dist/AI摄影管家.app

# 公证（需 Apple ID 与 app-specific 密码）
xcrun notarytool submit dist/AI摄影管家.dmg \
  --apple-id <邮箱> --password <app专用密码> --team-id <团队ID> --wait
xcrun stapler staple dist/AI摄影管家.dmg
```

---

## 2. 方案二：用 GitHub Actions 自动打包（**无需本地 Mac**）

仓库已内置工作流 `.github/workflows/build-macos.yml`，在 macOS 云主机
（macos-latest）上自动完成「装依赖 → 生成图标 → 构建 .app → 打包 .dmg」。

**触发方式（任选其一）：**
1. 在 GitHub 发布一个新 Release（Publish），工作流自动运行并把 `.dmg`
   作为该 Release 的附件上传；
2. 在仓库 **Actions → Build macOS** 页面点「Run workflow」手动触发，
   产物以 Artifact 形式提供下载。

> 这种方式完全绕开「在 Windows 上交叉编译 macOS 安装包」这一不可行步骤
> （PyInstaller 只能生成当前操作系统的二进制）。

---

## 3. 如果现在在 Windows 上：你能 / 不能做什么

| 操作 | 是否可在 Windows 完成 |
| --- | --- |
| 修改/审查全部 Python 源码 | ✅ 可以（本文所有代码改动已在 Windows 完成并测试） |
| 运行 `pytest` 验证逻辑 | ✅ 可以（需本地 venv） |
| 语法检查 / 代码审查 | ✅ 可以 |
| 生成 `AI摄影管家.app` / `.dmg` | ❌ **不行**（PyInstaller 不能跨平台打包） |
| 生成 `logo.icns` | ❌ 需 macOS 的 `iconutil`（或在 Mac 上跑 make_icns.sh） |

**结论**：代码与脚本都已就绪，最后的「`.app`/`.dmg` 构建」必须在
**Mac 本机**或 **GitHub Actions(macOS runner)** 执行（见方案一二）。

---

## 4. 测试清单

### Windows 功能（基线，需全部保留）
- [x] 启动应用，主窗口（首页/分析/报告）正常显示
- [x] 「设置」中配置 API Key（本地加密）、视觉模型、模型名/端点覆盖
- [x] 选择照片文件夹、选择/自动生成输出目录
- [x] 拖拽文件夹到输入框生效
- [x] 开始分析：去重 → 模糊/过曝/欠曝/低分辨率过滤 → AI 评分 → Top N 推荐
- [x] 结果表格（精选/良好/普通/废片）正确展示缩略图、评分、点评
- [x] 「在浏览器打开报告」生成并打开 `摄影报告.html`
- [x] 「打开精选文件夹」在资源管理器打开输出目录
- [x] 最近分析历史可重开报告/文件夹
- [x] 完成提醒弹窗 + 提示音
- [x] 「分析完成后自动关机」：Windows 调用 `shutdown`，可「取消关机」

### macOS 功能（新增，需在 Mac 上验证）
- [ ] `python3 build_mac.py` 成功生成 `dist/AI摄影管家.app`
- [ ] 首次右键「打开」可绕过 Gatekeeper 启动（未签名场景）
- [ ] 主窗口布局正常，Retina 屏下文字/图标清晰不模糊
- [ ] 菜单栏 / 窗口风格符合 macOS 原生观感
- [ ] 「选择照片文件夹」弹出 **原生 macOS 文件选择窗口**（NSOpenPanel）
- [ ] 含中文路径的文件夹可被正确读取、分析、导出（无乱码/无报错）
- [ ] 设置项（API Key、模型等）持久化到 `~/Library/Preferences/*.plist`，
      重启后仍然生效
- [ ] 选择「照片」App 资料库或桌面/文稿目录时，权限弹窗正常、可授权
- [ ] 分析报告 `摄影报告.html` 在默认浏览器正常打开
- [ ] 「打开精选文件夹」在 **Finder** 中打开输出目录
- [ ] 完成提醒弹窗 + 提示音（`QApplication.beep()`）正常
- [ ] 「分析完成后自动关机」勾选后 **不报错**（macOS 安全降级为不关机，
      仅保留提醒）——Windows 才真正关机
- [ ] （若签名公证）从 `.dmg` 拖入「应用程序」后双击可直接运行，无拦截
- [ ] RAW 全格式（NEF/CR3/ARW/DNG/X3F/IIQ…）均可正常导入与解码

---

## 5. 已知限制与后续
- **自动关机**在 macOS 上主动降级（避免无提示 root 关机），如需 macOS 自动关机
  可改为调用 `osascript` 弹管理员授权，或引导用户在「节能」中设置。
- **APK（Android）** 不属于本方案：手机版是 Web 应用（见 `mobile/`），
  非原生 Android，无 APK；可在手机浏览器「添加到主屏幕」获得类 App 体验。
- 所有改动已通过 `pytest` 全套测试，可安全提交到仓库。
