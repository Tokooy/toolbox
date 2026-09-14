/* ============================================================
   二维码批量生成 · 前端面板
   由工具台外壳（hub）按需动态加载：/apps/qrcode/panel.js -> export default 一个 Vue 组件
   ============================================================ */

import { Vue } from '/static/sdk/runtime.js';
import { api, sleep } from '/static/sdk/api.js';
import { store, toast, openModal, setModalBody, keepModalOpen } from '/static/sdk/ui.js';
import { ICONS } from '/static/sdk/icons.js';

const PER_PAGE = 3;   // 每组 3 个二维码

/* ============================================================
   二维码批量生成面板
   上传/生成（紧凑）→ 任务进度条 → 结果「每 3 个一组」翻页扫码
   ============================================================ */

export default {
  name: 'qrcode-panel',
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
            // 日志非空时错误信息会被淹没，这里把 t.error 一并追加，保证失败原因始终可见
            const lines = (t.log || []).slice();
            if (t.error) lines.push('', '✕ ' + t.error);
            setModalBody(lines.join('\n') || '未知错误');
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
