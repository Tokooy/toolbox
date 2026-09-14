/* ============================================================
   美债收益率看板 · 前端面板
   由工具台外壳（hub）按需动态加载：/apps/treasury/panel.js -> export default 一个 Vue 组件
   独立运行时（apps/treasury/standalone.py）加载的是同一个文件，因此这里不依赖任何 hub 专有代码。
   ============================================================ */

import { Vue, echarts } from '/static/sdk/runtime.js';
import { api } from '/static/sdk/api.js';
import { store, toast, openModal, setModalBody, scheduleModalClose, keepModalOpen, modalState } from '/static/sdk/ui.js';
import { ICONS } from '/static/sdk/icons.js';

/* ============================================================
   美债收益率面板（ECharts，逻辑与原实现一致）
   ============================================================ */

const SERIES_META = {
  DGS2:  { label: '2 年期',  color: '#fbbf24' },
  DGS10: { label: '10 年期', color: '#38bdf8' },
  DGS30: { label: '30 年期', color: '#a78bfa' },
};
const SPREAD_COLOR = '#f472b6';

export default {
  name: 'treasury-panel',
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
