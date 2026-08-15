"""AI摄影管家 · 手机版后端（Flask）。

复用桌面版全部核心逻辑（src/core + AnalysisController），通过 HTTP API 对外
提供服务，手机浏览器访问即可使用。功能与桌面版同等：
    本地预处理（去重/模糊/曝光）→ AI 视觉评分（8 维）→ Top 精选 → 摄影报告。

启动：
    python mobile/run_mobile.py
然后在手机浏览器访问 http://<电脑IP>:8778

架构：
- 配置存储：JSON 文件 + cryptography 加密 API Key（与桌面版 crypto 一致）。
- 上传会话：每个上传批次存到独立临时目录，分析完可清理。
- 分析任务：后台线程跑 AnalysisController，内存维护任务状态，前端轮询进度。
"""
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

# 把项目根加入 sys.path，使 src.* 可导入
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask, jsonify, request, render_template, send_file, abort

from src.app.controllers.analysis_controller import (
    AnalysisController, _card, _rejected_card,
)
from src.config.models_config import MODEL_PRESETS
from src.core.scoring.scorer import grade
from src.utils.crypto import decrypt_string, encrypt_string
from src.utils.file_utils import list_images
from src.utils.logger import get_logger

logger = get_logger("mobile")

_HERE = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(_HERE / "templates"),
    static_folder=str(_HERE / "static"),
)

# --------------------------------------------------------------------------- #
# 配置存储（JSON + crypto 加密 API Key）
# --------------------------------------------------------------------------- #
_CONFIG_DIR = Path.home() / ".ai_photo_manager" / "mobile"
_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_UPLOAD_ROOT = _CONFIG_DIR / "uploads"
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
_OUTPUT_ROOT = _CONFIG_DIR / "outputs"
_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(cfg: dict):
    _CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _get_api_key() -> str:
    cfg = _load_config()
    enc = cfg.get("api_key_enc", "")
    if not enc:
        return ""
    try:
        return decrypt_string(enc)
    except Exception:
        return ""


def _set_api_key(key: str):
    cfg = _load_config()
    if key:
        cfg["api_key_enc"] = encrypt_string(key)
    else:
        cfg.pop("api_key_enc", None)
    _save_config(cfg)


# --------------------------------------------------------------------------- #
# 任务管理
# --------------------------------------------------------------------------- #
TASKS: dict = {}  # task_id -> 状态 dict
_LOCK = threading.Lock()


def _new_session_dir() -> Path:
    d = _UPLOAD_ROOT / uuid.uuid4().hex[:12]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _serialize_tier(recs, with_thumb=True) -> list:
    out = []
    for r in recs:
        c = _card(r)
        if not with_thumb:
            c["thumb"] = ""
        out.append(c)
    return out


def _run_task(task_id, image_paths, model_id, api_key, output_dir,
              top_n, options, model_override):
    ctrl = AnalysisController()
    with _LOCK:
        t = TASKS.get(task_id)
        if t:
            t["ctrl"] = ctrl

    def on_progress(stage, cur, total, msg):
        with _LOCK:
            t = TASKS.get(task_id)
            if t:
                t["stage"] = stage
                t["current"] = cur
                t["total"] = total
                t["message"] = msg

    def on_done(summary):
        with _LOCK:
            t = TASKS.get(task_id)
            if t:
                t["done"] = True
                t["summary"] = summary
                t["finished_at"] = time.time()

    try:
        ctrl.run(
            image_paths, model_id, api_key, output_dir, top_n, options,
            model_override=model_override,
            on_progress=on_progress, on_done=on_done,
        )
    except Exception as e:
        logger.error(f"任务 {task_id} 失败: {e}")
        with _LOCK:
            t = TASKS.get(task_id)
            if t:
                t["error"] = str(e)
                t["done"] = True


# --------------------------------------------------------------------------- #
# 路由：页面
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------- #
# 路由：API
# --------------------------------------------------------------------------- #
@app.route("/api/presets")
def api_presets():
    return jsonify(MODEL_PRESETS)


@app.route("/api/config")
def api_get_config():
    cfg = _load_config()
    key = _get_api_key()
    return jsonify({
        "model_id": cfg.get("model_id", "glm-vision"),
        "model_override": cfg.get("model_override", ""),
        "base_url": cfg.get("base_url", ""),
        "dedup_level": cfg.get("dedup_level", "标准"),
        "top_n": cfg.get("top_n", 10),
        "has_api_key": bool(key),
        "api_key_masked": (key[:4] + "****" + key[-4:]) if key else "",
    })


@app.route("/api/config", methods=["POST"])
def api_set_config():
    data = request.get_json(force=True)
    cfg = _load_config()
    for k in ("model_id", "model_override", "base_url", "dedup_level", "top_n"):
        if k in data:
            cfg[k] = data[k]
    _save_config(cfg)
    if data.get("api_key"):
        _set_api_key(data["api_key"])
    return jsonify({"ok": True})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "files" not in request.files:
        return jsonify({"error": "未收到文件"}), 400
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "未选择文件"}), 400
    session_dir = _new_session_dir()
    saved = 0
    for f in files:
        name = f.filename or ""
        if not name:
            continue
        safe = os.path.basename(name)
        # 避免重名覆盖
        dest = session_dir / safe
        i = 1
        while dest.exists():
            dest = session_dir / f"{Path(safe).stem}_{i}{Path(safe).suffix}"
            i += 1
        f.save(str(dest))
        saved += 1
    return jsonify({"session_id": session_dir.name, "count": saved})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(force=True)
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "缺少 session_id"}), 400
    session_dir = _UPLOAD_ROOT / session_id
    if not session_dir.exists():
        return jsonify({"error": "会话不存在，请重新上传"}), 404
    paths = list_images(str(session_dir))
    if not paths:
        return jsonify({"error": "上传的文件没有受支持的图片格式（jpg/png/RAW 等）"}), 400

    cfg = _load_config()
    model_id = data.get("model_id") or cfg.get("model_id", "glm-vision")
    model_override = data.get("model_override", "") or cfg.get("model_override", "")
    api_key = data.get("api_key") or _get_api_key()
    if not api_key:
        return jsonify({"error": "请先配置 API Key"}), 400
    top_n = int(data.get("top_n") or cfg.get("top_n", 10))
    top_n = max(3, min(50, top_n))
    dedup_level = data.get("dedup_level") or cfg.get("dedup_level", "标准")
    options = {"dedup_level": dedup_level}

    task_id = uuid.uuid4().hex[:12]
    output_dir = _OUTPUT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        TASKS[task_id] = {
            "session_id": session_id,
            "output_dir": str(output_dir),
            "stage": "preprocess",
            "current": 0,
            "total": len(paths),
            "message": "准备中…",
            "done": False,
            "error": "",
            "summary": None,
            "started_at": time.time(),
            "ctrl": None,
        }
    th = threading.Thread(
        target=_run_task,
        args=(task_id, paths, model_id, api_key, str(output_dir),
              top_n, options, model_override),
        daemon=True,
    )
    th.start()
    return jsonify({"task_id": task_id, "total": len(paths)})


@app.route("/api/status/<task_id>")
def api_status(task_id):
    with _LOCK:
        t = TASKS.get(task_id)
        if not t:
            return jsonify({"error": "任务不存在"}), 404
        return jsonify({
            "stage": t["stage"],
            "current": t["current"],
            "total": t["total"],
            "message": t["message"],
            "done": t["done"],
            "error": t["error"],
        })


@app.route("/api/result/<task_id>")
def api_result(task_id):
    with _LOCK:
        t = TASKS.get(task_id)
        if not t:
            return jsonify({"error": "任务不存在"}), 404
        if not t["done"]:
            return jsonify({"error": "任务未完成"}), 400
        if t["error"]:
            return jsonify({"error": t["error"]}), 500
        s = t["summary"]
        if s is None:
            return jsonify({"error": "无结果"}), 500
        tier1 = _serialize_tier(s["tier1"], with_thumb=True)
        tier2 = [
            {
                "name": r.name,
                "score": round(r.total_score, 1),
                "grade": grade(r.total_score),
                "category": r.ai.get("category", ""),
            }
            for r in s["tier2"]
        ]
        tier3 = [
            {
                "name": r.name,
                "score": round(r.total_score, 1),
                "grade": grade(r.total_score),
            }
            for r in s["tier3"]
        ]
        rejected = [_rejected_card(r) for r in s["rejected"]]
        return jsonify({
            "total": len(s["results"]),
            "picked": len(s["tier1"]),
            "tier2_count": len(s["tier2"]),
            "tier3_count": len(s["tier3"]),
            "rejected_count": len(s["rejected"]),
            "dedup_count": s.get("dedup_count", 0),
            "dedup_level": s.get("dedup_level", ""),
            "output_dir": s.get("output_dir", ""),
            "duration_sec": s.get("duration_sec", 0),
            "duration_text": s.get("duration_text", ""),
            "ai_count": s.get("ai_count", 0),
            "tokens": s.get("tokens") or {"input_tokens": 0, "output_tokens": 0, "total": 0},
            "saved_sec": s.get("saved_sec", 0),
            "saved_time": s.get("saved_time", ""),
            "tier1": tier1,
            "tier2": tier2,
            "tier3": tier3,
            "rejected": rejected,
        })


@app.route("/api/report/<task_id>")
def api_report(task_id):
    with _LOCK:
        t = TASKS.get(task_id)
        if not t:
            abort(404)
        output_dir = t["output_dir"]
    report = os.path.join(output_dir, "摄影报告.html")
    if not os.path.exists(report):
        abort(404)
    return send_file(report, mimetype="text/html")


@app.route("/api/selected/<task_id>")
def api_selected_zip(task_id):
    """以目录列表形式返回精选原图所在目录（便于手机端逐张下载）。"""
    with _LOCK:
        t = TASKS.get(task_id)
        if not t:
            abort(404)
        output_dir = t["output_dir"]
    selected_dir = os.path.join(output_dir, "AI精选")
    if not os.path.isdir(selected_dir):
        return jsonify({"files": []})
    files = []
    for n in sorted(os.listdir(selected_dir)):
        p = os.path.join(selected_dir, n)
        if os.path.isfile(p):
            files.append({"name": n, "size": os.path.getsize(p)})
    return jsonify({"files": files})


@app.route("/api/download/<task_id>/<path:filename>")
def api_download(task_id, filename):
    with _LOCK:
        t = TASKS.get(task_id)
        if not t:
            abort(404)
        output_dir = t["output_dir"]
    # 仅允许从 AI精选/ 目录下载，防路径穿越
    selected_dir = os.path.join(output_dir, "AI精选")
    safe = os.path.basename(filename)
    p = os.path.join(selected_dir, safe)
    if not os.path.isfile(p):
        abort(404)
    return send_file(p, as_attachment=True, download_name=safe)


@app.route("/api/tasks")
def api_tasks():
    """列出最近任务（便于历史回看）。"""
    with _LOCK:
        items = []
        for tid, t in sorted(TASKS.items(), key=lambda kv: kv[1].get("started_at", 0), reverse=True):
            items.append({
                "task_id": tid,
                "done": t["done"],
                "error": t["error"],
                "total": t["total"],
                "current": t["current"],
                "started_at": t.get("started_at"),
            })
    return jsonify({"tasks": items[:20]})


def create_app() -> Flask:
    """供 gunicorn / waitress 调用。"""
    return app
