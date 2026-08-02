// pages/list.js — タスク一覧ページ(フィルタ状態⇔URL 双方向同期)
import { api, toastError } from "../api.js";
import { getStats } from "../store.js";
import { toast } from "../components/toast.js";
import { esc } from "../labels.js";
import "../components/task-card.js";
import "../components/filter-bar.js";
import "../components/pager.js";

const PER_PAGE = 24;
const MCP_URL = "https://ja.yhay81.com/mcp";
const FILTER_KEYS = ["q", "status", "kind", "category", "difficulty", "platform", "sort"];

function readParams() {
  const sp = new URLSearchParams(location.search);
  const values = {};
  for (const key of [...FILTER_KEYS, "page"]) {
    const v = sp.get(key);
    if (v) values[key] = v;
  }
  return values;
}

function writeParams(values) {
  const sp = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    if (values[key]) sp.set(key, values[key]);
  }
  if (values.page && Number(values.page) > 1) sp.set("page", values.page);
  const query = sp.toString();
  history.replaceState({}, "", query ? `/?${query}` : "/");
}

export async function renderList(outlet) {
  document.title = "タスク一覧 — ja-translation-todo";
  outlet.innerHTML = `
    <section class="hero">
      <div>
        <h1>ja-translation-todo</h1>
        <p class="hero-copy">OSSの日本語化タスクを、人間とAIエージェントが安全に発見・検証・実行するための公開レジストリ。</p>
      </div>
      <div class="hero-actions">
        <button type="button" class="button" id="copy-mcp">MCP URLをコピー</button>
        <a class="button" href="/feeds/tasks.atom">Atomフィード</a>
      </div>
    </section>
    <tt-filter-bar></tt-filter-bar>
    <div class="result-line">
      <span id="result-count" aria-live="polite">読み込み中…</span>
      <span class="revision" id="result-revision"></span>
    </div>
    <div class="task-grid" id="task-grid"></div>
    <tt-pager></tt-pager>`;

  outlet.querySelector("#copy-mcp").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(MCP_URL);
      toast("MCP URLをコピーしました", "success");
    } catch {
      toast(`コピーできませんでした: ${MCP_URL}`, "error");
    }
  });

  const filterBar = outlet.querySelector("tt-filter-bar");
  const pager = outlet.querySelector("tt-pager");
  const grid = outlet.querySelector("#task-grid");
  const countEl = outlet.querySelector("#result-count");
  const revisionEl = outlet.querySelector("#result-revision");

  filterBar.values = readParams();
  getStats()
    .then((stats) => {
      filterBar.categories = Object.keys(stats.by_category || {}).sort();
      // カテゴリ選択肢の読み込み後にURLの値を再適用する
      filterBar.values = readParams();
    })
    .catch(() => {});

  let requestSeq = 0;

  async function load() {
    const params = readParams();
    const page = Math.max(1, Number(params.page) || 1);
    const sp = new URLSearchParams();
    for (const key of FILTER_KEYS) {
      if (params[key]) sp.set(key, params[key]);
    }
    sp.set("limit", String(PER_PAGE));
    if (page > 1) sp.set("cursor", String((page - 1) * PER_PAGE));

    const seq = ++requestSeq;
    countEl.textContent = "読み込み中…";
    try {
      const data = await api(`/api/v2/tasks?${sp.toString()}`);
      if (seq !== requestSeq) return; // 古いレスポンスは破棄
      const items = data.items || [];
      const total = data.total ?? items.length;

      grid.innerHTML = "";
      for (const bundle of items) {
        const card = document.createElement("tt-task-card");
        card.task = bundle;
        grid.appendChild(card);
      }
      if (items.length === 0) {
        grid.innerHTML = '<p class="empty-state">条件に一致するタスクがありません。</p>';
      }

      const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
      const to = (page - 1) * PER_PAGE + items.length;
      countEl.textContent =
        total === 0 ? "0件" : `全${total}件中 ${from}–${to}件を表示`;
      revisionEl.textContent = data.catalog_revision
        ? `catalog_revision: ${data.catalog_revision}`
        : "";
      pager.update({ page, total, perPage: PER_PAGE });
    } catch (err) {
      if (seq !== requestSeq) return;
      countEl.textContent = "読み込みに失敗しました";
      grid.innerHTML = `<p class="error-state">タスク一覧を取得できませんでした: ${esc(err.message)}</p>`;
      toastError(err);
    }
  }

  filterBar.addEventListener("filter-change", (event) => {
    writeParams({ ...event.detail }); // フィルタ変更時は1ページ目に戻す
    load();
  });

  pager.addEventListener("page-change", (event) => {
    writeParams({ ...readParams(), page: String(event.detail.page) });
    window.scrollTo({ top: 0 });
    load();
  });

  await load();
}
