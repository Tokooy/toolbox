import { Vue } from '/static/sdk/runtime.js';

export default {
  props: ['active'],
  setup(props) {
    const workspace = new URL('./workspace/', import.meta.url).pathname;
    return () => Vue.withDirectives(
      Vue.h('iframe', {
        class: 'agora-workspace',
        src: workspace,
        title: '共识 Agora · 多 Agent 研讨',
      }),
      [[Vue.vShow, props.active === 'agora']],
    );
  },
};
