// 排程執行狀況管理後台（REQ_013）+ 帳號密碼登入（REQ_014）— 無外部相依，重用 dashboard.css 樣式。

const $ = (sel) => document.querySelector(sel);

async function apiGet(path) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ---------------------------------------------------------------------------
// 登入 / 登出 / 變更密碼（REQ_014）
// ---------------------------------------------------------------------------

const loginWrap = $("#login-wrap");
const userBar = $("#user-bar");
const loginForm = $("#login-form");
const loginMsg = $("#login-msg");
const loginSubmitBtn = $("#login-submit");

function showLoggedOut(message) {
  userBar.hidden = true;
  $("#main-content").innerHTML = "";
  $("#main-content").appendChild(loginWrap);
  loginWrap.hidden = false;
  loginWrap.classList.add("fade-in");
  loginForm.reset();
  loginMsg.innerHTML = message
    ? `<div class="form-msg error">${escapeHtml(message)}</div>`
    : "";
}

function showLoggedIn(username) {
  loginWrap.hidden = true;
  userBar.hidden = false;
  $("#username-label").textContent = `已登入：${username}`;
  loadJobs();
}

async function checkSession() {
  try {
    const me = await apiGet("/api/v1/auth/me");
    showLoggedIn(me.username);
  } catch (e) {
    showLoggedOut();
  }
}

loginForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  loginMsg.innerHTML = "";
  loginSubmitBtn.disabled = true;
  loginSubmitBtn.textContent = "登入中…";
  try {
    const me = await apiPost("/api/v1/auth/login", {
      username: $("#login-username").value.trim(),
      password: $("#login-password").value,
    });
    loginWrap.hidden = true;
    userBar.hidden = false;
    userBar.classList.add("fade-in");
    $("#username-label").textContent = `已登入：${me.username}`;
    loadJobs();
  } catch (e) {
    loginMsg.innerHTML = `<div class="form-msg error">${escapeHtml(e.message || "帳號或密碼錯誤")}</div>`;
  } finally {
    loginSubmitBtn.disabled = false;
    loginSubmitBtn.textContent = "登入";
  }
});

$("#logout-btn").addEventListener("click", async () => {
  try {
    await apiPost("/api/v1/auth/logout", {});
  } catch (e) {
    // 忽略登出本身的錯誤，仍然回到登入畫面
  }
  showLoggedOut();
});

const changePasswordOverlay = $("#change-password-overlay");
const changePasswordForm = $("#change-password-form");
const changePasswordMsg = $("#change-password-msg");

$("#change-password-btn").addEventListener("click", () => {
  changePasswordMsg.innerHTML = "";
  changePasswordForm.reset();
  changePasswordOverlay.hidden = false;
});
$("#change-password-cancel").addEventListener("click", () => {
  changePasswordOverlay.hidden = true;
});
changePasswordOverlay.addEventListener("click", (ev) => {
  if (ev.target === changePasswordOverlay) changePasswordOverlay.hidden = true;
});

changePasswordForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  changePasswordMsg.innerHTML = "";

  const newPassword = $("#cp-new").value;
  const confirmPassword = $("#cp-confirm").value;
  if (newPassword !== confirmPassword) {
    changePasswordMsg.innerHTML = `<div class="form-msg error">兩次輸入的新密碼不一致。</div>`;
    return;
  }

  const submitBtn = $("#change-password-submit");
  submitBtn.disabled = true;
  try {
    await apiPost("/api/v1/auth/change-password", {
      current_password: $("#cp-current").value,
      new_password: newPassword,
    });
    changePasswordOverlay.hidden = true;
    changePasswordMsg.innerHTML = "";
  } catch (e) {
    changePasswordMsg.innerHTML = `<div class="form-msg error">${escapeHtml(e.message || "變更密碼失敗")}</div>`;
  } finally {
    submitBtn.disabled = false;
  }
});

$("#refresh-btn").addEventListener("click", loadJobs);

// ---------------------------------------------------------------------------
// 排程任務清單（REQ_013）
// ---------------------------------------------------------------------------

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

function renderJobsTable(jobs) {
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
    <div class="card fade-in">
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

function renderMessage(msg) {
  $("#main-content").innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
}

async function loadJobs() {
  try {
    const jobs = await apiGet("/api/v1/admin/jobs");
    renderJobsTable(jobs);
  } catch (e) {
    if (e.status === 401) {
      showLoggedOut("登入已過期，請重新登入。");
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
    if (e.status === 401) {
      showLoggedOut("登入已過期，請重新登入。");
      return;
    }
    alert(`觸發失敗：${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

checkSession();
