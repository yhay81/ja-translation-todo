// components/evidence-timeline.js — evidence を observed_at 降順で並べるタイムライン
import { esc, fmtDate } from "../labels.js";

// evidence.kind → タイムライン上の記号(絵文字は使わない)
const KIND_GLYPHS = {
  issue: "!",
  pull_request: "⇅",
  pr: "⇅",
  commit: "#",
  readme: "¶",
  document: "¶",
  doc: "¶",
  discussion: "◇",
  release: "◆",
  policy: "§",
  web: "→",
  page: "→",
};

class EvidenceTimeline extends HTMLElement {
  set evidence(list) {
    this._list = Array.isArray(list) ? list : [];
    this.render();
  }

  render() {
    const sorted = [...this._list].sort(
      (a, b) => new Date(b.observed_at || 0) - new Date(a.observed_at || 0),
    );
    if (sorted.length === 0) {
      this.innerHTML = '<p class="empty-state">証拠は登録されていません。</p>';
      return;
    }
    this.innerHTML = `<ol class="evidence-list">${sorted
      .map((ev) => {
        const glyph = KIND_GLYPHS[ev.kind] || "•";
        return `
          <li class="evidence-item" data-glyph="${esc(glyph)}">
            <div class="evidence-head">
              <span class="chip neutral">${esc(ev.kind || "evidence")}</span>
              <time datetime="${esc(ev.observed_at || "")}">${esc(fmtDate(ev.observed_at))}</time>
            </div>
            ${ev.note_ja ? `<p>${esc(ev.note_ja)}</p>` : ""}
            ${
              ev.url
                ? `<a class="evidence-url" href="${esc(ev.url)}" target="_blank" rel="noopener noreferrer">${esc(ev.url)}</a>`
                : ""
            }
          </li>`;
      })
      .join("")}</ol>`;
  }
}

customElements.define("tt-evidence-timeline", EvidenceTimeline);
