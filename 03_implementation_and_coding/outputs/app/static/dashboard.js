// 各公司各季度財務分析與股價預測系統 — 儀表板前端邏輯
// 無外部相依（不使用 CDN charting library），SVG 圖表為手刻實作。

const state = {
  loggedIn: false,
  companies: [],
  selectedTicker: "",
  selectedMarket: "",
};

const $ = (sel) => document.querySelector(sel);
const tooltipEl = $("#tooltip");

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail ? JSON.stringify(body.detail) : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(new URL(path, window.location.origin), {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
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

// ---------------------------------------------------------------------------
// Bootstrap / 登入狀態
// ---------------------------------------------------------------------------
// REQ_015：查看資料（公司清單/財務/股價/預測/回測）公開瀏覽，不需登入；
// 登入 session 僅用來解鎖「新增公司」（寫入操作，見下方 add-company modal）。

function setStatus(ok) {
  const dot = $("#status-dot");
  dot.classList.remove("ok", "err");
  dot.classList.add(ok ? "ok" : "err");
}

function showLoggedOut() {
  state.loggedIn = false;
  $("#auth-username").hidden = true;
  $("#logout-btn").hidden = true;
  $("#login-btn").hidden = false;
}

function showLoggedIn(username) {
  state.loggedIn = true;
  $("#auth-username").textContent = `已登入：${username}`;
  $("#auth-username").hidden = false;
  $("#logout-btn").hidden = false;
  $("#login-btn").hidden = true;
}

async function checkSession() {
  try {
    const me = await apiGet("/api/v1/auth/me");
    showLoggedIn(me.username);
  } catch (e) {
    showLoggedOut();
  }
}

async function tryConnect() {
  try {
    const companies = await apiGet("/api/v1/companies", { market: state.selectedMarket });
    state.companies = companies;
    setStatus(true);
    populateCompanySelect();
  } catch (e) {
    setStatus(false);
    state.companies = [];
    populateCompanySelect();
    renderGlobalMessage(`無法載入公司清單：${e.message}`);
  }
}

function populateCompanySelect() {
  const sel = $("#company-select");
  sel.innerHTML = "";
  if (state.companies.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— 尚無公司資料 —";
    sel.appendChild(opt);
    state.selectedTicker = "";
    renderGlobalMessage("目前資料庫中尚無公司資料。請先透過資料擷取排程（MOPS/SEC EDGAR）匯入財報，或使用 /api/v1/admin/ingest/trigger 觸發擷取。");
    return;
  }
  state.companies.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = `${c.market}:${c.ticker}`;
    opt.textContent = `${c.name}（${c.ticker}．${c.market === "TW" ? "台股" : "美股"}）`;
    sel.appendChild(opt);
  });
  const first = state.companies[0];
  state.selectedTicker = first.ticker;
  state.selectedMarketForTicker = first.market;
  sel.value = `${first.market}:${first.ticker}`;
  loadCompanyData();
}

function renderGlobalMessage(msg) {
  $("#main-content").innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ---------------------------------------------------------------------------
// Data loading for a selected company
// ---------------------------------------------------------------------------

async function loadCompanyData() {
  const ticker = state.selectedTicker;
  const market = state.selectedMarketForTicker;
  if (!ticker) return;

  $("#main-content").innerHTML = `
    <div class="kpi-row" id="kpi-row"></div>
    <div class="card" id="price-card">
      <div class="card-header"><h2>股價歷史與最新預測</h2><div class="legend" id="price-legend"></div></div>
      <div class="chart-wrap" id="price-chart-wrap"></div>
    </div>
    <div class="card" id="financials-card">
      <div class="card-header">
        <h2>財務指標歷史</h2>
        <div>
          <label style="font-size:12px;color:var(--text-secondary);margin-right:6px;">指標</label>
          <select id="metric-select"></select>
        </div>
      </div>
      <div class="chart-wrap" id="metric-chart-wrap"></div>
      <div class="table-scroll" id="financials-table" style="margin-top:16px;"></div>
    </div>
    <div class="card" id="backtest-card">
      <div class="card-header"><h2>預測準確率回測</h2></div>
      <div id="backtest-body"></div>
    </div>
  `;

  const [financials, prices, prediction, backtest] = await Promise.all([
    apiGet(`/api/v1/companies/${encodeURIComponent(ticker)}/financials`, { market, quarters: 40 }).catch((e) => ({ error: e })),
    apiGet(`/api/v1/companies/${encodeURIComponent(ticker)}/prices`, { market }).catch((e) => ({ error: e })),
    apiGet(`/api/v1/companies/${encodeURIComponent(ticker)}/predictions/latest`, { market }).catch((e) => ({ error: e })),
    apiGet(`/api/v1/companies/${encodeURIComponent(ticker)}/backtest`, { market }).catch((e) => ({ error: e })),
  ]);

  renderKPIs(prediction);
  renderPriceSection(prices, prediction);
  renderFinancialsSection(financials);
  renderBacktestSection(backtest);
}

// ---------------------------------------------------------------------------
// KPI row (prediction headline)
// ---------------------------------------------------------------------------

const DIRECTION_LABEL = { UP: "上漲", DOWN: "下跌", FLAT: "持平" };

function renderKPIs(prediction) {
  const row = $("#kpi-row");
  if (prediction.error) {
    row.innerHTML = `<div class="stat-tile"><div class="label">最新預測</div><div class="empty-state" style="padding:8px 0;">尚無預測資料</div></div>`;
    return;
  }
  const dirClass = prediction.direction === "UP" ? "up" : prediction.direction === "DOWN" ? "down" : "flat";
  row.innerHTML = `
    <div class="stat-tile">
      <div class="label">最新一週預測方向</div>
      <div class="value"><span class="pill ${dirClass}"><span class="dot"></span>${DIRECTION_LABEL[prediction.direction] || prediction.direction}</span></div>
      <div class="sub">基準週：${prediction.base_week_start_date}</div>
    </div>
    <div class="stat-tile">
      <div class="label">預測幅度區間</div>
      <div class="value">${prediction.range_lower_pct}<span class="unit">%</span> ~ ${prediction.range_upper_pct}<span class="unit">%</span></div>
      <div class="sub">融合模型（factor+timeseries）</div>
    </div>
    <div class="stat-tile">
      <div class="label">信心分數</div>
      <div class="value">${(prediction.confidence_score * 100).toFixed(1)}<span class="unit">%</span></div>
      <div class="sub">模型版本：${prediction.model_version}</div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Price chart + prediction projection
// ---------------------------------------------------------------------------

function renderPriceSection(prices, prediction) {
  const legend = $("#price-legend");
  const wrap = $("#price-chart-wrap");

  if (prices.error || !prices.prices || prices.prices.length === 0) {
    legend.innerHTML = "";
    wrap.innerHTML = `<div class="empty-state">尚無股價歷史資料</div>`;
    return;
  }

  const points = prices.prices.map((p) => ({ label: p.trade_date, value: p.close_price }));
  const bands = [];
  const extraSeries = [];

  if (!prediction.error) {
    const lastClose = points[points.length - 1].value;
    const predLabel = "預測";
    const ranges = [
      { name: "融合模型", color: "var(--series-1)", lower: prediction.range_lower_pct, upper: prediction.range_upper_pct },
    ];
    if (prediction.sub_models?.factor_model?.range_pct) {
      ranges.push({ name: "財報因子模型", color: "var(--series-2)", lower: prediction.sub_models.factor_model.range_pct[0], upper: prediction.sub_models.factor_model.range_pct[1] });
    }
    if (prediction.sub_models?.timeseries_model?.range_pct) {
      ranges.push({ name: "時間序列模型", color: "var(--series-3)", lower: prediction.sub_models.timeseries_model.range_pct[0], upper: prediction.sub_models.timeseries_model.range_pct[1] });
    }
    points.push({ label: predLabel, value: null }); // 佔位，讓 x 軸多一格
    ranges.forEach((r, i) => {
      extraSeries.push({
        name: r.name,
        color: r.color,
        lower: lastClose * (1 + r.lower / 100),
        upper: lastClose * (1 + r.upper / 100),
        offset: (i - (ranges.length - 1) / 2) * 0.18,
      });
    });
    legend.innerHTML = ranges
      .map((r) => `<div class="item"><span class="key" style="background:${r.color}"></span>${escapeHtml(r.name)}</div>`)
      .join("");
  } else {
    legend.innerHTML = "";
  }

  drawPriceChart(wrap, points, extraSeries, { yFormat: (v) => v.toFixed(1) });
}

// ---------------------------------------------------------------------------
// Financial metrics section
// ---------------------------------------------------------------------------

const METRICS = [
  { key: "revenue", label: "營收", unit: "", scale: (v) => v / 1e8, suffix: "億" },
  { key: "eps", label: "EPS", unit: "元" },
  { key: "gross_margin", label: "毛利率", unit: "%" },
  { key: "net_margin", label: "淨利率", unit: "%" },
  { key: "debt_ratio", label: "負債比", unit: "%" },
  { key: "operating_cash_flow", label: "營業現金流", unit: "", scale: (v) => v / 1e8, suffix: "億" },
  { key: "pe_ratio", label: "本益比", unit: "" },
];

function renderFinancialsSection(financials) {
  const metricSelect = $("#metric-select");
  const chartWrap = $("#metric-chart-wrap");
  const tableWrap = $("#financials-table");

  if (financials.error || !financials.reports || financials.reports.length === 0) {
    metricSelect.innerHTML = "";
    chartWrap.innerHTML = `<div class="empty-state">尚無財務指標資料</div>`;
    tableWrap.innerHTML = "";
    return;
  }

  const reports = [...financials.reports].sort((a, b) =>
    a.fiscal_year !== b.fiscal_year ? a.fiscal_year - b.fiscal_year : a.fiscal_quarter - b.fiscal_quarter
  );

  metricSelect.innerHTML = METRICS.map((m) => `<option value="${m.key}">${m.label}</option>`).join("");
  metricSelect.onchange = () => drawMetricChart(reports, metricSelect.value);
  drawMetricChart(reports, METRICS[0].key);

  const cols = ["季度", ...METRICS.map((m) => m.label + (m.unit ? `(${m.unit})` : m.suffix ? `(${m.suffix})` : ""))];
  const rows = reports.map((r) => {
    const q = `${r.fiscal_year}Q${r.fiscal_quarter}`;
    const cells = METRICS.map((m) => {
      const raw = r[m.key];
      if (raw === null || raw === undefined) return "—";
      const v = m.scale ? m.scale(raw) : raw;
      return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    });
    return [q, ...cells];
  });
  tableWrap.innerHTML = `<table>
    <thead><tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${row.map((c) => `<td>${escapeHtml(String(c))}</td>`).join("")}</tr>`).join("")}</tbody>
  </table>`;
}

function drawMetricChart(reports, metricKey) {
  const metric = METRICS.find((m) => m.key === metricKey);
  const points = reports
    .filter((r) => r[metricKey] !== null && r[metricKey] !== undefined)
    .map((r) => ({ label: `${r.fiscal_year}Q${r.fiscal_quarter}`, value: metric.scale ? metric.scale(r[metricKey]) : r[metricKey] }));

  const wrap = $("#metric-chart-wrap");
  if (points.length === 0) {
    wrap.innerHTML = `<div class="empty-state">此指標尚無資料</div>`;
    return;
  }
  drawLineChart(wrap, [{ name: metric.label, color: "var(--series-1)", points }], {
    yFormat: (v) => v.toLocaleString(undefined, { maximumFractionDigits: 1 }) + (metric.suffix ? metric.suffix : metric.unit),
  });
}

// ---------------------------------------------------------------------------
// Backtest section
// ---------------------------------------------------------------------------

function renderBacktestSection(backtest) {
  const body = $("#backtest-body");
  if (backtest.error) {
    body.innerHTML = `<div class="empty-state">尚無回測資料。回測需累積至少 1 週已知結果的預測後才會產生統計，請待排程執行數週後回來查看。</div>`;
    return;
  }
  body.innerHTML = `
    <div class="kpi-row">
      <div class="stat-tile">
        <div class="label">方向準確率</div>
        <div class="value">${(backtest.directional_accuracy * 100).toFixed(1)}<span class="unit">%</span></div>
        <div class="sub">近 ${backtest.window_weeks} 週滾動視窗</div>
      </div>
      <div class="stat-tile">
        <div class="label">幅度區間命中率</div>
        <div class="value">${(backtest.range_hit_rate * 100).toFixed(1)}<span class="unit">%</span></div>
        <div class="sub">近 ${backtest.window_weeks} 週滾動視窗</div>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Generic SVG line chart (ordinal x-axis, crosshair + tooltip)
// ---------------------------------------------------------------------------

function niceTicks(min, max, count) {
  if (min === max) { min -= 1; max += 1; }
  const range = max - min;
  const rough = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  const step = (norm >= 5 ? 5 : norm >= 2 ? 2 : 1) * mag;
  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const ticks = [];
  for (let t = niceMin; t <= niceMax + step * 0.5; t += step) ticks.push(t);
  return ticks;
}

function drawLineChart(container, series, opts = {}) {
  const width = container.clientWidth || 800;
  const height = opts.height || 260;
  const pad = { top: 16, right: 20, bottom: 28, left: 56 };
  const yFormat = opts.yFormat || ((v) => v.toFixed(1));

  const labels = series[0].points.map((p) => p.label);
  const allValues = series.flatMap((s) => s.points.map((p) => p.value)).filter((v) => v !== null && v !== undefined);
  const minV = Math.min(...allValues);
  const maxV = Math.max(...allValues);
  const ticks = niceTicks(minV, maxV, 5);
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];

  const xStep = (width - pad.left - pad.right) / Math.max(labels.length - 1, 1);
  const xPos = (i) => pad.left + i * xStep;
  const yPos = (v) => height - pad.bottom - ((v - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);

  let svg = `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">`;

  ticks.forEach((t) => {
    const y = yPos(t);
    svg += `<line class="gridline" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" />`;
    svg += `<text class="axis-text" x="${pad.left - 8}" y="${y + 4}" text-anchor="end">${escapeHtml(yFormat(t))}</text>`;
  });

  const xTickEvery = Math.max(1, Math.ceil(labels.length / 8));
  labels.forEach((lab, i) => {
    if (i % xTickEvery !== 0 && i !== labels.length - 1) return;
    svg += `<text class="axis-text" x="${xPos(i)}" y="${height - pad.bottom + 18}" text-anchor="middle">${escapeHtml(String(lab))}</text>`;
  });

  series.forEach((s) => {
    const pts = s.points.map((p, i) => (p.value === null || p.value === undefined ? null : [xPos(i), yPos(p.value)]));
    const segments = [];
    let cur = [];
    pts.forEach((pt) => {
      if (pt === null) { if (cur.length > 1) segments.push(cur); cur = []; }
      else cur.push(pt);
    });
    if (cur.length > 1) segments.push(cur);
    segments.forEach((seg) => {
      const d = seg.map((pt, i) => `${i === 0 ? "M" : "L"}${pt[0].toFixed(1)},${pt[1].toFixed(1)}`).join(" ");
      svg += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />`;
    });
    const last = [...pts].reverse().find((p) => p !== null);
    if (last) {
      svg += `<circle cx="${last[0]}" cy="${last[1]}" r="4" fill="${s.color}" stroke="var(--surface-1)" stroke-width="2" />`;
    }
  });

  svg += `<line class="crosshair" id="chart-crosshair" x1="0" y1="${pad.top}" x2="0" y2="${height - pad.bottom}" style="opacity:0" />`;
  svg += `</svg>`;

  container.innerHTML = svg;
  const svgEl = container.querySelector("svg");
  attachHoverLayer(svgEl, { labels, series, xPos, yPos, pad, width, height, yFormat });
}

function attachHoverLayer(svgEl, ctx) {
  const { labels, series, xPos, pad, width, height } = ctx;
  const crosshair = svgEl.querySelector("#chart-crosshair");

  svgEl.addEventListener("pointermove", (ev) => {
    const rect = svgEl.getBoundingClientRect();
    const scaleX = ctx.width / rect.width;
    const mx = (ev.clientX - rect.left) * scaleX;
    const xStep = (width - pad.left - pad.right) / Math.max(labels.length - 1, 1);
    let idx = Math.round((mx - pad.left) / xStep);
    idx = Math.max(0, Math.min(labels.length - 1, idx));

    crosshair.setAttribute("x1", xPos(idx));
    crosshair.setAttribute("x2", xPos(idx));
    crosshair.style.opacity = 1;

    const rows = series
      .map((s) => {
        const pt = s.points[idx];
        if (!pt || pt.value === null || pt.value === undefined) return null;
        return `<div class="row"><span class="key" style="background:${s.color}"></span><span class="name">${escapeHtml(s.name)}</span><span class="val">${escapeHtml(ctx.yFormat(pt.value))}</span></div>`;
      })
      .filter(Boolean)
      .join("");
    if (!rows) { tooltipEl.style.opacity = 0; return; }

    tooltipEl.innerHTML = `<div class="date">${escapeHtml(String(labels[idx]))}</div>${rows}`;
    tooltipEl.style.opacity = 1;
    tooltipEl.style.left = ev.clientX + 14 + "px";
    tooltipEl.style.top = ev.clientY + 14 + "px";
  });

  svgEl.addEventListener("pointerleave", () => {
    crosshair.style.opacity = 0;
    tooltipEl.style.opacity = 0;
  });
}

// ---------------------------------------------------------------------------
// Price chart with prediction-range overlay (extends drawLineChart)
// ---------------------------------------------------------------------------

function drawPriceChart(container, points, extraSeries, opts = {}) {
  const width = container.clientWidth || 800;
  const height = 300;
  const pad = { top: 16, right: 20, bottom: 28, left: 56 };
  const yFormat = opts.yFormat || ((v) => v.toFixed(1));

  const labels = points.map((p) => p.label);
  const actualValues = points.map((p) => p.value).filter((v) => v !== null && v !== undefined);
  const bandValues = extraSeries.flatMap((s) => [s.lower, s.upper]);
  const allValues = [...actualValues, ...bandValues];
  const minV = Math.min(...allValues);
  const maxV = Math.max(...allValues);
  const ticks = niceTicks(minV, maxV, 5);
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];

  const xStep = (width - pad.left - pad.right) / Math.max(labels.length - 1, 1);
  const xPos = (i) => pad.left + i * xStep;
  const yPos = (v) => height - pad.bottom - ((v - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);

  let svg = `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">`;

  ticks.forEach((t) => {
    const y = yPos(t);
    svg += `<line class="gridline" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" />`;
    svg += `<text class="axis-text" x="${pad.left - 8}" y="${y + 4}" text-anchor="end">${escapeHtml(yFormat(t))}</text>`;
  });

  const xTickEvery = Math.max(1, Math.ceil(labels.length / 8));
  labels.forEach((lab, i) => {
    if (i % xTickEvery !== 0 && i !== labels.length - 1) return;
    svg += `<text class="axis-text" x="${xPos(i)}" y="${height - pad.bottom + 18}" text-anchor="middle">${escapeHtml(String(lab))}</text>`;
  });

  // 實際股價折線
  const actualPts = points.map((p, i) => (p.value === null ? null : [xPos(i), yPos(p.value)])).filter(Boolean);
  const linePath = actualPts.map((pt, i) => `${i === 0 ? "M" : "L"}${pt[0].toFixed(1)},${pt[1].toFixed(1)}`).join(" ");
  svg += `<path d="${linePath}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />`;
  const lastActual = actualPts[actualPts.length - 1];
  if (lastActual) svg += `<circle cx="${lastActual[0]}" cy="${lastActual[1]}" r="4" fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2" />`;

  // 預測區間（延伸至最後一格 "預測"）
  if (extraSeries.length > 0 && lastActual) {
    const predIdx = labels.length - 1;
    const predX = xPos(predIdx);

    extraSeries.forEach((s) => {
      const x = predX + s.offset * xStep;
      const yLower = yPos(s.lower), yUpper = yPos(s.upper);
      const yMid = (yLower + yUpper) / 2;
      // 連接虛線（僅主模型畫扇形淡色區）
      if (s.name === "融合模型") {
        svg += `<polygon points="${lastActual[0]},${lastActual[1]} ${x},${yUpper} ${x},${yLower}" fill="var(--series-1-wash)" />`;
        svg += `<line x1="${lastActual[0]}" y1="${lastActual[1]}" x2="${x}" y2="${yMid}" stroke="var(--series-1)" stroke-width="1.5" stroke-dasharray="4 3" />`;
      }
      svg += `<line x1="${x}" y1="${yLower}" x2="${x}" y2="${yUpper}" stroke="${s.color}" stroke-width="4" stroke-linecap="round" />`;
      svg += `<circle cx="${x}" cy="${yMid}" r="4" fill="${s.color}" stroke="var(--surface-1)" stroke-width="2" />`;
    });
  }

  svg += `<line class="crosshair" id="chart-crosshair" x1="0" y1="${pad.top}" x2="0" y2="${height - pad.bottom}" style="opacity:0" />`;
  svg += `</svg>`;

  container.innerHTML = svg;
  const svgEl = container.querySelector("svg");

  const hoverSeries = [{ name: "收盤價", color: "var(--series-1)", points }];
  attachHoverLayer(svgEl, { labels, series: hoverSeries, xPos, yPos, pad, width, height, yFormat });

  // 預測區間獨立 hover（因其非 ordinal 折線資料點）
  if (extraSeries.length > 0) {
    const predIdx = labels.length - 1;
    const predX = xPos(predIdx);
    extraSeries.forEach((s) => {
      const x = predX + s.offset * xStep;
      const hit = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      hit.setAttribute("x", x - 12);
      hit.setAttribute("y", pad.top);
      hit.setAttribute("width", 24);
      hit.setAttribute("height", height - pad.top - pad.bottom);
      hit.setAttribute("fill", "transparent");
      hit.addEventListener("pointermove", (ev) => {
        tooltipEl.innerHTML = `<div class="date">${escapeHtml(s.name)}</div>
          <div class="row"><span class="key" style="background:${s.color}"></span><span class="name">區間</span><span class="val">${s.lower.toFixed(2)} ~ ${s.upper.toFixed(2)}</span></div>`;
        tooltipEl.style.opacity = 1;
        tooltipEl.style.left = ev.clientX + 14 + "px";
        tooltipEl.style.top = ev.clientY + 14 + "px";
      });
      hit.addEventListener("pointerleave", () => { tooltipEl.style.opacity = 0; });
      svgEl.appendChild(hit);
    });
  }
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

$("#login-btn").addEventListener("click", () => {
  window.location.href = "/admin?next=" + encodeURIComponent(window.location.pathname);
});

$("#logout-btn").addEventListener("click", async () => {
  try {
    await apiPost("/api/v1/auth/logout", {});
  } catch (e) {
    // 忽略登出本身的錯誤，仍然回到未登入畫面
  }
  showLoggedOut();
});

$("#market-select").addEventListener("change", (e) => {
  state.selectedMarket = e.target.value;
  tryConnect();
});

$("#company-select").addEventListener("change", (e) => {
  const [market, ticker] = e.target.value.split(":");
  state.selectedTicker = ticker;
  state.selectedMarketForTicker = market;
  loadCompanyData();
});

// ---------------------------------------------------------------------------
// Add company modal（REQ_011）
// ---------------------------------------------------------------------------

const addCompanyOverlay = $("#add-company-overlay");
const addCompanyForm = $("#add-company-form");
const addCompanyMsg = $("#add-company-msg");
const addCikField = $("#add-cik-field");
const addSearchResults = $("#add-search-results");
const addTickerInput = $("#add-ticker");
const addNameInput = $("#add-name");

function openAddCompanyModal() {
  addCompanyMsg.innerHTML = "";
  addCompanyForm.reset();
  addCikField.hidden = true;
  hideSearchResults();
  addCompanyOverlay.hidden = false;
}

function closeAddCompanyModal() {
  addCompanyOverlay.hidden = true;
}

function showAddCompanyError(msg) {
  addCompanyMsg.innerHTML = `<div class="form-msg error">${escapeHtml(msg)}</div>`;
}

$("#add-company-btn").addEventListener("click", openAddCompanyModal);
$("#add-company-cancel").addEventListener("click", closeAddCompanyModal);

// ---------------------------------------------------------------------------
// Add company modal — 代碼/名稱模糊搜尋（REQ_012）
// ---------------------------------------------------------------------------

function hideSearchResults() {
  addSearchResults.hidden = true;
  addSearchResults.innerHTML = "";
}

function debounce(fn, delayMs) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}

function renderSearchResults(results) {
  if (results.length === 0) {
    addSearchResults.innerHTML = `<div class="empty">查無符合的公司，可直接手動填寫代碼與名稱。</div>`;
  } else {
    addSearchResults.innerHTML = results
      .map(
        (r) =>
          `<div class="result-item" data-ticker="${escapeHtml(r.ticker)}" data-name="${escapeHtml(r.name)}">` +
          `<span class="ticker">${escapeHtml(r.ticker)}</span><span class="name">${escapeHtml(r.name)}</span></div>`
      )
      .join("");
    addSearchResults.querySelectorAll(".result-item").forEach((el) => {
      el.addEventListener("click", () => {
        addTickerInput.value = el.dataset.ticker;
        addNameInput.value = el.dataset.name;
        hideSearchResults();
      });
    });
  }
  addSearchResults.hidden = false;
}

const runCompanySearch = debounce(async (query) => {
  if (query.trim().length === 0) {
    hideSearchResults();
    return;
  }
  try {
    const market = addCompanyForm.market.value;
    const results = await apiGet("/api/v1/companies/search", { market, q: query });
    renderSearchResults(results);
  } catch (e) {
    hideSearchResults();
  }
}, 300);

addTickerInput.addEventListener("input", (e) => runCompanySearch(e.target.value));
addNameInput.addEventListener("input", (e) => runCompanySearch(e.target.value));

addCompanyForm.querySelectorAll('input[name="market"]').forEach((radio) => {
  radio.addEventListener("change", hideSearchResults);
});

document.addEventListener("click", (ev) => {
  if (!addSearchResults.hidden && !ev.target.closest(".search-field")) hideSearchResults();
});
addCompanyOverlay.addEventListener("click", (ev) => {
  if (ev.target === addCompanyOverlay) closeAddCompanyModal();
});

addCompanyForm.querySelectorAll('input[name="market"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    addCikField.hidden = addCompanyForm.market.value !== "US";
  });
});

addCompanyForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  addCompanyMsg.innerHTML = "";

  if (!state.loggedIn) {
    showAddCompanyError("請先於右上角登入後再新增公司。");
    return;
  }

  const payload = {
    market: addCompanyForm.market.value,
    ticker: $("#add-ticker").value.trim(),
    name: $("#add-name").value.trim(),
    industry: $("#add-industry").value.trim() || null,
    cik: $("#add-cik").value.trim() || null,
  };

  try {
    const created = await apiPost("/api/v1/companies", payload);
    closeAddCompanyModal();
    await tryConnect();

    const sel = $("#company-select");
    const val = `${created.market}:${created.ticker}`;
    if ([...sel.options].some((o) => o.value === val)) {
      sel.value = val;
      state.selectedTicker = created.ticker;
      state.selectedMarketForTicker = created.market;
      await loadCompanyData();
    }

    const banner = document.createElement("div");
    banner.className = "form-msg info";
    banner.textContent = `已新增「${created.name}」（${created.ticker}）至追蹤清單。首次財務/股價資料需等排程執行，或由具 admin 權限之 API Key 呼叫 /api/v1/admin/ingest/trigger 手動觸發後才會出現。`;
    $("#main-content").prepend(banner);
  } catch (e) {
    if (e.status === 409) {
      showAddCompanyError("此公司已存在於追蹤清單。");
    } else if (e.status === 422) {
      addCikField.hidden = false;
      showAddCompanyError(e.message || "查無對應之 CIK，請手動輸入。");
    } else if (e.status === 403) {
      showAddCompanyError("新增公司需要 admin 權限。");
    } else if (e.status === 401) {
      showAddCompanyError("登入已過期，請重新登入。");
      showLoggedOut();
    } else {
      showAddCompanyError(`新增失敗：${e.message}`);
    }
  }
});

checkSession();
tryConnect();
