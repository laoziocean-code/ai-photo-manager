"""pytest 根配置：将项目根加入 sys.path，便于 `import src.*`。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
