/* AI摄影管家 · 手机版前端逻辑 */
const $ = (id) => document.getElementById(id);
let SESSION_ID = null;
let TASK_ID = null;
let POLL_TIMER = null;
let SELECTED_FILES = [];

const GRADE_CLASS = { A: "grade-A", B: "grade-B", C: "grade-C", D: "grade-D" };

// ---------- 视图切换 ----------
function go(step) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $("view-" + step).classList.add("active");
  document.querySelectorAll(".step").forEach((s) => {
    const order = ["config", "upload", "analyze", "result"];
    const cur = order.indexOf(step);
    const si = order.indexOf(s.dataset.step);
    s.classList.toggle("active", s.dataset.step === step);
    s.classList.toggle("done", si < cur);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".step").forEach((s) =>
  s.addEventListener("click", () => go(s.dataset.step))
);
$("goto_upload").onclick = () => go("upload");
$("back_to_config").onclick = () => go("config");
$("goto_analyze").onclick = () => startAnalyze();
$("back_to_upload").onclick = () => go("upload");
$("goto_result").onclick = () => go("result");
$("restart").onclick = () => {
  SESSION_ID = null;
  TASK_ID = null;
  SELECTED_FILES = [];
  $("file_input").value = "";
  $("file_label").textContent = "点击选择照片（可多选）";
  $("btn_upload").disabled = true;
  $("upload_count").textContent = "";
  $("session_info").classList.add("hidden");
  go("upload");
};

// ---------- 配置 ----------
async function loadPresetsAndConfig() {
  try {
    const [presetsRes, cfgRes] = await Promise.all([
      fetch("/api/presets"), fetch("/api/config"),
    ]);
    const presets = await presetsRes.json();
    const sel = $("model_id");
    sel.innerHTML = "";
    presets.forEach((p) => {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.name;
      sel.appendChild(o);
    });
    const cfg = await cfgRes.json();
    sel.value = cfg.model_id || "glm-vision";
    $("model_override").value = cfg.model_override || "";
    $("base_url").value = cfg.base_url || "";
    $("dedup_level").value = cfg.dedup_level || "标准";
    $("top_n").value = cfg.top_n || 10;
    if (cfg.has_api_key) {
      $("key_hint").textContent = "已保存 Key：" + cfg.api_key_masked;
    }
  } catch (e) {
    $("config_msg").textContent = "加载配置失败：" + e;
  }
}

$("toggle_key").onclick = () => {
  const inp = $("api_key");
  inp.type = inp.type === "password" ? "text" : "password";
  $("toggle_key").textContent = inp.type === "password" ? "显示" : "隐藏";
};

$("save_config").onclick = async () => {
  const body = {
    model_id: $("model_id").value,
    model_override: $("model_override").value.trim(),
    base_url: $("base_url").value.trim(),
    dedup_level: $("dedup_level").value,
    top_n: parseInt($("top_n").value, 10) || 10,
  };
  const key = $("api_key").value.trim();
  if (key) body.api_key = key;
  try {
    const r = await fetch("/api/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (j.ok) {
      $("config_msg").textContent = "✓ 已保存";
      $("api_key").value = "";
      loadPresetsAndConfig();
    } else {
      $("config_msg").textContent = "保存失败";
    }
  } catch (e) {
    $("config_msg").textContent = "保存失败：" + e;
  }
};

// ---------- 上传 ----------
$("file_input").addEventListener("change", (e) => {
  SELECTED_FILES = Array.from(e.target.files || []);
  $("file_label").textContent = SELECTED_FILES.length
    ? `已选 ${SELECTED_FILES.length} 张`
    : "点击选择照片（可多选）";
  $("btn_upload").disabled = SELECTED_FILES.length === 0;
  $("upload_count").textContent = "";
});

$("btn_upload").onclick = async () => {
  if (!SELECTED_FILES.length) return;
  $("btn_upload").disabled = true;
  $("upload_msg").textContent = "上传中…";
  const fd = new FormData();
  SELECTED_FILES.forEach((f) => fd.append("files", f));
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const j = await r.json();
    if (j.error) {
      $("upload_msg").textContent = "✗ " + j.error;
      $("btn_upload").disabled = false;
      return;
    }
    SESSION_ID = j.session_id;
    $("uploaded_n").textContent = j.count;
    $("session_id").textContent = j.session_id;
    $("session_info").classList.remove("hidden");
    $("upload_msg").textContent = "✓ 上传完成，可以开始分析";
  } catch (e) {
    $("upload_msg").textContent = "上传失败：" + e;
    $("btn_upload").disabled = false;
  }
};

// ---------- 分析 ----------
async function startAnalyze() {
  if (!SESSION_ID) {
    alert("请先上传照片");
    return;
  }
  go("analyze");
  $("goto_result").classList.add("hidden");
  $("progress_bar").style.width = "0%";
  $("progress_cur").textContent = "0";
  $("progress_msg").textContent = "提交中…";
  $("analyze_stage").textContent = "本地预处理中";

  const body = {
    session_id: SESSION_ID,
    model_id: $("model_id").value,
    model_override: $("model_override").value.trim(),
    top_n: parseInt($("top_n").value, 10) || 10,
    dedup_level: $("dedup_level").value,
  };
  try {
    const r = await fetch("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (j.error) {
      $("progress_msg").textContent = "✗ " + j.error;
      return;
    }
    TASK_ID = j.task_id;
    $("progress_total").textContent = j.total;
    pollStatus();
  } catch (e) {
    $("progress_msg").textContent = "提交失败：" + e;
  }
}

function pollStatus() {
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  POLL_TIMER = setInterval(async () => {
    if (!TASK_ID) return;
    try {
      const r = await fetch("/api/status/" + TASK_ID);
      const s = await r.json();
      if (s.error) { clearInterval(POLL_TIMER); $("progress_msg").textContent = "✗ " + s.error; return; }
      const stageText = {
        preprocess: "本地预处理中", ai: "AI 视觉评分中",
        export: "导出精选与报告中", done: "完成",
      }[s.stage] || s.stage;
      $("analyze_stage").textContent = stageText;
      $("progress_cur").textContent = s.current;
      $("progress_total").textContent = s.total;
      const pct = s.total ? Math.min(100, Math.round((s.current / s.total) * 100)) : 0;
      if (s.stage === "done") {
        $("progress_bar").style.width = "100%";
        $("progress_msg").textContent = "✓ 分析完成";
      } else if (s.stage === "export") {
        $("progress_bar").style.width = "100%";
        $("progress_msg").textContent = s.message;
      } else {
        $("progress_bar").style.width = pct + "%";
        $("progress_msg").textContent = s.message;
      }
      if (s.done) {
        clearInterval(POLL_TIMER);
        if (s.error) {
          $("progress_msg").textContent = "✗ " + s.error;
        } else {
          $("goto_result").classList.remove("hidden");
          loadResult();
          go("result");
        }
      }
    } catch (e) { /* 网络抖动，继续轮询 */ }
  }, 1500);
}

// ---------- 结果 ----------
function gradeClass(score) {
  if (score >= 90) return "grade-A";
  if (score >= 80) return "grade-A";
  if (score >= 70) return "grade-B";
  if (score >= 60) return "grade-C";
  return "grade-D";
}

function exifTags(exif) {
  if (!exif) return "";
  return Object.entries(exif).map(([k, v]) => `<span class="tag">${k}: ${v}</span>`).join("");
}

function photoCardHTML(c) {
  const cls = gradeClass(c.score);
  const retouch = c.retouch ? `<div class="block"><h4>🎨 修图建议</h4><p>${escapeHtml(c.retouch)}</p></div>` : "";
  const publish = c.publish ? `<div class="block"><h4>📤 发布建议</h4><p>${escapeHtml(c.publish)}</p></div>` : "";
  const review = c.review ? `<div class="block"><h4>💬 摄影师点评</h4><p>${escapeHtml(c.review)}</p></div>` : "";
  const cat = c.category ? `<span class="tag">${escapeHtml(c.category)}</span>` : "";
  const exif = exifTags(c.exif);
  return `<div class="photo-card">
    ${c.thumb ? `<img src="${c.thumb}" alt="${escapeHtml(c.name)}" loading="lazy" />` : ""}
    <div class="body">
      <div class="score-row">
        <div class="score-circle ${cls}">${c.score}</div>
        <div><div class="photo-name">${escapeHtml(c.name)}</div>${cat}${exif}</div>
      </div>
      ${review}${retouch}${publish}
    </div>
  </div>`;
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}

function fmtDuration(sec) {
  sec = Math.round(Number(sec) || 0);
  if (sec < 60) return sec + " 秒";
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m < 60) return m + " 分 " + s + " 秒";
  const h = Math.floor(m / 60);
  return h + " 时 " + (m % 60) + " 分";
}

async function loadResult() {
  if (!TASK_ID) return;
  try {
    const r = await fetch("/api/result/" + TASK_ID);
    const j = await r.json();
    if (j.error) { alert(j.error); return; }
    const tk = j.tokens || {};
    const statLine = [
      j.duration_text ? "耗时 " + j.duration_text : "",
      tk.total ? "Token " + tk.total : "",
      j.saved_time ? "节省人工 " + j.saved_time : "",
    ].filter(Boolean).join(" · ");
    $("result_summary").classList.remove("hidden");
    $("result_summary").innerHTML = `
      <div class="summary-grid">
        <div class="cell"><div class="v">${j.total}</div><div class="k">候选总数</div></div>
        <div class="cell"><div class="v">${j.picked}</div><div class="k">精选</div></div>
        <div class="cell"><div class="v">${j.tier2_count}</div><div class="k">良好</div></div>
        <div class="cell"><div class="v">${j.rejected_count}</div><div class="k">废片/去重</div></div>
      </div>
      ${statLine ? `<div class="hint" style="margin-top:10px">${statLine}</div>` : ""}
      <div class="hint" style="margin-top:6px">去重档位：${j.dedup_level} · 去重 ${j.dedup_count} 张</div>`;

    $("t1_count").textContent = j.tier1.length;
    $("tier1_list").innerHTML = j.tier1.map(photoCardHTML).join("");

    const show2 = j.tier2.length > 0;
    $("t2_count").textContent = j.tier2.length;
    document.querySelector('h3.section-title:nth-of-type(2)').classList.toggle("hidden", !show2);
    $("tier2_list").classList.toggle("hidden", !show2);
    $("tier2_list").innerHTML = j.tier2.map((p) =>
      `<div class="mini-list-item"><span class="name">${escapeHtml(p.name)}</span><span class="score">${p.score} ${p.grade}</span></div>`
    ).join("");

    const show3 = j.tier3.length > 0;
    $("t3_count").textContent = j.tier3.length;
    document.querySelector('h3.section-title:nth-of-type(3)').classList.toggle("hidden", !show3);
    $("tier3_list").classList.toggle("hidden", !show3);
    $("tier3_list").innerHTML = j.tier3.map((p) =>
      `<div class="mini-list-item"><span class="name">${escapeHtml(p.name)}</span><span class="score">${p.score}</span></div>`
    ).join("");

    const showR = j.rejected.length > 0;
    $("rj_count").textContent = j.rejected.length;
    document.querySelector('h3.section-title:nth-of-type(4)').classList.toggle("hidden", !showR);
    $("rejected_list").classList.toggle("hidden", !showR);
    $("rejected_list").innerHTML = j.rejected.map((p) =>
      `<div class="mini-list-item reject-item"><span class="name">${escapeHtml(p.name)}${p.is_dup ? "（重复于 " + escapeHtml(p.dup_of) + "）" : ""}<br><span class="reason">${escapeHtml(p.reason)}</span></span></div>`
    ).join("");
  } catch (e) {
    alert("加载结果失败：" + e);
  }
}

$("btn_report").onclick = () => {
  if (TASK_ID) window.open("/api/report/" + TASK_ID, "_blank");
};

$("btn_selected").onclick = async () => {
  if (!TASK_ID) return;
  try {
    const r = await fetch("/api/selected/" + TASK_ID);
    const j = await r.json();
    if (!j.files || !j.files.length) { alert("暂无精选原图"); return; }
    // 逐张打开下载（移动端逐个触发）
    for (const f of j.files) {
      const a = document.createElement("a");
      a.href = "/api/download/" + TASK_ID + "/" + encodeURIComponent(f.name);
      a.download = f.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
  } catch (e) { alert("下载失败：" + e); }
};

// ---------- 初始化 ----------
loadPresetsAndConfig();
