"""摄影质感深色主题样式表加载。"""
from pathlib import Path


def load_stylesheet() -> str:
    """读取同级目录下的 theme.qss 作为全局样式。"""
    p = Path(__file__).parent / "theme.qss"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""
