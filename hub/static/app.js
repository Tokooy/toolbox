/* ============================================================
   Toolbox 工具台 — 前端逻辑
   单页应用：左侧功能按钮动态生成（features.json），
   点哪个按钮切换哪个功能面板，任务全局互斥（同一时刻只跑一个）。
   ============================================================ */

'use strict';

/* ---------------- 基础工具 ---------------- */

const $ = (sel) => document.querySelector(sel);

async function api(url, opts) {
  const res = await fetch(url, opts);
  let body = null;
  try { body = await res.json(); } catch (_) { /* 非 JSON */ }
  if (!res.ok) throw new Error((body && body.error) || `HTTP ${res.status}`);
  return body;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let toastTimer = null;
function toast(msg, kind = '') {
  const el = $('#toast');
  el.textContent = msg;
  el.className = `toast show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 3600);
}

/* ---------------- 任务互斥（全局） ---------------- */

const TaskManager = {
  busy: false,
  name: null,

  acquire(name) {
    if (this.busy) return false;
    this.busy = true;
    this.name = name;
    this._paint();
    return true;
  },

  release() {
    this.busy = false;
    this.name = null;
    this._paint();
  },

  _paint() {
    const dot = $('#globalDot');
    const text = $('#globalTaskText');
    if (this.busy) {
      dot.className = 'status-dot busy';
      text.textContent = `运行中：${this.name}…`;
    } else {
      dot.className = 'status-dot ok';
      text.textContent = '空闲 · 无任务运行';
    }
  },
};

/* ---------------- 功能按钮与面板切换 ---------------- */

const ICONS = {
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
  qr: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 14h3v3h-3zM20 14h1M14 20h1M17 17h4v4h-4z"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
};

let FEATURES = [];       // features.json 内容
let currentFeature = null;
let chart = null;        // ECharts 实例（美债）
let treasuryLoaded = false;

async function initFeatures() {
  const cfg = await api('/api/apps');
  FEATURES = cfg.features || [];
  $('#appName').textContent = cfg.app_name || 'Toolbox 工具台';
  $('#appSubtitle').textContent = cfg.app_subtitle || '';

  const list = $('#featureList');
  list.innerHTML = '';

  // 只渲染已就绪的功能（未就绪条目不会出现在页面上）
  const readyFeatures = FEATURES.filter((f) => f.status === 'ready');

  readyFeatures.forEach((f) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.dataset.id = f.id;
    btn.className = 'feature-btn';
    btn.innerHTML = `
      <span class="fb-icon">${ICONS[f.icon] || ICONS.plus}</span>
      <span class="fb-name">${escapeHtml(f.name)}</span>`;
    btn.addEventListener('click', () => switchFeature(f.id));
    list.appendChild(btn);
  });

  // 侧栏收起为窄条时，用图标快速切换功能
  const iconsBar = $('#sidebarIcons');
  iconsBar.innerHTML = '';
  readyFeatures.forEach((f) => {
    const ib = document.createElement('button');
    ib.type = 'button';
    ib.dataset.id = f.id;
    ib.className = 'side-icon';
    ib.title = f.name;
    ib.setAttribute('aria-label', f.name);
    ib.innerHTML = ICONS[f.icon] || ICONS.plus;
    ib.addEventListener('click', () => switchFeature(f.id));
    iconsBar.appendChild(ib);
  });

  // 默认打开第一个 ready 功能
  const first = readyFeatures[0];
  if (first) switchFeature(first.id);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function switchFeature(id) {
  currentFeature = id;
  const meta = FEATURES.find((f) => f.id === id) || {};

  document.querySelectorAll('.feature-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.id === id);
  });
  document.querySelectorAll('.side-icon').forEach((b) => {
    b.classList.toggle('active', b.dataset.id === id);
  });

  document.querySelectorAll('.panel').forEach((p) => { p.hidden = true; });

  if (id === 'treasury') {
    $('#panel-treasury').hidden = false;
    if (!treasuryLoaded) { treasuryLoaded = true; loadTreasury(); }
    else if (chart) setTimeout(() => chart.resize(), 80);
  } else if (id === 'qrcode') {
    $('#panel-qrcode').hidden = false;
    refreshQrStatus();
  } else {
    // 预留/占位功能：统一展示"即将上线"面板
    $('#panel-coming').hidden = false;
    $('#comingName').textContent = meta.name || '即将上线';
    $('#comingDesc').textContent = meta.desc || '该功能正在开发中。';
  }
}

window.addEventListener('resize', () => { if (chart) chart.resize(); });

/* ============================================================
   功能一：美债收益率看板（逻辑与原 us-treasury-yields 保持一致）
   ============================================================ */

const SERIES_META = {
  DGS2:  { label: '2 年期',  color: '#fbbf24' },
  DGS10: { label: '10 年期', color: '#38bdf8' },
  DGS30: { label: '30 年期', color: '#a78bfa' },
};
const SPREAD_COLOR = '#f472b6';

const statsEl = $('#tStats');
const chartEl = $('#tChart');
const tBtn = $('#tRefreshBtn');
const tUpdateText = $('#tUpdateText');
const tDot = $('#tDot');

let tState = null;

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function toTs(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}
function fmtDate(ts) {
  const dt = new Date(ts);
  const pad = (n) => String(n).padStart(2, '0');
  return `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}`;
}

function lastNonNull(values) {
  for (let i = values.length - 1; i >= 0; i--) {
    if (values[i] != null) return values[i];
  }
  return null;
}

function fmtNum(v, digits = 2) {
  return v == null ? '—' : Number(v).toFixed(digits);
}

function fmtChange(v) {
  if (v == null) return '<span class="flat">无数据</span>';
  if (Math.abs(v) < 0.005) return '<span class="flat">持平</span>';
  const arrow = v > 0 ? '▲' : '▼';
  const cls = v > 0 ? 'up' : 'down';
  const sign = v > 0 ? '+' : '';
  return `<span class="${cls}">${arrow} ${sign}${v.toFixed(2)}</span>`;
}

function fmtUpdatedAt(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} `
       + `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}

function sparkline(id, values, color) {
  const pts = values.filter((v) => v != null).slice(-90);
  if (pts.length < 2) return '';
  const W = 100, H = 30, PAD = 2;
  const min = Math.min(...pts), max = Math.max(...pts);
  const span = (max - min) || 1;
  const step = W / (pts.length - 1);
  const y = (v) => (H - PAD - ((v - min) / span) * (H - PAD * 2)).toFixed(1);
  const line = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${y(v)}`).join('');
  const area = `${line} L${W},${H} L0,${H} Z`;
  return `
    <svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="spark-${id}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="${color}" stop-opacity="0.30"/>
          <stop offset="1" stop-color="${color}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${area}" fill="url(#spark-${id})"/>
      <path d="${line}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round"/>
    </svg>`;
}

function renderStats(d) {
  const cards = Object.entries(SERIES_META).map(([sid, meta]) => {
    const values = d.series[sid].values;
    const last = lastNonNull(values);
    const prevIdx = values.lastIndexOf(last);
    const prev = prevIdx > 0 ? lastNonNull(values.slice(0, prevIdx)) : null;
    const chg = (last != null && prev != null) ? last - prev : null;
    return `
      <div class="stat-card" style="--accent:${meta.color}">
        <div class="stat-label">${meta.label} 收益率</div>
        <div class="stat-value">${fmtNum(last)}<span class="unit">%</span></div>
        <div class="stat-change">${fmtChange(chg)}<span class="delta-label">较前一交易日</span></div>
        ${sparkline(sid, values, meta.color)}
      </div>`;
  });

  const v2 = lastNonNull(d.series.DGS2.values);
  const v10 = lastNonNull(d.series.DGS10.values);
  const spread = (v2 != null && v10 != null) ? v10 - v2 : null;
  const inverted = spread != null && spread < 0;
  const spreadColor = spread != null ? (inverted ? '#f87171' : '#34d399') : SPREAD_COLOR;

  cards.push(`
    <div class="stat-card" style="--accent:${SPREAD_COLOR}">
      <div class="stat-label">10Y − 2Y 期限利差</div>
      <div class="stat-value" style="color:${spreadColor}">${spread == null ? '—' : spread.toFixed(2)}<span class="unit">%</span></div>
      <span class="stat-badge ${inverted ? 'inverted' : 'normal'}">
        ${inverted ? '⛔ 曲线倒挂' : '✅ 曲线正常'}
      </span>
      <p class="stat-change" style="margin-top:6px">
        <span class="delta-label">${inverted ? '长期收益率低于短期，历史上多为衰退前兆' : '10 年期收益率高于 2 年期'}</span>
      </p>
    </div>`);

  statsEl.innerHTML = cards.join('');
}

/* 点击某条曲线：该曲线保持高亮，其他曲线变暗（仍可见，配合 emphasis.focus='series'）；
   再次点击同一条 → 恢复三条全部正常显示。三条曲线始终同时显示。 */
function bindChartClick() {
  if (!chart) return;
  chart.off('click');
  let activeIndex = null;
  chart.on('click', (params) => {
    if (!params || params.componentType !== 'series') return;
    const idx = params.seriesIndex;
    if (activeIndex === idx) {
      // 恢复全部正常显示
      chart.dispatchAction({ type: 'downplay' });
      activeIndex = null;
    } else {
      chart.dispatchAction({ type: 'downplay' });
      chart.dispatchAction({ type: 'highlight', seriesIndex: idx });
      activeIndex = idx;
    }
  });
}

function buildOption(d) {
  const times = d.dates.map(toTs);

  const series = Object.entries(SERIES_META).map(([sid, meta]) => ({
    name: meta.label,
    type: 'line',
    // 剔除 null 点：非交易日（周末/节假日）FRED 无数据，删除后曲线平滑衔接、不再断开
    data: d.series[sid].values.map((v, i) => [times[i], v]).filter(([, v]) => v != null),
    symbol: 'none',
    smooth: 0.3,
    lineStyle: { width: 2, color: meta.color },
    itemStyle: { color: meta.color },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: hexToRgba(meta.color, 0.16) },
        { offset: 1, color: hexToRgba(meta.color, 0) },
      ]),
    },
    emphasis: { focus: 'series', lineStyle: { width: 3 } },
    z: 3,
  }));

  return {
    animationDuration: 450,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10, 16, 30, 0.94)',
      borderColor: 'rgba(255, 255, 255, 0.12)',
      borderWidth: 1,
      padding: [12, 16],
      textStyle: { color: '#dbe4f3', fontSize: 12.5 },
      axisPointer: {
        type: 'cross',
        crossStyle: { color: 'rgba(255, 255, 255, 0.25)' },
        label: { backgroundColor: '#1e293b', color: '#e2e8f0' },
      },
      formatter(params) {
        const rows = params.map((p) => {
          const v = Array.isArray(p.value) ? p.value[1] : p.value;
          return `
          <div style="display:flex;align-items:center;gap:9px;margin-top:5px;line-height:1.5">
            <span style="width:10px;height:10px;border-radius:3px;background:${p.color};flex:none"></span>
            <span style="color:#8ea0bd;width:56px">${p.seriesName}</span>
            <span style="font-weight:600;font-variant-numeric:tabular-nums">${v == null ? '—' : Number(v).toFixed(2) + '%'}</span>
          </div>`;
        }).join('');
        const ts = Array.isArray(params[0].value) ? params[0].value[0] : params[0].axisValue;
        const date = ts != null ? fmtDate(Number(ts)) : '—';
        return `<div style="font-weight:700;font-size:13px">${date}</div>${rows}`;
      },
    },
    legend: {
      top: 0,
      right: 26,
      itemWidth: 16,
      itemHeight: 3,
      itemGap: 22,
      textStyle: { color: '#8ea0bd', fontSize: 12.5 },
      // 图例默认开关式切换（可任意组合显示），三条曲线默认同时显示
    },
    grid: { left: 48, right: 22, top: 40, bottom: 60 },
    xAxis: {
      type: 'time',
      min: times[0],
      max: times[times.length - 1],
      maxInterval: 366 * 24 * 3600 * 1000,
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.12)' } },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11.5, formatter: fmtDate },
    },
    yAxis: {
      type: 'value',
      scale: true,
      name: '收益率 (%)',
      nameTextStyle: { color: '#64748b', fontSize: 11.5, padding: [0, 0, 0, -8] },
      axisLabel: { color: '#64748b', fontSize: 11.5, formatter: '{value}' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.09)', type: 'dashed' } },
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
    ],
    toolbox: {
      show: true,
      right: 0,
      top: 0,
      itemSize: 15,
      feature: {
        restore: {
          show: true,
          title: '还原视图',
          iconStyle: { borderColor: '#8ea0bd' },
          emphasis: { iconStyle: { borderColor: '#e6edf7' } },
        },
      },
    },
    series,
  };
}

function renderTreasury(d) {
  tState = d;
  if (d.no_data) {
    // 无本地缓存：不联网自动获取（网络不通时避免卡死），提示用户按需获取
    statsEl.innerHTML = '';
    chartEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.21 15.89A10 10 0 1 1 8 2.83"/>
            <path d="M22 12A10 10 0 0 0 12 2v10z"/>
          </svg>
        </div>
        <p class="empty-title">暂无本地数据</p>
        <p class="empty-desc">本地缓存已被清空。请点击右上角「获取最新数据」按钮联网获取（FRED 数据源）。
          若无法直连 FRED，可为本机配置代理（export HTTPS_PROXY=…）后重启服务再试。</p>
      </div>`;
    tUpdateText.textContent = '无本地数据 · 请点击「获取最新数据」';
    tDot.className = 'status-dot';
    return;
  }
  renderStats(d);
  if (typeof echarts === 'undefined') {
    chartEl.innerHTML = '<div style="height:100%;display:grid;place-items:center;color:#8ea0bd;font-size:14px">'
      + '图表库 ECharts 加载失败，请检查网络后刷新页面（CDN: cdn.jsdelivr.net）</div>';
  } else {
    if (!chart) chart = echarts.init(chartEl);
    chart.setOption(buildOption(d), { notMerge: true });
    bindChartClick();
  }

  tUpdateText.textContent = `数据截至 ${d.last_date || '—'} · ${d.rows} 个交易日 · 更新于 ${fmtUpdatedAt(d.updated_at)}`;
  tDot.className = 'status-dot ok';
}

async function loadTreasury() {
  try {
    const d = await api('/api/treasury/data');
    renderTreasury(d);
  } catch (err) {
    tDot.className = 'status-dot err';
    tUpdateText.textContent = '数据加载失败';
    chartEl.innerHTML = '<div style="height:100%;display:grid;place-items:center;color:#8ea0bd;font-size:14px">'
      + '无法加载数据：' + err.message + '</div>';
    toast('数据加载失败，请刷新页面重试', 'err');
  }
}

/* 刷新按钮：与二维码生成互斥（服务端也有全局锁兜底） */
tBtn.addEventListener('click', async () => {
  if (tBtn.disabled) return;
  if (!TaskManager.acquire('美债数据刷新')) {
    toast('有任务正在运行，请稍候再试', 'err');
    return;
  }
  tBtn.disabled = true;
  tBtn.classList.add('loading');
  tDot.className = 'status-dot busy';
  tUpdateText.textContent = '正在从 FRED 获取最新数据…';
  openModal('获取最新数据', '运行中', 'running');
  setModalBody('正在从 FRED 获取最新数据…\n\n'
    + '首次获取需下载 2020 年至今全部数据；之后为增量获取，只取缺失的几天，通常几秒完成。');
  try {
    const d = await api('/api/treasury/refresh', { method: 'POST' });
    renderTreasury(d);
    const rm = d.refresh_meta || {};
    let head, detail;
    if (rm.mode === 'incremental' && rm.new_dates === 0) {
      head = '✓ 已是最新数据';
      detail = `数据截至 ${d.last_date}（FRED 尚未发布更新的交易日数据）\n共 ${d.rows} 个交易日`;
    } else if (rm.mode === 'incremental') {
      head = '✓ 增量更新完成';
      detail = `数据截至 ${d.last_date} · 共 ${d.rows} 个交易日\n本次新增 ${rm.new_dates} 天数据`;
    } else {
      head = '✓ 数据获取完成';
      detail = `数据截至 ${d.last_date} · 共 ${d.rows} 个交易日`;
    }
    modalState.textContent = '✓ 完成';
    modalState.className = 'log-state done';
    setModalBody(`${head}\n\n${detail}\n\n数据为美国交易日收盘值（美东时间），与北京时间存在时差，\nFRED 通常在美东交易日收盘后更新。`);
    scheduleModalClose(3);
  } catch (err) {
    tDot.className = 'status-dot err';
    if (tState) tUpdateText.textContent = `数据截至 ${tState.last_date}（更新失败）`;
    else tUpdateText.textContent = '获取失败';
    modalState.textContent = '✕ 失败';
    modalState.className = 'log-state error';
    setModalBody(`从 FRED 获取数据失败：\n\n${err.message}`);
    keepModalOpen('任务失败，可关闭弹窗后重试（本地已缓存的数据不受影响）');
  } finally {
    TaskManager.release();
    tBtn.disabled = false;
    tBtn.classList.remove('loading');
  }
});

/* ============================================================
   功能二：二维码批量生成（全新界面）
   ============================================================ */

const dropzone = $('#dropzone');
const fileInput = $('#fileInput');
const fileInfo = $('#fileInfo');
const fileNameEl = $('#fileName');
const fileMetaEl = $('#fileMeta');
const fileClear = $('#fileClear');
const runBtn = $('#runBtn');
const runBtnText = $('#runBtnText');
const runHint = $('#runHint');
const appModal = $('#appModal');
const modalClose = $('#modalClose');
const modalFoot = $('#modalFoot');
const modalBody = $('#modalBody');
const modalState = $('#modalState');
const modalTitle = $('#modalTitle');
const resultCard = $('#resultCard');
const resultMeta = $('#resultMeta');
const resultActions = $('#resultActions');
const resultFrame = $('#resultFrame');

let currentFile = null;
let pollTimer = null;

/* ---- 通用提示弹窗（美债刷新等任务使用） ---- */
let modalCloseTimer = null;

function openModal(title, stateText, stateCls) {
  modalTitle.textContent = title || '提示';
  modalState.textContent = stateText || '';
  modalState.className = 'log-state' + (stateCls ? ' ' + stateCls : '');
  modalBody.innerHTML = '';
  modalFoot.innerHTML = '';
  appModal.hidden = false;
  clearTimeout(modalCloseTimer);
  document.body.style.overflow = 'hidden';
}
function closeModal() {
  appModal.hidden = true;
  modalFoot.innerHTML = '';
  clearTimeout(modalCloseTimer);
  document.body.style.overflow = '';
}
function setModalBody(text) {
  modalBody.textContent = text;
  modalBody.scrollTop = modalBody.scrollHeight;
}
/* 完成后自动关闭（一闪即过）；失败则停留让用户细看 */
function scheduleModalClose(seconds) {
  clearTimeout(modalCloseTimer);
  let left = seconds;
  modalFoot.innerHTML = `<span class="modal-countdown">${left} 秒后自动关闭</span>`;
  modalCloseTimer = setInterval(() => {
    left -= 1;
    if (left <= 0) {
      clearInterval(modalCloseTimer);
      closeModal();
      return;
    }
    modalFoot.innerHTML = `<span class="modal-countdown">${left} 秒后自动关闭</span>`;
  }, 1000);
}
function keepModalOpen(msg) {
  clearTimeout(modalCloseTimer);
  modalFoot.innerHTML = `<span>${msg}</span>`;
}
modalClose.addEventListener('click', closeModal);
appModal.addEventListener('click', (e) => { if (e.target === appModal) closeModal(); });

/* ---- 上传 ---- */
function setFileInfo(name, size, modified) {
  currentFile = { name, size, modified };
  fileNameEl.textContent = name;
  fileMetaEl.textContent = `${(size / 1024).toFixed(1)} KB · ${modified || '刚刚上传'}`;
  fileInfo.hidden = false;
  runBtn.disabled = false;
  runHint.textContent = '文件已就绪，点击「开始生成二维码」运行。';
  runHint.className = 'run-hint';
}

async function uploadFile(file) {
  if (!file) return;
  if (!/\.(xlsx|xls)$/i.test(file.name)) {
    toast('仅支持 .xlsx / .xls 文件', 'err');
    return;
  }
  if (TaskManager.busy) {
    toast('有任务正在运行，请稍候再上传', 'err');
    return;
  }
  try {
    const buf = await file.arrayBuffer();
    const res = await fetch(`/api/qrcode/upload?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      body: buf,
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || '上传失败');
    setFileInfo(body.filename, buf.byteLength, null);
    toast('✓ Excel 已上传', 'ok');
  } catch (err) {
    toast('✕ ' + err.message, 'err');
  }
}

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
  fileInput.value = '';
});
['dragover', 'dragenter'].forEach((ev) => {
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
});
['dragleave', 'drop'].forEach((ev) => {
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });
});
dropzone.addEventListener('drop', (e) => {
  const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) uploadFile(f);
});
fileClear.addEventListener('click', () => {
  currentFile = null;
  fileInfo.hidden = true;
  runBtn.disabled = true;
  runHint.textContent = '';
});

/* ---- 状态与结果 ---- */
async function refreshQrStatus() {
  try {
    const s = await api('/api/qrcode/status');
    if (s.input_files && s.input_files.length) {
      const f = s.input_files[0];
      if (!currentFile) setFileInfo(f.name, f.size, f.modified);
    } else if (!currentFile) {
      runBtn.disabled = true;
      runHint.textContent = 'input/ 目录为空：请先上传 Excel 文件。';
    }
    if (s.has_result && resultCard.hidden) {
      // 面板尚未展示且已有历史结果时，先展示出来
      const r = await api('/api/qrcode/result');
      if (r.has_result) renderResult(r);
    }
  } catch (_) { /* 忽略状态刷新失败 */ }
}

function renderResult(r) {
  resultCard.hidden = false;
  if (r.html) resultFrame.srcdoc = r.html;

  const parts = [];
  if (r.html_name) parts.push(`HTML 输出 <b>${escapeHtml(r.html_name)}</b>`);
  if (r.xlsx_name) parts.push(`Excel 输出 <b>${escapeHtml(r.xlsx_name)}</b>`);
  resultMeta.innerHTML = parts.join(' · ') || '';

  resultActions.innerHTML = (r.outputs || []).map((o) => `
    <a class="btn btn-ghost btn-sm" href="${o.url}" download>
      <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      <span>下载 ${o.kind === 'html' ? 'HTML' : 'Excel'}</span>
    </a>`).join('');
}

/* ---- 运行与轮询 ---- */
runBtn.addEventListener('click', async () => {
  if (runBtn.disabled) return;
  if (!currentFile) {
    toast('请先上传 Excel 文件', 'err');
    return;
  }
  if (!TaskManager.acquire('二维码生成')) {
    toast('有任务正在运行，请稍候再试', 'err');
    return;
  }

  runBtn.disabled = true;
  runBtn.classList.add('loading');
  runBtnText.textContent = '正在生成…';
  // 清空旧结果，避免把上次的预览误认为本次输出
  resultCard.hidden = true;
  resultActions.innerHTML = '';
  resultMeta.innerHTML = '';
  resultFrame.srcdoc = '';
  runHint.textContent = '任务已在后台运行，完成后会提示；生成期间不会并发执行其他任务。';
  runHint.className = 'run-hint';

  try {
    const { task_id } = await api('/api/qrcode/run', { method: 'POST' });
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const t = await api(`/api/qrcode/task/${task_id}`);

      if (t.status === 'done') {
        runHint.textContent = `✓ 生成完成：${t.result && t.result.html_name}`;
        runHint.className = 'run-hint ok';
        renderResult(t.result);
        toast(`✓ 二维码生成完成（${t.result && t.result.html_name}）`, 'ok');
        break;
      }
      if (t.status === 'error') {
        runHint.textContent = '✕ 生成失败，请查看弹窗中的错误日志';
        runHint.className = 'run-hint err';
        // 失败时弹窗展示完整日志，便于排查
        openModal('二维码生成失败', '✕ 失败', 'error');
        setModalBody((t.log || []).join('\n') || t.error || '未知错误');
        keepModalOpen('任务失败，可关闭弹窗后重试');
        toast('✕ 生成失败', 'err');
        break;
      }
      await sleep(700);
    }
  } catch (err) {
    runHint.textContent = '✕ 请求失败';
    runHint.className = 'run-hint err';
    toast('✕ ' + err.message, 'err');
  } finally {
    TaskManager.release();
    runBtn.disabled = false;
    runBtn.classList.remove('loading');
    runBtnText.textContent = '开始生成二维码';
    refreshQrStatus();
  }
});

/* ---------------- 侧栏收起 / 展开 ---------------- */

const layoutEl = document.querySelector('.layout');
const sidebarToggle = $('#sidebarToggle');

function setSidebarCollapsed(collapsed) {
  layoutEl.classList.toggle('sidebar-collapsed', collapsed);
  // 图标方向由 CSS 控制：展开时旋转 180° 显示「<」，收起时显示「>」
  // 收起后主区域变宽，通知图表重新适配尺寸
  if (chart) setTimeout(() => chart.resize(), 380);
}
sidebarToggle.addEventListener('click', () => {
  const collapsed = layoutEl.classList.toggle('sidebar-collapsed');
  setSidebarCollapsed(collapsed);
});

/* ---------------- 初始化 ---------------- */

(async function boot() {
  try {
    await initFeatures();
  } catch (err) {
    toast('功能配置加载失败：' + err.message, 'err');
  }
})();
