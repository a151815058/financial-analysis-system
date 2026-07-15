// 排程執行狀況管理後台（REQ_013）— 無外部相依，重用 dashboard.css 樣式。

const state = { apiKey: localStorage.getItem("fas_api_key") || "" };

const $ = (sel) => document.querySelector(sel);

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const res = await fetch(url, { headers: { "X-API-Key": state.apiKey } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(new URL(path, window.location.origin), {
    method: "POST",
    headers: { "X-API-Key": state.apiKey, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function setStatus(ok) {
  const dot = $("#status-dot");
  dot.classList.remove("ok", "err");
  dot.classList.add(ok ? "ok" : "err");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

const TASK_LABELS = {
  mops_ingest: "台股財報擷取（MOPS）",
  sec_edgar_ingest: "美股財報擷取（SEC EDGAR）",
  price_ingest: "股價擷取",
  weekly_predict: "每週預測（尚未串接，佔位）",
  model_retrain: "模型重訓（尚未串接，佔位）",
  weekly_backtest: "預測回測（尚未串接，佔位）",
};

function fmt(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString("zh-TW", { hour12: false });
}

function statusBadge(job) {
  if (!job.last_run) return `<span class="pill flat"><span class="dot"></span>尚未執行過</span>`;
  const ok = job.last_run.status === "success";
  return `<span class="pill ${ok ? "up" : "down"}"><span class="dot"></span>${ok ? "成功" : "失敗"}</span>`;
}

function renderMessage(msg) {
  $("#main-content").innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
}

function renderJobs(jobs) {
  const rows = jobs
    .map((job) => {
      const lastRun = job.last_run;
      const detail = lastRun && lastRun.detail ? escapeHtml(lastRun.detail) : "—";
      return `
        <tr>
          <td>${escapeHtml(TASK_LABELS[job.id] || job.id)}</td>
          <td>${statusBadge(job)}</td>
          <td>${lastRun ? (lastRun.trigger_mode === "manual" ? "手動" : "排程") : "—"}</td>
          <td>${lastRun ? fmt(lastRun.finished_at) : "—"}</td>
          <td>${fmt(job.next_run_time)}</td>
          <td class="detail-cell">${detail}</td>
          <td><button class="primary trigger-btn" data-task="${escapeHtml(job.id)}">立即執行</button></td>
        </tr>`;
    })
    .join("");

  $("#main-content").innerHTML = `
    <div class="card">
      <div class="card-header"><h2>排程任務</h2></div>
      <div class="table-scroll">
        <table class="table-left">
          <thead>
            <tr>
              <th>任務</th><th>最新結果</th><th>觸發方式</th><th>最後執行時間</th>
              <th>下次排定時間</th><th>錯誤訊息</th><th></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;

  $("#main-content")
    .querySelectorAll(".trigger-btn")
    .forEach((btn) => btn.addEventListener("click", () => triggerJob(btn.dataset.task, btn)));
}

async function loadJobs() {
  if (!state.apiKey) {
    setStatus(false);
    renderMessage("請先於右上角輸入具 admin 權限的 API Key。");
    return;
  }
  try {
    const jobs = await apiGet("/api/v1/admin/jobs");
    setStatus(true);
    renderJobs(jobs);
  } catch (e) {
    setStatus(false);
    if (e.status === 401) {
      renderMessage("API Key 無效或已撤銷，請重新確認後再試一次。");
    } else if (e.status === 403) {
      renderMessage("此頁面需要 admin 權限的 API Key，read scope 無法查看排程狀態。");
    } else {
      renderMessage(`無法載入排程狀態：${e.message}`);
    }
  }
}

async function triggerJob(task, btn) {
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "觸發中…";
  try {
    await apiPost("/api/v1/admin/ingest/trigger", { task });
    setTimeout(loadJobs, 1500);
  } catch (e) {
    if (e.status === 403) {
      alert("觸發失敗：需要 admin 權限的 API Key。");
    } else {
      alert(`觸發失敗：${e.message}`);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

$("#api-key-input").value = state.apiKey;
$("#save-key-btn").addEventListener("click", () => {
  state.apiKey = $("#api-key-input").value.trim();
  localStorage.setItem("fas_api_key", state.apiKey);
  loadJobs();
});
$("#refresh-btn").addEventListener("click", loadJobs);

if (state.apiKey) loadJobs();
