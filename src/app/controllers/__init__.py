"""控制器层：协调预处理 → AI → 精选 → 报告，与 GUI 解耦。

通过 on_progress / on_done 回调向界面汇报，不直接依赖 PySide6。
"""
