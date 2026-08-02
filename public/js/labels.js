// labels.js — 日本語ラベル定義と小さな整形ヘルパ

export const STATUS_LABELS = {
  needs_verification: "再検証待ち",
  ready: "着手可能",
  ask_first: "要事前相談",
  in_progress: "作業中",
  blocked: "停止中",
  done: "完了",
  stale: "情報失効",
};

export const STATUS_ORDER = [
  "ready",
  "needs_verification",
  "ask_first",
  "in_progress",
  "blocked",
  "done",
  "stale",
];

export const KIND_LABELS = {
  verification: "検証",
  translation: "翻訳",
  maintenance: "保守",
};

export const AUTOMATION_LABELS = {
  discover_only: "調査のみ",
  draft_only: "下書きまで",
  draft_pr: "PR下書きまで",
  pr_allowed: "PR提出可",
  maintenance_allowed: "保守可",
  blocked: "自動化禁止",
};

// blocked 以外は許可の広さの順(メータ表示に使用)
export const AUTOMATION_ORDER = [
  "discover_only",
  "draft_only",
  "draft_pr",
  "pr_allowed",
  "maintenance_allowed",
];

export const PERMISSION_LABELS = {
  unknown: { symbol: "?", label: "不明" },
  explicit: { symbol: "✓", label: "明示的に許可" },
  implied: { symbol: "≈", label: "暗黙的" },
  forbidden: { symbol: "✕", label: "禁止" },
  disclose: { symbol: "✓", label: "開示すれば可" },
  allowed: { symbol: "✓", label: "可" },
  ask_first: { symbol: "!", label: "要相談" },
};

export const PERMISSION_FIELD_LABELS = {
  translation: "翻訳",
  ai_assistance: "AI支援",
  pull_request: "Pull Request",
};

export const PLATFORM_LABELS = {
  github: "GitHub直",
  crowdin: "Crowdin",
  transifex: "Transifex",
  weblate: "Weblate",
  gitlocalize: "GitLocalize",
  other: "その他",
};

export const CONTENT_TYPE_LABELS = {
  official_docs: "公式ドキュメント",
  readme: "README",
  book: "書籍",
  specification: "仕様書",
  ui_strings: "UI文字列",
  tutorial: "チュートリアル",
};

export const JAPANESE_TEAM_LABELS = {
  active: "活発",
  inactive: "停滞中",
  none: "なし",
  unknown: "不明",
};

export const SORT_LABELS = {
  updated: "更新順",
  stars: "スター順",
  difficulty: "難易度順",
  status: "状態順",
};

export const DIFFICULTY_BAND_LABELS = {
  easy: "易 (1-2)",
  medium: "中 (3)",
  hard: "難 (4-5)",
};

// difficulty score(1-5) → 易/中/難 の帯
export function difficultyBand(score) {
  if (!score) return null;
  if (score <= 2) return "easy";
  if (score === 3) return "medium";
  return "hard";
}

// HTMLエスケープ(テンプレート文字列への埋め込み用)
export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// epoch秒 / ISO文字列 の両方を受け付けて Date にする
function toDate(value) {
  if (value == null || value === "") return null;
  const d = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtDate(value) {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleDateString("ja-JP", { year: "numeric", month: "2-digit", day: "2-digit" });
}

export function fmtDateTime(value) {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// star数: metrics.stars を優先し、旧データの legacy.Star にフォールバック
export function starsOf(task) {
  const v = task?.metrics?.stars ?? task?.legacy?.Star ?? null;
  return typeof v === "number" ? v : null;
}

export function fmtStars(n) {
  if (n == null) return null;
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}
