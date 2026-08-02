// pages/task-detail.js — タスク詳細ページ(SSR初期データ対応・読み取り専用)
import { api, toastError } from "../api.js";
import {
  esc,
  fmtDate,
  fmtDateTime,
  KIND_LABELS,
  PERMISSION_LABELS,
  PERMISSION_FIELD_LABELS,
  PLATFORM_LABELS,
  CONTENT_TYPE_LABELS,
  JAPANESE_TEAM_LABELS,
  starsOf,
  fmtStars,
} from "../labels.js";
import { difficultyDotsHtml } from "../components/task-card.js";
import "../components/status-badge.js";
import "../components/automation-meter.js";
import "../components/evidence-timeline.js";

// Worker が <!--ssr:data--> に注入した initial-data を1回だけ利用する
function readInitialData(taskId) {
  const el = document.getElementById("initial-data");
  if (!el) return null;
  let data = null;
  try {
    data = JSON.parse(el.textContent);
  } catch {
    data = null;
  }
  el.remove(); // SPA内遷移で別タスクに誤用しないよう破棄
  return data && data.id === taskId ? data : null;
}

const CREDIT_LABELS = {
  unknown: "不明",
  commit_author: "コミット作者として記録",
  co_author: "共同作者として記録",
  contributors_page: "貢献者ページに記載",
  acknowledgement: "謝辞に記載",
  external_link: "外部リンクで紹介",
};

// credit オブジェクトを人が読める1行にする
function creditText(credit) {
  const expected = CREDIT_LABELS[credit.expected] || credit.expected || "不明";
  const attribution = credit.public_attribution ? "公開クレジットあり" : "公開クレジットなし";
  return `${expected} / ${attribution}`;
}

function permissionRow(field, value) {
  const meta = PERMISSION_LABELS[value] || { symbol: "?", label: value || "不明" };
  return `
    <tr class="permission-${esc(value || "unknown")}">
      <td>${esc(PERMISSION_FIELD_LABELS[field] || field)}</td>
      <td><span class="permission-symbol" aria-hidden="true">${esc(meta.symbol)}</span>${esc(meta.label)}</td>
    </tr>`;
}

function kvRow(label, valueHtml) {
  return valueHtml ? `<dt>${esc(label)}</dt><dd>${valueHtml}</dd>` : "";
}

const REPO_URL = "https://github.com/yhay81/ja-translation-todo";

// タスク更新は GitHub リポジトリへの Pull Request で受け付ける
function updateSectionHtml(taskId) {
  const id = encodeURIComponent(taskId);
  return `
    <section class="panel">
      <h2>このタスクを更新する</h2>
      <p>
        このレジストリは読み取り専用です。タスク情報の更新は、GitHubリポジトリの
        <code>catalog/tasks/${esc(taskId)}.json</code> を編集するPull Requestで受け付けます。
        更新の際は<a href="${REPO_URL}/blob/master/docs/verification-playbook.md" target="_blank" rel="noopener noreferrer">検証プレイブック</a>の規則に従ってください。
      </p>
      <ul>
        <li><a href="${REPO_URL}/edit/master/catalog/tasks/${id}.json" target="_blank" rel="noopener noreferrer">GitHubでこのタスクのJSONを編集してPRを作成する</a></li>
        <li>既存の関連作業を確認:
          <a href="${REPO_URL}/issues?q=${id}" target="_blank" rel="noopener noreferrer">Issues</a> ·
          <a href="${REPO_URL}/pulls?q=${id}" target="_blank" rel="noopener noreferrer">Pull Requests</a>
        </li>
        <li><a href="${REPO_URL}/blob/master/docs/verification-playbook.md" target="_blank" rel="noopener noreferrer">検証プレイブック(docs/verification-playbook.md)</a></li>
      </ul>
    </section>`;
}

function pathList(paths) {
  if (!Array.isArray(paths) || paths.length === 0) return "";
  return `<ul>${paths.map((p) => `<li><code>${esc(p)}</code></li>`).join("")}</ul>`;
}

function view(t) {
  const stars = fmtStars(starsOf(t));
  const workflow = t.workflow || {};
  const community = t.community || {};
  const difficulty = t.difficulty || null;

  return `
    <a class="detail-back" href="/">← タスク一覧へ戻る</a>
    <header class="detail-header">
      <div class="badge-row">
        <tt-status-badge status="${esc(t.status)}"></tt-status-badge>
        <span class="chip neutral">${esc(KIND_LABELS[t.kind] || t.kind)}</span>
        <tt-automation-meter level="${esc(t.automation?.level || "")}"></tt-automation-meter>
      </div>
      <h1>${esc(t.title?.ja || t.title?.en || t.id)}</h1>
      ${t.title?.en && t.title?.ja ? `<p class="hero-copy">${esc(t.title.en)}</p>` : ""}
      <p><a class="repo-link" href="${esc(t.project?.url || "#")}" target="_blank" rel="noopener noreferrer">${esc(t.project?.repository || "")}</a></p>
      ${t.project?.summary_ja ? `<p>${esc(t.project.summary_ja)}</p>` : ""}
    </header>

    <div class="detail-columns">
      <div class="detail-main">
        <section class="panel">
          <h2>許可の状態</h2>
          <table class="permission-table">
            <tbody>
              ${permissionRow("translation", t.permissions?.translation)}
              ${permissionRow("ai_assistance", t.permissions?.ai_assistance)}
              ${permissionRow("pull_request", t.permissions?.pull_request)}
            </tbody>
          </table>
          ${
            Array.isArray(t.automation?.allowed_actions) && t.automation.allowed_actions.length > 0
              ? `<h3>許可されている自動化アクション</h3>
                 <div class="chip-row">${t.automation.allowed_actions
                   .map((a) => `<span class="chip"><code>${esc(a)}</code></span>`)
                   .join("")}</div>`
              : ""
          }
        </section>

        <section class="panel">
          <h2>証拠タイムライン</h2>
          <tt-evidence-timeline></tt-evidence-timeline>
        </section>

        ${
          Array.isArray(t.validation) && t.validation.length > 0
            ? `<section class="panel">
                <h2>検証手順</h2>
                ${t.validation
                  .map(
                    (v) => `
                      <div class="validation-item">
                        <span class="chip neutral">${esc(v.kind || "check")}</span>
                        ${v.command ? `<pre><code>${esc(v.command)}</code></pre>` : ""}
                        ${v.description_ja ? `<p class="validation-desc">${esc(v.description_ja)}</p>` : ""}
                      </div>`,
                  )
                  .join("")}
              </section>`
            : ""
        }

        ${updateSectionHtml(t.id)}

        ${
          t.legacy
            ? `<details class="legacy-details panel">
                <summary>旧カタログの情報(legacy)</summary>
                <pre><code>${esc(JSON.stringify(t.legacy, null, 2))}</code></pre>
              </details>`
            : ""
        }
      </div>

      <div class="detail-side">
        <section class="panel">
          <h2>タスク情報</h2>
          <dl class="kv-list">
            ${kvRow("ID", `<code>${esc(t.id)}</code>`)}
            ${kvRow("カテゴリ", t.project?.category ? esc(t.project.category) : "")}
            ${kvRow("ライセンス", t.project?.license ? esc(t.project.license) : "")}
            ${kvRow("Stars", stars ? `★ ${esc(stars)}` : "")}
            ${kvRow(
              "難易度",
              difficulty?.score
                ? `${difficultyDotsHtml(difficulty)} ${esc(String(difficulty.score))}/5`
                : "",
            )}
            ${kvRow(
              "難易度内訳",
              difficulty?.factors
                ? esc(
                    ["volume", "workflow", "domain"]
                      .filter((k) => difficulty.factors[k] != null)
                      .map((k) => `${k}: ${difficulty.factors[k]}`)
                      .join(" / "),
                  )
                : "",
            )}
            ${kvRow(
              "コンテンツ種別",
              t.content_type ? esc(CONTENT_TYPE_LABELS[t.content_type] || t.content_type) : "",
            )}
            ${kvRow(
              "翻訳プラットフォーム",
              workflow.platform
                ? workflow.platform_url
                  ? `<a href="${esc(workflow.platform_url)}" target="_blank" rel="noopener noreferrer">${esc(PLATFORM_LABELS[workflow.platform] || workflow.platform)}</a>`
                  : esc(PLATFORM_LABELS[workflow.platform] || workflow.platform)
                : "",
            )}
            ${kvRow(
              "翻訳リポジトリ",
              workflow.translation_repo ? `<code>${esc(workflow.translation_repo)}</code>` : "",
            )}
            ${kvRow(
              "日本語チーム",
              community.japanese_team
                ? community.team_url
                  ? `<a href="${esc(community.team_url)}" target="_blank" rel="noopener noreferrer">${esc(JAPANESE_TEAM_LABELS[community.japanese_team] || community.japanese_team)}</a>`
                  : esc(JAPANESE_TEAM_LABELS[community.japanese_team] || community.japanese_team)
                : "",
            )}
            ${kvRow("対象locale", t.target?.locale ? `<code>${esc(t.target.locale)}</code>` : "")}
            ${kvRow("更新日時", esc(fmtDateTime(t.updated_at)))}
            ${kvRow("task_revision", t.task_revision ? `<code>${esc(t.task_revision)}</code>` : "")}
            ${kvRow(
              "最終検証",
              t.provenance?.last_verified_at ? esc(fmtDate(t.provenance.last_verified_at)) : "",
            )}
          </dl>
          ${
            t.links?.bundle
              ? `<p style="margin-top:var(--space-3)"><a href="${esc(t.links.bundle)}" target="_blank" rel="noopener noreferrer">JSON bundle を表示</a></p>`
              : ""
          }
        </section>

        <section class="panel">
          <h2>対象パス</h2>
          ${
            t.source
              ? `<h3>source <code>${esc(t.source.revision || "")}</code></h3>${pathList(t.source.paths)}`
              : ""
          }
          ${t.target ? `<h3>target (${esc(t.target.locale || "ja")})</h3>${pathList(t.target.paths)}` : ""}
        </section>

        ${
          t.credit || t.provenance
            ? `<section class="panel">
                <h2>出所</h2>
                <dl class="kv-list">
                  ${kvRow("クレジット", t.credit ? esc(creditText(t.credit)) : "")}
                  ${kvRow(
                    "imported_from",
                    t.provenance?.imported_from ? esc(t.provenance.imported_from) : "",
                  )}
                  ${kvRow(
                    "imported_at",
                    t.provenance?.imported_at ? esc(fmtDate(t.provenance.imported_at)) : "",
                  )}
                </dl>
              </section>`
            : ""
        }
      </div>
    </div>`;
}

export async function renderTaskDetail(outlet, params) {
  outlet.innerHTML = '<p class="page-loading">読み込み中…</p>';

  let bundle = readInitialData(params.id);
  if (!bundle) {
    try {
      bundle = await api(`/api/v2/tasks/${encodeURIComponent(params.id)}`);
    } catch (err) {
      if (err.status === 404) {
        outlet.innerHTML = `
          <div class="notfound-page">
            <p class="code">404</p>
            <h1>タスクが見つかりません</h1>
            <p>ID <code>${esc(params.id)}</code> のタスクは存在しないか、削除されました。</p>
            <p><a class="button" href="/">タスク一覧へ戻る</a></p>
          </div>`;
        document.title = "タスクが見つかりません — ja-translation-todo";
        return;
      }
      outlet.innerHTML = `<p class="error-state">タスクを取得できませんでした: ${esc(err.message)}</p>`;
      toastError(err);
      return;
    }
  }

  document.title = `${bundle.title?.ja || bundle.id} — ja-translation-todo`;
  outlet.innerHTML = view(bundle);
  outlet.querySelector("tt-evidence-timeline").evidence = bundle.evidence || [];
}
