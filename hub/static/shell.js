/* ============================================================
   Toolbox 工具台 · 宿主外壳（单页应用）
   ------------------------------------------------------------
   外壳只做四件事，不含任何业务逻辑：
     ① 读 /api/apps 拿到应用清单（来自各 apps/<id>/app.json）
     ② 渲染顶栏与侧栏功能按钮
     ③ 按需动态加载被点开的应用面板：/apps/<id>/panel.js + panel.css
     ④ 托管全局任务状态、弹窗与 Toast
   业务界面全部在应用自己的 frontend/panel.js 里；新增工具只需加一个目录。
   ============================================================ */

import { Vue } from './sdk/runtime.js';
import { api } from './sdk/api.js';
import { store, toast, ModalBox, ToastBox } from './sdk/ui.js';
import { ICONS } from './sdk/icons.js';

/* 已加载的面板：{ id, component }。
   面板常驻 DOM（各自用 v-show 控制显隐），因此切换工具不会丢失图表 / 翻页状态。 */
const loaded = Vue.reactive([]);
const state = Vue.reactive({ ready: false, loadingId: null, error: null });

/* 应用样式按需加载：某个工具第一次被打开时才拉它的 panel.css */
function ensureStyle(app) {
  if (!app.style || document.querySelector('link[data-app-style="' + app.id + '"]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = app.style;
  link.dataset.appStyle = app.id;
  document.head.appendChild(link);
}

/** 激活某个工具：第一次点开时才把它的面板模块拉下来并注册为组件。 */
async function activate(id) {
  store.active = id;
  if (loaded.some((panel) => panel.id === id)) { state.error = null; return; }

  const app = store.apps.find((item) => item.id === id);
  if (!app) { state.error = { id, message: '应用清单里没有这个工具' }; return; }

  state.error = null;
  state.loadingId = id;
  try {
    ensureStyle(app);
    const module = await import(app.panel);
    const component = module.default || module.Panel;
    if (!component) throw new Error('面板模块没有 export default 一个 Vue 组件');
    loaded.push({ id, component: Vue.markRaw(component) });
  } catch (err) {
    state.error = { id, message: err.message || String(err) };
  } finally {
    state.loadingId = null;
  }
}

/* ---------------- 根组件 ---------------- */

const AppRoot = {
  components: { ModalBox, ToastBox },
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
          <span class="status-dot" :class="store.taskBusy ? 'busy' : 'ok'"></span>
          <span>{{ store.taskBusy ? '运行中：' + store.taskName + '…' : '空闲 · 无任务运行' }}</span>
        </div>
      </div>
    </header>

    <div class="layout" :class="{ 'sidebar-collapsed': store.sidebarCollapsed }">
      <!-- 侧栏：功能按钮由 /api/apps 动态生成 -->
      <nav class="sidebar" aria-label="功能导航">
        <button class="sidebar-toggle" type="button" title="收起 / 展开侧栏" @click="toggleSidebar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"
               stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
        <div class="sidebar-head"><span class="sidebar-title">功能列表</span></div>
        <div class="feature-list">
          <button v-for="app in store.apps" :key="app.id" type="button"
                  class="feature-btn" :class="{ active: store.active === app.id }" @click="activate(app.id)">
            <span class="fb-icon" v-html="iconOf(app)"></span>
            <span class="fb-name">{{ app.name }}</span>
          </button>
        </div>
        <div class="sidebar-icons">
          <button v-for="app in store.apps" :key="'i' + app.id" type="button"
                  class="side-icon" :class="{ active: store.active === app.id }"
                  :title="app.name" :aria-label="app.name" @click="activate(app.id)">
            <span v-html="iconOf(app)"></span>
          </button>
        </div>
        <div class="sidebar-foot">功能按钮由 apps/*/app.json 自动生成<br/>新增工具只需加一个目录</div>
      </nav>

      <!-- 主内容区：已加载的面板常驻 DOM，各自用 v-show 控制显隐 -->
      <main class="main">
        <component v-for="panel in loaded" :key="panel.id" :is="panel.component"
                   :active="store.active"></component>

        <section class="panel-loading" v-if="state.loadingId">正在加载面板…</section>

        <section class="panel-error" v-if="state.error">
          <h3>面板加载失败</h3>
          <p>{{ state.error.message }}</p>
          <p>请确认 <code>apps/{{ state.error.id }}/frontend/</code> 下存在
             <code>app.json</code> 里声明的入口文件。</p>
          <button class="btn btn-accent btn-sm" type="button" @click="activate(state.error.id)">重新加载</button>
        </section>
      </main>
    </div>

    <modal-box></modal-box>
    <toast-box></toast-box>
  </div>`,
  setup() {
    function toggleSidebar() { store.sidebarCollapsed = !store.sidebarCollapsed; }
    function iconOf(app) { return ICONS[app.icon] || ICONS.plus; }

    async function init() {
      try {
        const cfg = await api('/api/apps');
        store.appName = cfg.app_name || store.appName;
        store.appSubtitle = cfg.app_subtitle || '';
        store.apps = cfg.apps || [];
        state.ready = true;
        if (store.apps.length) await activate(store.apps[0].id);
        else toast('未发现已启用的工具（检查 apps/*/app.json）', 'err');
      } catch (err) {
        state.ready = true;
        toast('应用清单加载失败：' + err.message, 'err');
      }
    }
    init();

    return { store, state, loaded, activate, toggleSidebar, iconOf };
  },
};

Vue.createApp(AppRoot).mount('#app');
