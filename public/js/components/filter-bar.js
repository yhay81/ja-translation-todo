// components/filter-bar.js — 一覧ページの検索・絞り込みバー
import {
  STATUS_LABELS,
  STATUS_ORDER,
  KIND_LABELS,
  PLATFORM_LABELS,
  SORT_LABELS,
  DIFFICULTY_BAND_LABELS,
  esc,
} from "../labels.js";

const DEBOUNCE_MS = 180;

function options(map, keys) {
  return keys.map((k) => `<option value="${esc(k)}">${esc(map[k])}</option>`).join("");
}

class FilterBar extends HTMLElement {
  connectedCallback() {
    if (this._rendered) return;
    this._rendered = true;
    this.innerHTML = `
      <form class="filter-bar" role="search" aria-label="タスクの絞り込み">
        <input name="q" type="search" placeholder="repository・キーワードで検索" aria-label="キーワード検索" autocomplete="off">
        <select name="status" aria-label="状態で絞り込み">
          <option value="">状態: すべて</option>
          ${options(STATUS_LABELS, STATUS_ORDER)}
        </select>
        <select name="kind" aria-label="種類で絞り込み">
          <option value="">種類: すべて</option>
          ${options(KIND_LABELS, Object.keys(KIND_LABELS))}
        </select>
        <select name="category" aria-label="カテゴリで絞り込み">
          <option value="">カテゴリ: すべて</option>
        </select>
        <select name="difficulty" aria-label="難易度で絞り込み">
          <option value="">難易度: すべて</option>
          ${options(DIFFICULTY_BAND_LABELS, ["easy", "medium", "hard"])}
        </select>
        <select name="platform" aria-label="プラットフォームで絞り込み">
          <option value="">Platform: すべて</option>
          ${options(PLATFORM_LABELS, Object.keys(PLATFORM_LABELS))}
        </select>
        <select name="sort" aria-label="並び順">
          ${options(SORT_LABELS, Object.keys(SORT_LABELS))}
        </select>
      </form>`;

    const form = this.querySelector("form");
    form.addEventListener("submit", (e) => e.preventDefault());
    form.q.addEventListener("input", () => {
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this.emit(), DEBOUNCE_MS);
    });
    form.addEventListener("change", (e) => {
      if (e.target.tagName === "SELECT") this.emit();
    });
    if (this._pendingValues) this.values = this._pendingValues;
    if (this._pendingCategories) this.categories = this._pendingCategories;
  }

  // URLSearchParams 由来の値をフォームへ反映する
  set values(v) {
    if (!this._rendered) {
      this._pendingValues = v;
      return;
    }
    const form = this.querySelector("form");
    for (const name of ["q", "status", "kind", "category", "difficulty", "platform", "sort"]) {
      form.elements[name].value = v?.[name] || (name === "sort" ? "updated" : "");
    }
  }

  // /api/v2/stats の by_category からカテゴリ選択肢を生成する
  set categories(list) {
    if (!this._rendered) {
      this._pendingCategories = list;
      return;
    }
    const select = this.querySelector('select[name="category"]');
    const current = select.value;
    select.innerHTML =
      '<option value="">カテゴリ: すべて</option>' +
      (list || []).map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    select.value = current;
  }

  read() {
    const form = this.querySelector("form");
    const result = {};
    for (const name of ["q", "status", "kind", "category", "difficulty", "platform", "sort"]) {
      const value = form.elements[name].value.trim();
      if (value) result[name] = value;
    }
    return result;
  }

  emit() {
    this.dispatchEvent(new CustomEvent("filter-change", { detail: this.read() }));
  }
}

customElements.define("tt-filter-bar", FilterBar);
