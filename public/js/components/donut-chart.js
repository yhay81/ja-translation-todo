// components/donut-chart.js — 依存なしSVG手書きのドーナツチャート+凡例
import { esc } from "../labels.js";

const RADIUS = 54;
const STROKE = 22;
const SIZE = (RADIUS + STROKE) * 2;

class DonutChart extends HTMLElement {
  // rows: [{label, value, color}]  color は CSS変数可
  set data(rows) {
    this._rows = (Array.isArray(rows) ? rows : []).filter((r) => (r.value || 0) > 0);
    this.render();
  }

  render() {
    const rows = this._rows;
    if (rows.length === 0) {
      this.innerHTML = '<p class="empty-state">データがありません。</p>';
      return;
    }
    const total = rows.reduce((sum, r) => sum + r.value, 0);
    const circumference = 2 * Math.PI * RADIUS;
    const center = SIZE / 2;
    const chartLabel = this.getAttribute("label") || "ドーナツチャート";
    const desc = rows.map((r) => `${r.label}: ${r.value}`).join("、");

    let offset = 0;
    const segments = rows
      .map((row) => {
        const fraction = row.value / total;
        const dash = fraction * circumference;
        // 12時位置から時計回りに描く(rotate -90)
        const seg = `<circle cx="${center}" cy="${center}" r="${RADIUS}" fill="none"
          stroke="${esc(row.color || "var(--chart-1)")}" stroke-width="${STROKE}"
          stroke-dasharray="${dash.toFixed(2)} ${(circumference - dash).toFixed(2)}"
          stroke-dashoffset="${(-offset).toFixed(2)}"
          transform="rotate(-90 ${center} ${center})"></circle>`;
        offset += dash;
        return seg;
      })
      .join("");

    const legend = rows
      .map(
        (row) => `
          <li>
            <span class="swatch" style="background:${esc(row.color || "var(--chart-1)")}"></span>
            <span>${esc(row.label)}</span>
            <span class="legend-value">${row.value}</span>
          </li>`,
      )
      .join("");

    this.innerHTML = `
      <div class="donut-wrap">
        <svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${esc(chartLabel)}: ${esc(desc)}">
          ${segments}
          <text x="${center}" y="${center - 2}" text-anchor="middle" class="donut-center">${total}</text>
          <text x="${center}" y="${center + 16}" text-anchor="middle" class="donut-center-sub">合計</text>
        </svg>
        <ul class="chart-legend">${legend}</ul>
      </div>`;
  }
}

customElements.define("tt-donut-chart", DonutChart);
