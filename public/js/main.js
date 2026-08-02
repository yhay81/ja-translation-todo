// main.js — 起動処理(テーマ・ヘッダ/フッタ・ルーティング)
import { route, setNotFound, start } from "./router.js";
import { getStats } from "./store.js";
import { renderList } from "./pages/list.js";
import { renderTaskDetail } from "./pages/task-detail.js";
import { renderStats } from "./pages/stats.js";
import { renderAbout } from "./pages/about.js";
import { renderNotFound } from "./pages/not-found.js";

// ---- テーマ切替(auto/light/dark、localStorage保存) ----
const THEME_KEY = "tt:theme";
const THEME_CYCLE = ["auto", "light", "dark"];
const THEME_LABELS = { auto: "テーマ: 自動", light: "テーマ: ライト", dark: "テーマ: ダーク" };

function currentTheme() {
  try {
    const t = localStorage.getItem(THEME_KEY);
    return THEME_CYCLE.includes(t) ? t : "auto";
  } catch {
    return "auto";
  }
}

function applyTheme(theme) {
  if (theme === "auto") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = theme;
  }
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* 保存できなくても動作は継続 */
  }
}

// ---- ヘッダ ----
function renderHeader() {
  const header = document.getElementById("site-header");
  header.innerHTML = `
    <div class="header-inner container">
      <a class="brand" href="/">ja-translation-todo</a>
      <nav class="site-nav" aria-label="サイト内ナビゲーション">
        <a href="/" data-nav="/">タスク一覧</a>
        <a href="/stats" data-nav="/stats">統計</a>
        <a href="/about" data-nav="/about">使い方</a>
      </nav>
      <div class="header-actions">
        <button type="button" class="icon-button" id="theme-toggle"></button>
        <a class="header-repo-link" href="https://github.com/yhay81/ja-translation-todo" target="_blank" rel="noopener noreferrer">GitHub</a>
      </div>
    </div>`;

  const toggle = header.querySelector("#theme-toggle");
  const syncToggle = () => {
    toggle.textContent = THEME_LABELS[currentTheme()];
  };
  toggle.addEventListener("click", () => {
    const next =
      THEME_CYCLE[(THEME_CYCLE.indexOf(currentTheme()) + 1) % THEME_CYCLE.length];
    applyTheme(next);
    syncToggle();
  });
  syncToggle();
}

// ---- 現在ページのナビ強調 ----
function syncNavCurrent() {
  for (const link of document.querySelectorAll("[data-nav]")) {
    const isCurrent =
      link.dataset.nav === "/"
        ? location.pathname === "/" || location.pathname.startsWith("/tasks/")
        : location.pathname.startsWith(link.dataset.nav);
    if (isCurrent) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

// ---- フッタ ----
function renderFooter() {
  const footer = document.getElementById("site-footer");
  footer.innerHTML = `
    <div class="container footer-inner">
      <p class="footer-revision" id="footer-revision">ja-translation-todo</p>
      <nav aria-label="関連リンク">
        <a href="https://github.com/yhay81/ja-translation-todo" target="_blank" rel="noopener noreferrer">GitHub</a>
        <a href="/openapi.json">OpenAPI</a>
        <a href="/llms.txt">llms.txt</a>
        <a href="/feeds/tasks.atom">タスクAtom</a>
      </nav>
    </div>`;
  getStats()
    .then((stats) => {
      if (stats?.catalog_revision) {
        footer.querySelector("#footer-revision").textContent =
          `catalog_revision: ${stats.catalog_revision}`;
      }
    })
    .catch(() => {});
}

// ---- ルーティング ----
function wrap(handler) {
  return async (outlet, params) => {
    await handler(outlet, params);
    syncNavCurrent();
  };
}

route("/", wrap(renderList));
route("/tasks/:id", wrap(renderTaskDetail));
route("/stats", wrap(renderStats));
route("/about", wrap(renderAbout));
setNotFound(wrap(renderNotFound));

renderHeader();
renderFooter();
start(document.getElementById("main"));
