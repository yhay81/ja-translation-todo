// components/bar-chart.js — 依存なしSVG手書きの横棒グラフ
import { esc } from "../labels.js";

const ROW_HEIGHT = 30;
const LABEL_WIDTH = 130;
const VALUE_WIDTH = 44;
const CHART_WIDTH = 520;

class BarChart extends HTMLElement {
  // rows: [{label, value, color?}]  color は CSS変数可
  set data(rows) {
    this._rows = Array.isArray(rows) ? rows : [];
    this.render();
  }

  render() {
    const rows = this._rows;
    if (rows.length === 0) {
      this.innerHTML = '<p class="empty-state">データがありません。</p>';
      return;
    }
    const max = Math.max(1, ...rows.map((r) => r.value || 0));
    const barSpan = CHART_WIDTH - LABEL_WIDTH - VALUE_WIDTH - 12;
    const height = rows.length * ROW_HEIGHT + 6;
    const chartLabel = this.getAttribute("label") || "棒グラフ";
    const desc = rows.map((r) => `${r.label}: ${r.value}`).join("、");

    const body = rows
      .map((row, i) => {
        const y = i * ROW_HEIGHT + 4;
        const value = row.value || 0;
        const w = Math.max(2, Math.round((barSpan * value) / max));
        const color = row.color || "var(--chart-1)";
        return `
          <text x="${LABEL_WIDTH - 8}" y="${y + 15}" text-anchor="end" class="chart-label">${esc(row.label)}</text>
          <rect x="${LABEL_WIDTH}" y="${y}" width="${barSpan}" height="20" rx="5" class="chart-track"></rect>
          <rect x="${LABEL_WIDTH}" y="${y}" width="${w}" height="20" rx="5" style="fill:${esc(color)}"></rect>
          <text x="${LABEL_WIDTH + w + 8}" y="${y + 15}" class="chart-value">${value}</text>`;
      })
      .join("");

    this.innerHTML = `
      <svg viewBox="0 0 ${CHART_WIDTH} ${height}" role="img"
        aria-label="${esc(chartLabel)}: ${esc(desc)}" preserveAspectRatio="xMinYMin meet">
        ${body}
      </svg>`;
  }
}

customElements.define("tt-bar-chart", BarChart);
