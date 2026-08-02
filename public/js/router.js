// router.js — History API ベースの小型SPAルータ
const routes = [];
let notFoundHandler = null;
let outlet = null;

// pattern 例: "/", "/tasks/:id"
export function route(pattern, handler) {
  routes.push({ segments: pattern.split("/").filter(Boolean), handler });
}

export function setNotFound(handler) {
  notFoundHandler = handler;
}

export function navigate(url, { replace = false } = {}) {
  if (replace) {
    history.replaceState({}, "", url);
  } else {
    history.pushState({}, "", url);
  }
  window.scrollTo(0, 0);
  dispatch();
}

// SPA外として素通しするパス(Worker/静的ファイルが応答する)
const PASSTHROUGH = /^\/(api|feeds|mcp|openapi|llms|schema)(\/|$|\.)/;

export function start(mainElement) {
  outlet = mainElement;
  window.addEventListener("popstate", () => dispatch());

  // 同一オリジンの内部リンクをSPA遷移に変換する
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = event.target.closest("a");
    if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
    const url = new URL(anchor.href, location.href);
    if (url.origin !== location.origin) return;
    if (PASSTHROUGH.test(url.pathname) || /\.[a-z0-9]+$/i.test(url.pathname)) return;
    event.preventDefault();
    navigate(url.pathname + url.search + url.hash);
  });

  dispatch();
}

export async function dispatch() {
  const segments = location.pathname.split("/").filter(Boolean);
  for (const r of routes) {
    if (r.segments.length !== segments.length) continue;
    const params = {};
    let matched = true;
    for (let i = 0; i < r.segments.length; i += 1) {
      const seg = r.segments[i];
      if (seg.startsWith(":")) {
        params[seg.slice(1)] = decodeURIComponent(segments[i]);
      } else if (seg !== segments[i]) {
        matched = false;
        break;
      }
    }
    if (!matched) continue;
    outlet.innerHTML = "";
    await r.handler(outlet, params);
    return;
  }
  if (notFoundHandler) {
    outlet.innerHTML = "";
    await notFoundHandler(outlet, {});
  }
}
