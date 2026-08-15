"""AI摄影管家 · 手机版启动入口。

启动后在手机浏览器访问 http://<电脑IP>:8778 即可使用。
手机与电脑需在同一局域网（Wi-Fi）。

用法：
    python mobile/run_mobile.py [--host 0.0.0.0] [--port 8778]

依赖：先在项目根 pip install -r requirements.txt（已含 flask）。
"""
import argparse
import socket
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description="AI摄影管家 · 手机版后端")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    parser.add_argument("--port", type=int, default=8778, help="端口，默认 8778")
    args = parser.parse_args()

    from mobile.backend import create_app

    app = create_app()
    ip = _local_ip()
    url = f"http://{ip}:{args.port}"
    print("=" * 56)
    print("  📸 AI摄影管家 · 手机版")
    print("=" * 56)
    print(f"  电脑访问：http://127.0.0.1:{args.port}")
    print(f"  手机访问：{url}")
    print("  （手机与电脑需在同一 Wi-Fi 局域网）")
    print("-" * 56)
    print("  按 Ctrl+C 停止服务。")
    print("=" * 56)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
