/* ============================================================
   宿主 SDK · 请求与通用工具
   ============================================================ */

/** 统一的 JSON 请求封装：失败时抛出带后端 `error` 文案的 Error。 */
export async function api(url, opts) {
  const res = await fetch(url, opts);
  let body = null;
  try { body = await res.json(); } catch (e) { /* 非 JSON 响应（如静态文件） */ }
  if (!res.ok) throw new Error((body && body.error) || ('HTTP ' + res.status));
  return body;
}

/** 简单延时（轮询任务进度时用）。 */
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
