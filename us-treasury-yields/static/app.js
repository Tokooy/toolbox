/* ============================================================
   美国国债收益率看板 — 前端逻辑
   数据接口：GET /api/data（读取本地缓存）、POST /api/refresh（联网更新）
   ============================================================ */

'use strict';

const SERIES_META = {
  DGS2:  { label: '2 年期',  color: '#fbbf24' },
  DGS10: { label: '10 年期', color: '#38bdf8' },
  DGS30: { label: '30 年期', color: '#a78bfa' },
};
const SPREAD_COLOR = '#f472b6';

const $ = (sel) => document.querySelector(sel);
const statsEl = $('#stats');
const chartEl = $('#chart');
const btn = $('#refreshBtn');
const updateText = $('#updateText');
const statusDot = $('#statusDot');

let chart = null;      // ECharts 实例
let state = null;      // 当前数据快照 { dates, series, ... }

/* ---------------- 工具函数 ---------------- */

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

/* 日期工具：FRED 日期是日历日，统一用 UTC 构造/格式化，避免时区偏移导致日期错位 */
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

let toastTimer = null;
function setToast(msg, kind = '') {
  const el = $('#toast');
  el.textContent = msg;
  el.className = `toast show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 3200);
}

async function api(url, opts) {
  const res = await fetch(url, opts);
  let body = null;
  try { body = await res.json(); } catch (_) { /* 非 JSON 响应 */ }
  if (!res.ok) throw new Error((body && body.error) || `HTTP ${res.status}`);
  return body;
}

/* ---------------- 统计卡片 ---------------- */

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

/* ---------------- 图表 ---------------- */

function buildOption(d) {
  /* 横轴时间戳（UTC，保证 YYYY-MM-DD 逐字对应） */
  const times = d.dates.map(toTs);

  const series = Object.entries(SERIES_META).map(([sid, meta]) => ({
    name: meta.label,
    type: 'line',
    data: d.series[sid].values.map((v, i) => [times[i], v]),
    symbol: 'none',
    smooth: 0.25,
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
        /* 时间轴下每个点的 value 是 [时间戳, 数值] 数组，取 [1] 为收益率、[0] 为日期 */
        const rows = params.map((p) => {
          const v = Array.isArray(p.value) ? p.value[1] : p.value;
          return `
          <div style="display:flex;align-items:center;gap:9px;margin-top:5px;line-height:1.5">
            <span style="width:10px;height:10px;border-radius:3px;background:${p.color};flex:none"></span>
            <span style="color:#8ea0bd;width:56px">${p.seriesName}</span>
            <span style="font-weight:600;font-variant-numeric:tabular-nums">${v == null ? '—' : Number(v).toFixed(2) + '%'}</span>
          </div>`;
        }).join('');
        /* 工具提示框顶部：具体日期 YYYY-MM-DD */
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
    },
    grid: { left: 48, right: 22, top: 40, bottom: 60 },
    xAxis: {
      type: 'time',
      min: times[0],
      max: times[times.length - 1],
      /* 全视图下刻度间隔不小于约一年（2020/2021/…按年分格，底下不再密密麻麻）；
         滚轮放大后自动细化为季度 / 月份 / 日期 */
      maxInterval: 366 * 24 * 3600 * 1000,
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.12)' } },
      axisTick: { show: false },
      /* 横轴标签一律显示完整日期 YYYY-MM-DD */
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
    /* 鼠标滚轮缩放时间跨度（需求 9）：inside 型 dataZoom */
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,   // 滚轮 → 时间轴放大/缩小
        moveOnMouseMove: true,    // 按住拖拽 → 平移时间窗口
        moveOnMouseWheel: false,  // 避免与滚轮缩放冲突
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

function renderChart(d) {
  if (!chart) chart = echarts.init(chartEl);
  chart.setOption(buildOption(d), { notMerge: true });
}

/* ---------------- 渲染入口 ---------------- */

function render(d) {
  state = d;
  renderStats(d);
  renderChart(d);

  updateText.textContent = `数据截至 ${d.last_date || '—'} · ${d.rows} 个交易日 · 更新于 ${fmtUpdatedAt(d.updated_at)}`;
  statusDot.className = 'status-dot ok';
}

async function loadInitial() {
  try {
    const d = await api('/api/data');
    render(d);
  } catch (err) {
    statusDot.className = 'status-dot err';
    updateText.textContent = '数据加载失败';
    chartEl.innerHTML = '<div style="height:100%;display:grid;place-items:center;color:#8ea0bd;font-size:14px">'
      + '无法加载数据：' + err.message + '</div>';
    setToast('数据加载失败，请刷新页面重试', 'err');
  }
}

/* ---------------- 按钮：按需获取最新数据（需求 6） ---------------- */

btn.addEventListener('click', async () => {
  if (btn.disabled) return;
  btn.disabled = true;
  btn.classList.add('loading');
  statusDot.className = 'status-dot';
  updateText.textContent = '正在从 FRED 获取最新数据…';
  try {
    const d = await api('/api/refresh', { method: 'POST' });
    render(d);
    setToast(`✓ 已获取最新数据（截至 ${d.last_date}）`, 'ok');
  } catch (err) {
    statusDot.className = 'status-dot err';
    if (state) {
      updateText.textContent = `数据截至 ${state.last_date}（更新失败）`;
    } else {
      updateText.textContent = '获取失败';
    }
    setToast('✕ ' + err.message, 'err');
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
});

/* ---------------- 初始化 ---------------- */

window.addEventListener('resize', () => { if (chart) chart.resize(); });
loadInitial();
