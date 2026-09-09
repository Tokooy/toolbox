/* ============================================================
   Toolbox 工具台 — 前端逻辑（Vue 3，无构建，本地离线运行）
   单页应用：左侧功能按钮由 features.json 动态生成，
   点哪个按钮切换哪个功能面板，任务全局互斥（同一时刻只跑一个）。

   组件：
     <app-root>      顶栏 + 侧栏 + 面板容器 + Modal/Toast
     <treasury-panel> 美债收益率看板（ECharts）
     <qrcode-panel>   二维码批量生成：紧凑上传/运行 + 任务进度条
                      + 结果「每 3 个一组」左右翻页扫码
   ============================================================ */

'use strict';

/* ---------------- 全局状态（轻量 store） ---------------- */

const store = Vue.reactive({
  appName: 'Toolbox 工具台',
  appSubtitle: '',
  features: [],          // 已就绪功能（来自 /api/apps）
  active: null,          // 当前功能 id
  sidebarCollapsed: false,
  taskBusy: false,       // 全局任务互斥
  taskName: null,
});

const toastState = Vue.reactive({ visible: false, text: '', kind: '' });
let _toastTimer = null;
function toast(text, kind) {
  toastState.text = text;
  toastState.kind = kind || '';
  toastState.visible = true;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { toastState.visible = false; }, 3600);
}

const modalState = Vue.reactive({
  visible: false, title: '提示', stateText: '', stateCls: '',
  body: '', foot: '', countdown: null, _timer: null,
});
function openModal(title, stateText, stateCls) {
  modalState.title = title || '提示';
  modalState.stateText = stateText || '';
  modalState.stateCls = stateCls || '';
  modalState.body = '';
  modalState.foot = '';
  modalState.visible = true;
  modalState.countdown = null;
  clearInterval(modalState._timer);
}
function closeModal() {
  modalState.visible = false;
  clearInterval(modalState._timer);
  modalState.countdown = null;
}
function setModalBody(text) { modalState.body = text; }
function scheduleModalClose(seconds) {
  clearInterval(modalState._timer);
  let left = seconds;
  modalState.countdown = left;
  modalState.foot = left + ' 秒后自动关闭';
  modalState._timer = setInterval(() => {
    left -= 1;
    if (left <= 0) { clearInterval(modalState._timer); closeModal(); return; }
    modalState.countdown = left;
    modalState.foot = left + ' 秒后自动关闭';
  }, 1000);
}
function keepModalOpen(msg) {
  clearInterval(modalState._timer);
  modalState.foot = msg || '';
  modalState.countdown = null;
}

/* ---------------- 基础工具 ---------------- */

async function api(url, opts) {
  const res = await fetch(url, opts);
  let body = null;
  try { body = await res.json(); } catch (e) { /* 非 JSON */ }
  if (!res.ok) throw new Error((body && body.error) || ('HTTP ' + res.status));
  return body;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------------- 图标（内联 SVG 常量） ---------------- */

const ICONS = {
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
  qr: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 14h3v3h-3zM20 14h1M14 20h1M17 17h4v4h-4z"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
  left: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
  right: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
};

/* ============================================================
   通用 Modal（任务日志 / 提示）
   ============================================================ */

const ModalBox = {
  template: `
  <transition name="fade">
  <div class="modal-mask" v-if="modalState.visible" @click.self="closeModal">
    <div class="modal" role="dialog">
      <div class="modal-head">
        <div class="modal-title">
          <span class="modal-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </span>
          <span>{{ modalState.title }}</span>
          <span class="log-state" :class="modalState.stateCls">{{ modalState.stateText }}</span>
        </div>
        <button class="modal-close" type="button" title="关闭" @click="closeModal">✕</button>
      </div>
      <pre class="log"><span class="log-dim"></span>{{ modalState.body }}</pre>
      <div class="modal-foot"><span v-if="modalState.countdown != null" class="modal-countdown">{{ modalState.countdown }} 秒后自动关闭</span><span v-else>{{ modalState.foot }}</span></div>
    </div>
  </div>
  </transition>`,
  setup() {
    return { modalState, closeModal };
  },
};

const ToastBox = {
  template: `
  <div class="toast" :class="[toastState.visible ? 'show' : '', toastState.kind]" role="status">{{ toastState.text }}</div>`,
  setup() {
    return { toastState };
  },
};

/* ============================================================
   美债收益率面板（ECharts，逻辑与原实现一致）
   ============================================================ */

const SERIES_META = {
  DGS2:  { label: '2 年期',  color: '#fbbf24' },
  DGS10: { label: '10 年期', color: '#38bdf8' },
  DGS30: { label: '30 年期', color: '#a78bfa' },
};
const SPREAD_COLOR = '#f472b6';

const TreasuryPanel = {
  template: `
  <section class="panel" v-show="isActive">
    <div class="panel-head">
      <div>
        <h2>美债收益率看板</h2>
        <p class="panel-sub">美国 2 / 10 / 30 年期国债收益率 · 数据来源 FRED（圣路易斯联储）</p>
      </div>
      <div class="panel-actions">
        <div class="update-info">
          <span class="status-dot" :class="dotCls"></span>
          <span>{{ updateText }}</span>
        </div>
        <button class="btn btn-primary btn-sm" type="button" :disabled="refreshing" @click="refresh">
          <span class="btn-icon" v-html="ICONS.refresh"></span>
          <span>{{ refreshing ? '获取中…' : '获取最新数据' }}</span>
        </button>
      </div>
    </div>

    <section class="stats" id="tStats" aria-label="最新收益率概览" v-html="statsHtml"></section>

    <div class="chart-card">
      <div class="chart-head">
        <div>
          <h3>收益率走势（2020 年至今）</h3>
          <p class="chart-tip">滚轮缩放时间跨度 · 按住拖拽平移 · 右上角按钮还原视图 · 悬停查看每日数值</p>
        </div>
      </div>
      <div ref="chartEl" class="chart" role="img" aria-label="美国 2/10/30 年期国债收益率曲线图"></div>
    </div>

    <footer class="panel-foot">
      <p>数据来源：<a href="https://fred.stlouisfed.org/" target="_blank" rel="noopener">FRED</a>
        · <span class="swatch" style="--c:#fbbf24"></span>DGS2（2 年期）
        · <span class="swatch" style="--c:#38bdf8"></span>DGS10（10 年期）
        · <span class="swatch" style="--c:#a78bfa"></span>DGS30（30 年期）—— 美国国债恒定到期收益率（日频收盘值）</p>
    </footer>
  </section>`,
  props: { active: { type: String, default: null } },
  setup(props) {
    const chartEl = Vue.ref(null);
    const isActive = Vue.computed(() => props.active === 'treasury');
    const state = Vue.reactive({
      dotCls: '', updateText: '正在加载数据…',
      data: null, chart: null, loaded: false, refreshing: false,
      statsHtml: '',
    });

    function hexToRgba(hex, alpha) {
      const n = parseInt(hex.slice(1), 16);
      return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
    }
    function toTs(dateStr) {
      const p = dateStr.split('-').map(Number);
      return Date.UTC(p[0], p[1] - 1, p[2]);
    }
    function fmtDate(ts) {
      const d = new Date(ts);
      const pad = (n) => String(n).padStart(2, '0');
      return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate());
    }
    function lastNonNull(values) {
      for (let i = values.length - 1; i >= 0; i--) if (values[i] != null) return values[i];
      return null;
    }
    function fmtNum(v) { return v == null ? '—' : Number(v).toFixed(2); }
    function fmtChange(v) {
      if (v == null) return '<span class="flat">无数据</span>';
      if (Math.abs(v) < 0.005) return '<span class="flat">持平</span>';
      const arrow = v > 0 ? '▲' : '▼';
      const cls = v > 0 ? 'up' : 'down';
      const sign = v > 0 ? '+' : '';
      return '<span class="' + cls + '">' + arrow + ' ' + sign + v.toFixed(2) + '</span>';
    }
    function fmtUpdatedAt(iso) {
      if (!iso) return '—';
      const d = new Date(iso);
      const pad = (n) => String(n).padStart(2, '0');
      return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()) + ' '
        + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ' UTC';
    }
    function sparkline(id, values, color) {
      const pts = values.filter((v) => v != null).slice(-90);
      if (pts.length < 2) return '';
      const W = 100, H = 30, PAD = 2;
      const min = Math.min.apply(null, pts), max = Math.max.apply(null, pts);
      const span = (max - min) || 1;
      const step = W / (pts.length - 1);
      const y = (v) => (H - PAD - ((v - min) / span) * (H - PAD * 2)).toFixed(1);
      const line = pts.map((v, i) => (i === 0 ? 'M' : 'L') + (i * step).toFixed(1) + ',' + y(v)).join('');
      const area = line + ' L' + W + ',' + H + ' L0,' + H + ' Z';
      return '<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">'
        + '<defs><linearGradient id="spark-' + id + '" x1="0" y1="0" x2="0" y2="1">'
        + '<stop offset="0" stop-color="' + color + '" stop-opacity="0.30"/>'
        + '<stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>'
        + '<path d="' + area + '" fill="url(#spark-' + id + ')"/>'
        + '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    }
    function renderStats(d) {
      const cards = Object.keys(SERIES_META).map((sid) => {
        const meta = SERIES_META[sid];
        const values = d.series[sid].values;
        const last = lastNonNull(values);
        const prevIdx = values.lastIndexOf(last);
        const prev = prevIdx > 0 ? lastNonNull(values.slice(0, prevIdx)) : null;
        const chg = (last != null && prev != null) ? last - prev : null;
        return '<div class="stat-card" style="--accent:' + meta.color + '">'
          + '<div class="stat-label">' + meta.label + ' 收益率</div>'
          + '<div class="stat-value">' + fmtNum(last) + '<span class="unit">%</span></div>'
          + '<div class="stat-change">' + fmtChange(chg) + '<span class="delta-label">较前一交易日</span></div>'
          + sparkline(sid, values, meta.color) + '</div>';
      });
      const v2 = lastNonNull(d.series.DGS2.values);
      const v10 = lastNonNull(d.series.DGS10.values);
      const spread = (v2 != null && v10 != null) ? v10 - v2 : null;
      const inverted = spread != null && spread < 0;
      const spreadColor = spread != null ? (inverted ? '#f87171' : '#34d399') : SPREAD_COLOR;
      cards.push('<div class="stat-card" style="--accent:' + SPREAD_COLOR + '">'
        + '<div class="stat-label">10Y − 2Y 期限利差</div>'
        + '<div class="stat-value" style="color:' + spreadColor + '">' + (spread == null ? '—' : spread.toFixed(2)) + '<span class="unit">%</span></div>'
        + '<span class="stat-badge ' + (inverted ? 'inverted' : 'normal') + '">'
        + (inverted ? '⛔ 曲线倒挂' : '✅ 曲线正常') + '</span>'
        + '<p class="stat-change" style="margin-top:6px"><span class="delta-label">'
        + (inverted ? '长期收益率低于短期，历史上多为衰退前兆' : '10 年期收益率高于 2 年期')
        + '</span></p></div>');
      state.statsHtml = cards.join('');
    }

    function buildOption(d) {
      const times = d.dates.map(toTs);
      const series = Object.keys(SERIES_META).map((sid) => {
        const meta = SERIES_META[sid];
        return {
          name: meta.label, type: 'line',
          data: d.series[sid].values.map((v, i) => [times[i], v]).filter((x) => x[1] != null),
          symbol: 'none', smooth: 0.3,
          lineStyle: { width: 2, color: meta.color },
          itemStyle: { color: meta.color },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: hexToRgba(meta.color, 0.16) },
            { offset: 1, color: hexToRgba(meta.color, 0) },
          ]) },
          emphasis: { focus: 'series', lineStyle: { width: 3 } },
          z: 3,
        };
      });
      return {
        animationDuration: 450,
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(10, 16, 30, 0.94)', borderColor: 'rgba(255, 255, 255, 0.12)',
          borderWidth: 1, padding: [12, 16], textStyle: { color: '#dbe4f3', fontSize: 12.5 },
          axisPointer: {
            type: 'cross', crossStyle: { color: 'rgba(255, 255, 255, 0.25)' },
            label: { backgroundColor: '#1e293b', color: '#e2e8f0' },
          },
          formatter(params) {
            const rows = params.map((p) => {
              const v = Array.isArray(p.value) ? p.value[1] : p.value;
              return '<div style="display:flex;align-items:center;gap:9px;margin-top:5px;line-height:1.5">'
                + '<span style="width:10px;height:10px;border-radius:3px;background:' + p.color + ';flex:none"></span>'
                + '<span style="color:#8ea0bd;width:56px">' + p.seriesName + '</span>'
                + '<span style="font-weight:600;font-variant-numeric:tabular-nums">' + (v == null ? '—' : Number(v).toFixed(2) + '%') + '</span></div>';
            }).join('');
            const ts = Array.isArray(params[0].value) ? params[0].value[0] : params[0].axisValue;
            return '<div style="font-weight:700;font-size:13px">' + (ts != null ? fmtDate(Number(ts)) : '—') + '</div>' + rows;
          },
        },
        legend: { top: 0, right: 26, itemWidth: 16, itemHeight: 3, itemGap: 22, textStyle: { color: '#8ea0bd', fontSize: 12.5 } },
        grid: { left: 48, right: 22, top: 40, bottom: 60 },
        xAxis: {
          type: 'time', min: times[0], max: times[times.length - 1],
          maxInterval: 366 * 24 * 3600 * 1000,
          axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.12)' } },
          axisTick: { show: false }, axisLabel: { color: '#64748b', fontSize: 11.5, formatter: fmtDate },
        },
        yAxis: {
          type: 'value', scale: true, name: '收益率 (%)',
          nameTextStyle: { color: '#64748b', fontSize: 11.5, padding: [0, 0, 0, -8] },
          axisLabel: { color: '#64748b', fontSize: 11.5 }, splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.09)', type: 'dashed' } },
        },
        dataZoom: [{ type: 'inside', xAxisIndex: 0, start: 0, end: 100, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false }],
        toolbox: {
          show: true, right: 0, top: 0, itemSize: 15,
          feature: { restore: { show: true, title: '还原视图', iconStyle: { borderColor: '#8ea0bd' }, emphasis: { iconStyle: { borderColor: '#e6edf7' } } } },
        },
        series,
      };
    }

    function bindChartClick() {
      const ch = state.chart;
      if (!ch) return;
      ch.off('click');
      let activeIndex = null;
      ch.on('click', (params) => {
        if (!params || params.componentType !== 'series') return;
        const idx = params.seriesIndex;
        if (activeIndex === idx) {
          ch.dispatchAction({ type: 'downplay' });
          activeIndex = null;
        } else {
          ch.dispatchAction({ type: 'downplay' });
          ch.dispatchAction({ type: 'highlight', seriesIndex: idx });
          activeIndex = idx;
        }
      });
    }

    function renderTreasury(d) {
      state.data = d;
      if (d.no_data) {
        state.statsHtml = '';
        state.dotCls = '';
        state.updateText = '无本地数据 · 请点击「获取最新数据」';
        return;
      }
      renderStats(d);
      if (typeof echarts === 'undefined') {
        state.dotCls = 'err';
        state.updateText = '图表库加载失败';
        return;
      }
      Vue.nextTick(() => {
        if (!state.chart) state.chart = echarts.init(chartEl.value);
        state.chart.setOption(buildOption(d), { notMerge: true });
        bindChartClick();
      });
      state.updateText = '数据截至 ' + (d.last_date || '—') + ' · ' + d.rows + ' 个交易日 · 更新于 ' + fmtUpdatedAt(d.updated_at);
      state.dotCls = 'ok';
    }

    async function loadTreasury() {
      try {
        const d = await api('/api/treasury/data');
        renderTreasury(d);
      } catch (err) {
        state.dotCls = 'err';
        state.updateText = '数据加载失败';
        toast('数据加载失败，请刷新页面重试', 'err');
      }
    }

    async function refresh() {
      if (state.refreshing) return;
      if (store.taskBusy) { toast('有任务正在运行，请稍候再试', 'err'); return; }
      store.taskBusy = true; store.taskName = '美债数据刷新';
      state.refreshing = true;
      state.dotCls = 'busy';
      state.updateText = '正在从 FRED 获取最新数据…';
      openModal('获取最新数据', '运行中', 'running');
      setModalBody('正在从 FRED 获取最新数据…\n\n首次获取需下载 2020 年至今全部数据；之后为增量获取，只取缺失的几天，通常几秒完成。');
      try {
        const d = await api('/api/treasury/refresh', { method: 'POST' });
        renderTreasury(d);
        const rm = d.refresh_meta || {};
        let head, detail;
        if (rm.mode === 'incremental' && rm.new_dates === 0) {
          head = '✓ 已是最新数据';
          detail = '数据截至 ' + d.last_date + '（FRED 尚未发布更新的交易日数据）\n共 ' + d.rows + ' 个交易日';
        } else if (rm.mode === 'incremental') {
          head = '✓ 增量更新完成';
          detail = '数据截至 ' + d.last_date + ' · 共 ' + d.rows + ' 个交易日\n本次新增 ' + rm.new_dates + ' 天数据';
        } else {
          head = '✓ 数据获取完成';
          detail = '数据截至 ' + d.last_date + ' · 共 ' + d.rows + ' 个交易日';
        }
        modalState.stateText = '✓ 完成';
        modalState.stateCls = 'done';
        setModalBody(head + '\n\n' + detail + '\n\n数据为美国交易日收盘值（美东时间），与北京时间存在时差，FRED 通常在美东交易日收盘后更新。');
        scheduleModalClose(3);
      } catch (err) {
        state.dotCls = 'err';
        if (state.data) state.updateText = '数据截至 ' + state.data.last_date + '（更新失败）';
        else state.updateText = '获取失败';
        modalState.stateText = '✕ 失败';
        modalState.stateCls = 'error';
        setModalBody('从 FRED 获取数据失败：\n\n' + err.message);
        keepModalOpen('任务失败，可关闭弹窗后重试（本地已缓存的数据不受影响）');
      } finally {
        store.taskBusy = false; store.taskName = null;
        state.refreshing = false;
      }
    }

    // 面板激活时才初始化/调整尺寸（v-show 常驻 DOM，保留图表状态）
    Vue.watch(isActive, (on) => {
      if (!on) return;
      if (!state.loaded) { state.loaded = true; loadTreasury(); }
      else if (state.chart) Vue.nextTick(() => state.chart.resize());
    });
    Vue.onMounted(() => { if (isActive.value && !state.loaded) { state.loaded = true; loadTreasury(); } });

    return {
      isActive, state, ICONS, refresh,
      // 模板中直接裸用这些状态名，必须在此暴露（toRef 保持响应式读写）：
      // 否则 updateText/dotCls/statsHtml 渲染为空、ref="chartEl" 拿不到 DOM，
      // echarts.init(null) 抛错导致走势图无法绘制。
      dotCls: Vue.toRef(state, 'dotCls'),
      updateText: Vue.toRef(state, 'updateText'),
      refreshing: Vue.toRef(state, 'refreshing'),
      statsHtml: Vue.toRef(state, 'statsHtml'),
      chartEl,
    };
  },
};

/* ============================================================
   二维码批量生成面板
   上传/生成（紧凑）→ 任务进度条 → 结果「每 3 个一组」翻页扫码
   ============================================================ */

const PER_PAGE = 3;   // 每组 3 个二维码

const QrcodePanel = {
  template: `
  <section class="panel" v-show="isActive">
    <div class="panel-head">
      <div>
        <h2>二维码批量生成</h2>
        <p class="panel-sub">读取 Excel「二维码编号」列，批量生成二维码并输出 HTML / Excel</p>
      </div>
    </div>

    <!-- ① 上传 + ② 运行（紧凑布局，高度约为原来的 1/2） -->
    <div class="qr-top">

      <div class="card qr-cell-card">
        <div class="card-title">
          <span class="step-badge">1</span>
          <span>上传 Excel 文件</span>
        </div>

        <div v-if="!file" class="dropzone dropzone-compact" tabindex="0"
             :class="{ dragover: dragOver }" @click="pickFile" @keydown.enter.prevent="pickFile"
             @keydown.space.prevent="pickFile" @dragover.prevent="dragOver = true"
             @dragenter.prevent="dragOver = true" @dragleave.prevent="dragOver = false"
             @drop.prevent="onDrop">
          <span class="dz-icon" v-html="ICONS.upload"></span>
          <span class="dz-line">
            <span class="dz-main">点击选择或拖拽 Excel</span>
            <span class="dz-sub">支持 .xlsx / .xls · 第一列列名须为「二维码编号」</span>
          </span>
        </div>

        <div v-else class="file-info file-info-compact">
          <span class="fi-icon" v-html="ICONS.file"></span>
          <div class="fi-text">
            <div class="fi-name">{{ file.name }}</div>
            <div class="fi-meta">{{ fileMeta }}</div>
          </div>
          <button class="fi-clear" type="button" title="移除文件" @click="clearFile">✕</button>
        </div>
        <input ref="fileInput" type="file" accept=".xlsx,.xls" hidden @change="onFileChange" />
      </div>

      <div class="card qr-cell-card">
        <div class="card-title">
          <span class="step-badge">2</span>
          <span>开始生成</span>
        </div>
        <div class="qr-run-row">
          <button class="btn btn-accent" type="button" :disabled="!canRun" @click="start">
            <span class="btn-icon" v-html="ICONS.refresh"></span>
            <span>{{ running ? '正在生成…' : '开始生成二维码' }}</span>
          </button>
          <div class="run-hint" :class="runHintCls" v-html="runHintHtml"></div>
        </div>
        <p class="card-tip card-tip-tiny">每次运行自动清理旧输出（HTML / Excel / 二维码缓存）<br/>生成期间可切换其他功能，任务在后台继续。</p>
      </div>
    </div>

    <!-- ③ 结果区：进度条 + 每 3 个一组翻页 -->
    <div class="card qr-card-wide qr-result-card" v-if="hasResult || running">
      <div class="card-title">
        <span class="step-badge">3</span>
        <span>生成结果</span>
        <div class="result-actions">
          <a v-for="o in (result ? result.outputs : [])" :key="o.name" class="btn btn-ghost btn-sm"
             :href="o.url" download>
            <span class="btn-icon" v-html="ICONS.download"></span>
            <span>下载 {{ o.kind === 'html' ? 'HTML' : 'Excel' }}</span>
          </a>
        </div>
      </div>

      <!-- 进度条（成组预览区上方） -->
      <div class="prog" v-if="running || progress > 0">
        <div class="prog-head">
          <span class="prog-label">{{ progressText }}</span>
          <span class="prog-num">{{ running ? Math.min(99, Math.round(progress)) : 100 }}%</span>
        </div>
        <div class="prog-track" role="progressbar" :aria-valuenow="running ? Math.round(progress) : 100">
          <div class="prog-bar" :class="{ running: running }"
               :style="{ width: (running ? Math.max(6, progress) : 100) + '%' }"></div>
        </div>
      </div>

      <div class="result-meta" v-if="showMeta">
        HTML 输出 <b>{{ result.html_name }}</b> · Excel 输出 <b>{{ result.xlsx_name }}</b>
      </div>

      <!-- 每 3 个一组 + 左右翻页按钮 -->
      <div v-if="hasResult" class="stage">
        <button class="pager-btn" type="button" title="上一组" :disabled="page <= 0" @click="pagePrev">
          <span v-html="ICONS.left"></span>
        </button>

        <transition name="qrpage" mode="out-in">
        <div class="qr-stage" :key="page">
          <div class="qr-item" v-for="it in currentChunk" :key="it.image">
            <img class="qr-img" :src="it.image" :alt="it.code" loading="lazy" />
            <div class="qr-code">{{ it.code }}</div>
          </div>
        </div>
        </transition>

        <button class="pager-btn" type="button" title="下一组" :disabled="page >= totalPages - 1" @click="pageNext">
          <span v-html="ICONS.right"></span>
        </button>
      </div>

      <div v-if="hasResult" class="page-indicator">
        第 {{ page + 1 }} / {{ totalPages }} 组 · 共 {{ result.count }} 个二维码
      </div>
      <div v-else-if="running" class="page-indicator">正在生成…</div>
      <div v-else-if="showEmpty" class="empty-state">
        <p class="empty-title">暂无生成结果</p>
        <p class="empty-desc">请先上传 Excel 并点击「开始生成二维码」。</p>
      </div>
    </div>
  </section>`,
  props: { active: { type: String, default: null } },
  setup(props) {
    const isActive = Vue.computed(() => props.active === 'qrcode');
    const fileInput = Vue.ref(null);
    const state = Vue.reactive({
      file: null, dragOver: false, pollTimer: null, taskId: null,
      running: false, runState: 'idle',   // idle | running | done | error
      progress: 0,                        // 生成任务进度 0-100
      progressText: '准备生成',
      hintText: '', hintCls: '',
      result: null, page: 0,
      statusChecked: false,
    });

    const PER = PER_PAGE;
    const hasResult = Vue.computed(() => !!(state.result && state.result.count > 0));
    const showMeta = Vue.computed(() => !!(state.result && state.result.html_name));
    const showEmpty = Vue.computed(() => !!state.result && !state.result.count);
    const totalPages = Vue.computed(() => state.result ? Math.max(1, Math.ceil(state.result.count / PER)) : 0);
    const currentChunk = Vue.computed(() => {
      if (!state.result) return [];
      const s = state.page * PER;
      return state.result.items.slice(s, s + PER);
    });
    const canRun = Vue.computed(() => !!state.file && !state.running);
    const runHintHtml = Vue.computed(() => state.hintText);
    const runHintCls = Vue.computed(() => state.hintCls);
    const fileMeta = Vue.computed(() => {
      if (!state.file) return '';
      return ((state.file.size || 0) / 1024).toFixed(1) + ' KB · ' + (state.file.modified || '刚刚上传');
    });
    const progressText = Vue.computed(() => state.progressText);

    function pickFile() { if (!state.running) fileInput.value.click(); }
    function onFileChange(e) {
      const f = e.target.files && e.target.files[0];
      e.target.value = '';
      if (f) uploadFile(f);
    }
    function onDrop(e) {
      state.dragOver = false;
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) uploadFile(f);
    }
    async function uploadFile(file) {
      if (!file) return;
      if (!/\.(xlsx|xls)$/i.test(file.name)) { toast('仅支持 .xlsx / .xls 文件', 'err'); return; }
      if (store.taskBusy) { toast('有任务正在运行，请稍候再上传', 'err'); return; }
      try {
        const buf = await file.arrayBuffer();
        const res = await fetch('/api/qrcode/upload?filename=' + encodeURIComponent(file.name), {
          method: 'POST', body: buf,
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || '上传失败');
        state.file = { name: body.filename, size: buf.byteLength, modified: null };
        state.hintText = '文件已就绪，点击「开始生成二维码」运行。';
        state.hintCls = '';
        toast('✓ Excel 已上传', 'ok');
      } catch (err) {
        toast('✕ ' + err.message, 'err');
      }
    }
    function clearFile() {
      state.file = null;
      state.hintText = '';
      state.hintCls = '';
    }

    function applyResult(r) {
      state.result = r || null;
      state.page = 0;
      if (r && r.count) {
        state.hintText = '✓ 生成完成：' + r.html_name + '（共 ' + r.count + ' 个，每 ' + PER + ' 个一组，可左右翻页）';
        state.hintCls = 'ok';
      }
    }

    // 由日志推断进度：生成脚本输出 [1/5]…[5/5] 分步标记
    function progressFromLog(log) {
      let last = 0;
      for (let i = log.length - 1; i >= 0; i--) {
        const m = log[i].match(/\[\s*(\d+)\s*\/\s*5\s*\]/);
        if (m) { last = Math.max(0, Math.min(5, parseInt(m[1], 10))); break; }
      }
      return last > 0 ? (last / 5) * 100 : 8;
    }

    async function start() {
      if (!state.file) { toast('请先上传 Excel 文件', 'err'); return; }
      if (state.running) return;
      if (store.taskBusy) { toast('有任务正在运行，请稍候再试', 'err'); return; }
      store.taskBusy = true; store.taskName = '二维码生成';
      state.running = true; state.runState = 'running';
      state.progress = 4; state.progressText = '任务启动中…';
      state.result = null; state.page = 0;
      state.hintText = '任务已在后台运行，完成后会提示；生成期间不会并发执行其他任务。';
      state.hintCls = '';
      try {
        const { task_id } = await api('/api/qrcode/run', { method: 'POST' });
        state.taskId = task_id;
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const t = await api('/api/qrcode/task/' + task_id);
          if (t.status === 'done') {
            state.progress = 100; state.progressText = '生成完成';
            state.running = false; state.runState = 'done';
            applyResult(t.result);
            toast('✓ 二维码生成完成（共 ' + (t.result && t.result.count) + ' 个）', 'ok');
            break;
          }
          if (t.status === 'error') {
            state.running = false; state.runState = 'error';
            state.hintText = '✕ 生成失败，请查看弹窗中的错误日志';
            state.hintCls = 'err';
            openModal('二维码生成失败', '✕ 失败', 'error');
            setModalBody((t.log || []).join('\n') || t.error || '未知错误');
            keepModalOpen('任务失败，可关闭弹窗后重试');
            toast('✕ 生成失败', 'err');
            break;
          }
          const p = progressFromLog(t.log || []);
          state.progress = Math.max(state.progress, p);
          state.progressText = '正在生成二维码…';
          await sleep(600);
        }
      } catch (err) {
        state.running = false; state.runState = 'error';
        state.hintText = '✕ 请求失败：' + err.message;
        state.hintCls = 'err';
        toast('✕ ' + err.message, 'err');
      } finally {
        store.taskBusy = false; store.taskName = null;
      }
    }

    function pagePrev() { if (state.page > 0) state.page -= 1; }
    function pageNext() { if (state.page < totalPages.value - 1) state.page += 1; }

    // 面板激活时同步一次状态（历史结果/已上传文件回显）
    async function refreshStatus() {
      try {
        const s = await api('/api/qrcode/status');
        if (s.input_files && s.input_files.length && !state.file) {
          const f = s.input_files[0];
          state.file = { name: f.name, size: f.size, modified: f.modified };
        } else if (!s.input_files || !s.input_files.length) {
          if (!state.file && !state.running) { state.hintText = 'input/ 目录为空：请先上传 Excel 文件。'; state.hintCls = ''; }
        }
        if (s.has_result && !state.result) {
          const r = await api('/api/qrcode/result');
          if (r && r.has_result) applyResult(r);
        }
      } catch (e) { /* 忽略 */ }
    }

    Vue.watch(isActive, (on) => {
      if (on && !state.statusChecked) { state.statusChecked = true; refreshStatus(); }
    });

    return {
      isActive, state, ICONS, fileInput, hasResult, showMeta, showEmpty, totalPages, currentChunk,
      canRun, runHintHtml, runHintCls, fileMeta, progressText,
      // 模板中直接裸用这些状态名，必须在此暴露（toRef 保持响应式读写）：
      // 否则上传后 file 不显示、running 恒为假 → 进度条与结果区永不出现、
      // result 为 undefined → 下载按钮 / 每 3 个一组扫码全部失效。
      file: Vue.toRef(state, 'file'),
      dragOver: Vue.toRef(state, 'dragOver'),
      running: Vue.toRef(state, 'running'),
      result: Vue.toRef(state, 'result'),
      progress: Vue.toRef(state, 'progress'),
      page: Vue.toRef(state, 'page'),
      pickFile, onFileChange, onDrop, clearFile, start, pagePrev, pageNext,
    };
  },
};

/* ============================================================
   根组件：顶栏 / 侧栏 / 面板容器
   ============================================================ */

const AppRoot = {
  template: `
  <div>
    <div class="bg-glow" aria-hidden="true"></div>

    <!-- 顶栏 -->
    <header class="topbar">
      <div class="brand">
        <div class="logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1"
               stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>
            <rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 14h7v7h-7z" fill="currentColor" stroke="none" opacity="0.9"/>
          </svg>
        </div>
        <div class="brand-text">
          <h1>{{ store.appName }}</h1>
          <p>{{ store.appSubtitle }}</p>
        </div>
      </div>
      <div class="topbar-right">
        <div class="task-indicator">
          <span class="status-dot" :class="taskDotCls"></span>
          <span>{{ store.taskBusy ? '运行中：' + store.taskName + '…' : '空闲 · 无任务运行' }}</span>
        </div>
      </div>
    </header>

    <div class="layout" :class="{ 'sidebar-collapsed': store.sidebarCollapsed }">
      <!-- 侧栏 -->
      <nav class="sidebar" aria-label="功能导航">
        <button class="sidebar-toggle" type="button" title="收起 / 展开侧栏" @click="toggleSidebar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"
               stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
        <div class="sidebar-head"><span class="sidebar-title">功能列表</span></div>
        <div class="feature-list">
          <button v-for="f in store.features" :key="f.id" type="button"
                  class="feature-btn" :class="{ active: store.active === f.id }" @click="store.active = f.id">
            <span class="fb-icon" v-html="iconOf(f)"></span>
            <span class="fb-name">{{ f.name }}</span>
          </button>
        </div>
        <div class="sidebar-icons">
          <button v-for="f in store.features" :key="'i' + f.id" type="button"
                  class="side-icon" :class="{ active: store.active === f.id }"
                  :title="f.name" :aria-label="f.name" @click="store.active = f.id">
            <span v-html="iconOf(f)"></span>
          </button>
        </div>
        <div class="sidebar-foot">功能按钮由 features.json 动态生成<br/>添加新功能只需改配置</div>
      </nav>

      <!-- 主内容（面板常驻 DOM，v-show 切换以保留图表/翻页状态） -->
      <main class="main">
        <treasury-panel :active="store.active"></treasury-panel>
        <qrcode-panel :active="store.active"></qrcode-panel>

        <section class="panel" v-show="isComing">
          <div class="coming">
            <div class="coming-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                   stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <h3>{{ coming.name || '即将上线' }}</h3>
            <p>{{ coming.desc || '该功能正在开发中。在 hub/features.json 中把对应条目改为 status: ready 并提供面板即可启用。' }}</p>
          </div>
        </section>
      </main>
    </div>

    <modal-box></modal-box>
    <toast-box></toast-box>
  </div>`,
  components: { TreasuryPanel, QrcodePanel, ModalBox, ToastBox },
  setup() {
    const coming = Vue.reactive({ name: '', desc: '' });
    const isComing = Vue.computed(() => {
      const f = store.features.find((x) => x.id === store.active);
      return !!store.active && f && f.id !== 'treasury' && f.id !== 'qrcode';
    });
    const taskDotCls = Vue.computed(() => store.taskBusy ? 'busy' : 'ok');
    function toggleSidebar() { store.sidebarCollapsed = !store.sidebarCollapsed; }
    function iconOf(f) { return ICONS[f.icon] || ICONS.plus; }

    async function init() {
      try {
        const cfg = await api('/api/apps');
        store.appName = cfg.app_name || 'Toolbox 工具台';
        store.appSubtitle = cfg.app_subtitle || '';
        store.features = (cfg.features || []).filter((f) => f.status === 'ready');
        store.active = store.features.length ? store.features[0].id : null;
        if (!store.active) toast('未发现已就绪的功能', 'err');
      } catch (err) {
        toast('功能配置加载失败：' + err.message, 'err');
      }
    }
    init();

    return { store, coming, isComing, taskDotCls, toggleSidebar, iconOf };
  },
};

/* ---------------- 启动 ---------------- */

Vue.createApp(AppRoot).mount('#app');
