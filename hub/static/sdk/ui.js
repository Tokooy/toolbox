/* ============================================================
   宿主 SDK · 全局状态 / Toast / 弹窗
   ------------------------------------------------------------
   应用面板通过这里与外壳交互（不要自己实现第二套通知组件）：
     import { store, toast, openModal, setModalBody, closeModal,
              scheduleModalClose, keepModalOpen } from '/static/sdk/ui.js';
   ============================================================ */

import { Vue } from './runtime.js';
import { ICONS } from './icons.js';

/* ---------------- 全局状态（轻量 store） ---------------- */

export const store = Vue.reactive({
  appName: 'Toolbox 工具台',
  appSubtitle: '',
  apps: [],              // 应用清单（来自 /api/apps，由 apps/*/app.json 汇总而来）
  active: null,          // 当前激活的应用 id
  sidebarCollapsed: false,
  taskBusy: false,       // 全局任务互斥标记（同一时刻只跑一个重任务）
  taskName: null,
});

/* ---------------- Toast ---------------- */

const toastState = Vue.reactive({ visible: false, text: '', kind: '' });
let _toastTimer = null;

export function toast(text, kind) {
  toastState.text = text;
  toastState.kind = kind || '';
  toastState.visible = true;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { toastState.visible = false; }, 3600);
}

/* ---------------- 弹窗（任务日志 / 结果提示） ---------------- */

export const modalState = Vue.reactive({
  visible: false, title: '提示', stateText: '', stateCls: '',
  body: '', foot: '', countdown: null, _timer: null,
});

export function openModal(title, stateText, stateCls) {
  modalState.title = title || '提示';
  modalState.stateText = stateText || '';
  modalState.stateCls = stateCls || '';
  modalState.body = '';
  modalState.foot = '';
  modalState.visible = true;
  modalState.countdown = null;
  clearInterval(modalState._timer);
}

export function closeModal() {
  modalState.visible = false;
  clearInterval(modalState._timer);
  modalState.countdown = null;
}

export function setModalBody(text) { modalState.body = text; }

/** N 秒后自动关闭（成功提示用）。 */
export function scheduleModalClose(seconds) {
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

/** 取消自动关闭并显示提示语（失败提示用，让用户看清原因）。 */
export function keepModalOpen(message) {
  clearInterval(modalState._timer);
  modalState.foot = message || '';
  modalState.countdown = null;
}

/* ---------------- 通用组件（外壳与独立运行页面共用） ---------------- */

export const ModalBox = {
  template: `
  <transition name="fade">
  <div class="modal-mask" v-if="modalState.visible" @click.self="closeModal">
    <div class="modal" role="dialog">
      <div class="modal-head">
        <div class="modal-title">
          <span class="modal-icon" aria-hidden="true" v-html="ICONS.alert"></span>
          <span>{{ modalState.title }}</span>
          <span class="log-state" :class="modalState.stateCls">{{ modalState.stateText }}</span>
        </div>
        <button class="modal-close" type="button" title="关闭" @click="closeModal">✕</button>
      </div>
      <pre class="log">{{ modalState.body }}</pre>
      <div class="modal-foot"><span v-if="modalState.countdown != null" class="modal-countdown">{{ modalState.countdown }} 秒后自动关闭</span><span v-else>{{ modalState.foot }}</span></div>
    </div>
  </div>
  </transition>`,
  setup() {
    return { modalState, closeModal, ICONS };
  },
};

export const ToastBox = {
  template: `
  <div class="toast" :class="[toastState.visible ? 'show' : '', toastState.kind]" role="status">{{ toastState.text }}</div>`,
  setup() {
    return { toastState };
  },
};
