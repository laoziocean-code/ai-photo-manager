"""模型连通性 ping：用轻量 GET /models 探测 API 可达性与延迟。

- 任何 HTTP 响应（含 401/404/403 等）都视为「服务器可达」；
- 只有连接级失败（超时 / DNS / 拒绝连接）才判「未连接」。
- 返回 (ok: bool, ms: int, detail: str)。纯标准库实现，无额外依赖。
"""
import time
import urllib.error
import urllib.request

from src.config.models_config import get_preset


def ping_model(model_id: str, api_key: str, base_url_override: str = "",
               model_override: str = ""):
    """探测模型端点。model_override 仅用于错误提示，不影响 URL 构造。"""
    if not api_key:
        return False, 0, "未配置 API Key"

    preset = get_preset(model_id)
    provider = preset.get("provider", "openai")
    base_url = (base_url_override or preset.get("base_url", "")).strip().rstrip("/")
    if not base_url:
        return False, 0, "未配置 API 端点"

    url = f"{base_url}/models"
    headers = {"User-Agent": "AI摄影管家/1.0"}
    if provider == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp.read()
        return True, round((time.time() - t0) * 1000), ""
    except urllib.error.HTTPError as e:
        # 服务器已响应 → 网络与端点可达
        return True, round((time.time() - t0) * 1000), f"HTTP {e.code}"
    except Exception as e:
        return False, 0, str(e)
