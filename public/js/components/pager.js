// components/pager.js — 前へ/次へのページ送り
class Pager extends HTMLElement {
  // state: { page(1始まり), total, perPage }
  update({ page, total, perPage }) {
    const totalPages = Math.max(1, Math.ceil(total / perPage));
    this._page = Math.min(Math.max(1, page), totalPages);
    if (totalPages <= 1) {
      this.innerHTML = "";
      this.hidden = true;
      return;
    }
    this.hidden = false;
    this.innerHTML = `
      <button type="button" class="button small" data-dir="-1" ${this._page <= 1 ? "disabled" : ""}>前へ</button>
      <span class="pager-status" aria-live="polite">${this._page} / ${totalPages} ページ</span>
      <button type="button" class="button small" data-dir="1" ${this._page >= totalPages ? "disabled" : ""}>次へ</button>`;
    for (const button of this.querySelectorAll("button")) {
      button.addEventListener("click", () => {
        const next = this._page + Number(button.dataset.dir);
        this.dispatchEvent(new CustomEvent("page-change", { detail: { page: next } }));
      });
    }
  }
}

customElements.define("tt-pager", Pager);
