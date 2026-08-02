// pages/stats.js — 統計ページ(メトリクスカード+SVGチャート)
import { toastError } from "../api.js";
import { getStats } from "../store.js";
import {
  esc,
  STATUS_LABELS,
  STATUS_ORDER,
  AUTOMATION_LABELS,
} from "../labels.js";
import "../components/bar-chart.js";
import "../components/donut-chart.js";

const STATUS_BAR_COLORS = {
  ready: "var(--status-ready-fg)",
  needs_verification: "var(--status-needs_verification-fg)",
  ask_first: "var(--status-ask_first-fg)",
  in_progress: "var(--status-in_progress-fg)",
  blocked: "var(--status-blocked-fg)",
  done: "var(--status-done-fg)",
  stale: "var(--status-stale-fg)",
};

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-8)",
];

export async function renderStats(outlet) {
  document.title = "統計 — ja-translation-todo";
  outlet.innerHTML = '<p class="page-loading">読み込み中…</p>';

  let stats;
  try {
    stats = await getStats(true);
  } catch (err) {
    outlet.innerHTML = `<p class="error-state">統計を取得できませんでした: ${esc(err.message)}</p>`;
    toastError(err);
    return;
  }

  const byStatus = stats.by_status || {};
  outlet.innerHTML = `
    <h1>統計</h1>
    <p class="hero-copy">catalog_revision: <code>${esc(stats.catalog_revision || "—")}</code></p>
    <div class="metric-cards">
      <div class="metric-card"><strong>${stats.total ?? 0}</strong><span>登録タスク</span></div>
      <div class="metric-card"><strong>${byStatus.ready ?? 0}</strong><span>着手可能</span></div>
      <div class="metric-card"><strong>${stats.verified ?? 0}</strong><span>検証済み</span></div>
      <div class="metric-card"><strong>${byStatus.needs_verification ?? 0}</strong><span>再検証待ち</span></div>
    </div>
    <div class="stats-grid">
      <section class="panel">
        <h2>状態別</h2>
        <tt-bar-chart id="chart-status" label="状態別タスク数"></tt-bar-chart>
      </section>
      <section class="panel">
        <h2>カテゴリ別</h2>
        <tt-bar-chart id="chart-category" label="カテゴリ別タスク数"></tt-bar-chart>
      </section>
      <section class="panel">
        <h2>難易度別</h2>
        <tt-bar-chart id="chart-difficulty" label="難易度別タスク数"></tt-bar-chart>
      </section>
      <section class="panel">
        <h2>自動化レベル別</h2>
        <tt-donut-chart id="chart-automation" label="自動化レベル別タスク数"></tt-donut-chart>
      </section>
    </div>`;

  outlet.querySelector("#chart-status").data = STATUS_ORDER.filter(
    (s) => byStatus[s] != null,
  ).map((s) => ({
    label: STATUS_LABELS[s],
    value: byStatus[s] || 0,
    color: STATUS_BAR_COLORS[s],
  }));

  const byCategory = stats.by_category || {};
  outlet.querySelector("#chart-category").data = Object.entries(byCategory)
    .sort((a, b) => b[1] - a[1])
    .map(([label, value]) => ({ label, value, color: "var(--chart-1)" }));

  const byDifficulty = stats.by_difficulty || {};
  const difficultyRows = ["1", "2", "3", "4", "5", "unrated"]
    .filter((k) => byDifficulty[k] != null)
    .map((k) => ({
      label: k === "unrated" ? "未評価" : `難易度 ${k}`,
      value: byDifficulty[k] || 0,
      color: k === "unrated" ? "var(--chart-8)" : "var(--chart-1)",
    }));
  outlet.querySelector("#chart-difficulty").data = difficultyRows;

  const byAutomation = stats.by_automation || {};
  outlet.querySelector("#chart-automation").data = Object.entries(byAutomation).map(
    ([key, value], i) => ({
      label: AUTOMATION_LABELS[key] || key,
      value: value || 0,
      color: CHART_COLORS[i % CHART_COLORS.length],
    }),
  );
}
