const labels = {
  status: {
    needs_verification: "要再検証",
    ready: "実行可能",
    ask_first: "要事前相談",
    in_progress: "進行中",
    blocked: "停止中",
    done: "完了",
    stale: "期限切れ",
  },
  kind: {
    verification: "方針調査",
    translation: "新規翻訳",
    maintenance: "翻訳保守",
  },
  automation: {
    discover_only: "調査のみ",
    draft_only: "下書きまで",
    draft_pr: "PR下書きまで",
    pr_allowed: "PR提出可",
    maintenance_allowed: "保守PR可",
    blocked: "自動化不可",
  },
  permission: {
    unknown: "未確認",
    explicit: "明示あり",
    implied: "実績から推定",
    forbidden: "禁止",
  },
};

const elements = {
  form: document.querySelector("#filters"),
  query: document.querySelector("#query"),
  status: document.querySelector("#status"),
  kind: document.querySelector("#kind"),
  grid: document.querySelector("#task-grid"),
  count: document.querySelector("#result-count"),
  template: document.querySelector("#task-template"),
  dialog: document.querySelector("#task-dialog"),
  detail: document.querySelector("#task-detail"),
  close: document.querySelector(".dialog-close"),
};

let debounce;

async function loadStats() {
  const response = await fetch("/api/v1/stats");
  if (!response.ok) return;
  const stats = await response.json();
  document.querySelector("#metric-total").textContent = stats.total;
  document.querySelector("#metric-ready").textContent = stats.by_status.ready;
  document.querySelector("#metric-verify").textContent = stats.by_status.needs_verification;
  document.querySelector("#catalog-revision").textContent =
    `catalog ${stats.catalog_revision.slice(0, 12)}`;
}

async function loadTasks() {
  const params = new URLSearchParams();
  if (elements.query.value.trim()) params.set("q", elements.query.value.trim());
  if (elements.status.value) params.set("status", elements.status.value);
  if (elements.kind.value) params.set("kind", elements.kind.value);
  params.set("limit", "100");

  elements.grid.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(`/api/v1/tasks?${params}`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const result = await response.json();
    renderTasks(result.items);
    elements.count.textContent = `${result.total}件`;
  } catch (error) {
    elements.grid.replaceChildren(messageCard("catalogを読み込めませんでした。"));
    elements.count.textContent = "取得失敗";
    console.error(error);
  } finally {
    elements.grid.removeAttribute("aria-busy");
  }
}

function renderTasks(tasks) {
  const fragment = document.createDocumentFragment();
  for (const task of tasks) {
    const card = elements.template.content.firstElementChild.cloneNode(true);
    const status = card.querySelector(".status");
    status.textContent = labels.status[task.status] ?? task.status;
    status.dataset.status = task.status;
    card.querySelector(".kind").textContent = labels.kind[task.kind] ?? task.kind;
    card.querySelector("h3").textContent = task.project.repository;
    card.querySelector(".summary").textContent =
      task.project.summary_ja || task.title.ja;
    card.querySelector(".automation").textContent =
      labels.automation[task.automation.level] ?? task.automation.level;
    card.querySelector(".permission").textContent =
      labels.permission[task.permissions.translation] ?? task.permissions.translation;
    card.querySelector(".card-action").addEventListener("click", () => showTask(task));
    fragment.append(card);
  }
  elements.grid.replaceChildren(fragment);
  if (tasks.length === 0) {
    elements.grid.replaceChildren(messageCard("条件に合うタスクはありません。"));
  }
}

function showTask(task) {
  const evidence = task.evidence
    .map(
      (item) =>
        `<li><a href="${escapeAttribute(item.url)}">${escapeHtml(item.kind)}</a>` +
        `<span>${escapeHtml(item.observed_at)} · ${escapeHtml(item.note_ja)}</span></li>`,
    )
    .join("");
  const actions = task.automation.allowed_actions
    .map((action) => `<li><code>${escapeHtml(action)}</code></li>`)
    .join("");
  elements.detail.innerHTML = `
    <p class="eyebrow">${escapeHtml(labels.kind[task.kind] ?? task.kind)}</p>
    <h2>${escapeHtml(task.project.repository)}</h2>
    <p class="dialog-summary">${escapeHtml(task.title.ja)}</p>
    <div class="detail-status">
      <span class="status" data-status="${escapeAttribute(task.status)}">${escapeHtml(labels.status[task.status] ?? task.status)}</span>
      <span>${escapeHtml(labels.automation[task.automation.level] ?? task.automation.level)}</span>
    </div>
    <h3>現在許可されている操作</h3>
    <ul class="action-list">${actions}</ul>
    <h3>証拠</h3>
    <ul class="evidence-list">${evidence || "<li>証拠はまだありません。</li>"}</ul>
    <div class="dialog-links">
      <a class="button primary" href="${escapeAttribute(task.project.url)}">repositoryを見る</a>
      <a class="button secondary" href="${escapeAttribute(task.links.bundle)}">JSON bundle</a>
    </div>
  `;
  elements.dialog.showModal();
}

function messageCard(message) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty-state";
  paragraph.textContent = message;
  return paragraph;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

elements.form.addEventListener("input", () => {
  clearTimeout(debounce);
  debounce = setTimeout(loadTasks, 180);
});
elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  loadTasks();
});
elements.close.addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("click", (event) => {
  if (event.target === elements.dialog) elements.dialog.close();
});
document.querySelector("#copy-mcp").addEventListener("click", async (event) => {
  const url = `${location.origin}/mcp`;
  await navigator.clipboard.writeText(url);
  event.currentTarget.textContent = "コピーしました";
  setTimeout(() => {
    event.currentTarget.textContent = "MCP URLをコピー";
  }, 1400);
});

await Promise.all([loadStats(), loadTasks()]);
