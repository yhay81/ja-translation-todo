// components/task-card.js — 一覧グリッド用のタスクカード
import { esc, KIND_LABELS, starsOf, fmtStars, difficultyBand } from "../labels.js";
import "./status-badge.js";
import "./automation-meter.js";

export function difficultyDotsHtml(difficulty) {
  const score = difficulty?.score;
  if (!score) return "";
  const band = difficultyBand(score);
  const dots = Array.from(
    { length: 5 },
    (_, i) => `<i class="${i < score ? "on" : ""}"></i>`,
  ).join("");
  return (
    `<span class="difficulty-dots band-${band}" title="難易度 ${score}/5" ` +
    `aria-label="難易度 ${score}/5">${dots}</span>`
  );
}

class TaskCard extends HTMLElement {
  set task(bundle) {
    this._task = bundle;
    this.render();
  }

  render() {
    const t = this._task;
    if (!t) return;
    const stars = fmtStars(starsOf(t));
    const category = t.project?.category;
    this.innerHTML = `
      <a class="task-card" href="/tasks/${encodeURIComponent(t.id)}">
        <div class="card-topline">
          <tt-status-badge status="${esc(t.status)}"></tt-status-badge>
          <span class="chip neutral">${esc(KIND_LABELS[t.kind] || t.kind)}</span>
        </div>
        <p class="card-repo">${esc(t.project?.repository || "")}</p>
        <h3>${esc(t.title?.ja || t.title?.en || t.id)}</h3>
        <p class="card-summary">${esc(t.project?.summary_ja || "")}</p>
        <div class="card-meta">
          ${category ? `<span>${esc(category)}</span>` : ""}
          ${difficultyDotsHtml(t.difficulty)}
          ${stars ? `<span title="GitHub stars">★ ${esc(stars)}</span>` : ""}
          <tt-automation-meter level="${esc(t.automation?.level || "")}"></tt-automation-meter>
        </div>
      </a>`;
  }
}

customElements.define("tt-task-card", TaskCard);
