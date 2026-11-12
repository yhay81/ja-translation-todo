// router.js — History API ベースの小型SPAルータ
const routes = [];
let notFoundHandler = null;
let outlet = null;
let navigationController = null;
let renderedPath = null;

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

// 一覧の検索条件だけが変わるときは、表示中のページを保つ。
export function replaceSearch(search) {
  history.replaceState({}, "", location.pathname + (search ? `?${search}` : ""));
  renderedPath = location.pathname + location.search;
}

// SPA外として素通しするパス(Worker/静的ファイルが応答する)
const PASSTHROUGH = /^\/(api|feeds|mcp|openapi|llms|schema)(\/|$|\.)/;

export function start(mainElement) {
  outlet = mainElement;
  window.addEventListener("popstate", () => {
    if (renderedPath !== location.pathname + location.search) dispatch();
  });

  // 同一オリジンの内部リンクをSPA遷移に変換する
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = event.target.closest("a");
    if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
    const url = new URL(anchor.href, location.href);
    if (url.origin !== location.origin) return;
    if (url.hash && url.pathname === location.pathname && url.search === location.search) return;
    if (PASSTHROUGH.test(url.pathname) || /\.[a-z0-9]+$/i.test(url.pathname)) return;
    event.preventDefault();
    navigate(url.pathname + url.search + url.hash);
  });

  dispatch();
}

export async function dispatch() {
  renderedPath = location.pathname + location.search;
  navigationController?.abort();
  navigationController = new AbortController();
  const { signal } = navigationController;
  const segments = location.pathname.split("/").filter(Boolean);
  for (const r of routes) {
    if (r.segments.length !== segments.length) continue;
    const params = {};
    let matched = true;
    for (let i = 0; i < r.segments.length; i += 1) {
      const seg = r.segments[i];
      if (seg.startsWith(":")) {
        try {
          params[seg.slice(1)] = decodeURIComponent(segments[i]);
        } catch {
          matched = false;
          break;
        }
      } else if (seg !== segments[i]) {
        matched = false;
        break;
      }
    }
    if (!matched) continue;
    outlet.innerHTML = "";
    await r.handler(outlet, params, signal);
    return;
  }
  if (notFoundHandler) {
    outlet.innerHTML = "";
    await notFoundHandler(outlet, {}, signal);
  }
}
