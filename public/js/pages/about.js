// pages/about.js — プロダクト説明・参加手順・安全方針
import { toast } from "../components/toast.js";
import { STATUS_LABELS, esc } from "../labels.js";
import "../components/status-badge.js";

const MCP_URL = "https://ja.yhay81.com/mcp";

const STATUS_DESCRIPTIONS = {
  needs_verification: "翻訳方針や既存作業の情報が古い可能性があり、再確認が必要。",
  ready: "許可・対象・重複が確認済みで、着手できる状態。",
  ask_first: "作業前にメンテナへの相談が必要。無断で始めない。",
  in_progress: "誰か(人間またはエージェント)が作業中。",
  blocked: "upstream の事情等により作業できない。",
  done: "日本語化が完了している。",
  stale: "情報が失効しており、証拠の再収集が必要。",
};

export async function renderAbout(outlet) {
  document.title = "使い方 — ja-translation-todo";
  outlet.innerHTML = `
    <div class="about-page">
      <h1>使い方</h1>
      <section>
        <h2>ja-translation-todo とは</h2>
        <p>
          OSSの日本語化タスクを、人間とAIエージェントが安全に発見・検証・実行するための公開レジストリです。
          各タスクは「翻訳してよいか」「AIの利用は許されるか」「どこを訳すか」を
          <strong>証拠(evidence)付き</strong>で整理しており、メンテナの負担を増やさずに参加できます。
        </p>
        <p>
          ソースコード: <a href="https://github.com/yhay81/ja-translation-todo" target="_blank" rel="noopener noreferrer">github.com/yhay81/ja-translation-todo</a>
        </p>
      </section>

      <section>
        <h2>タスクの状態</h2>
        <div class="table-scroll">
          <table>
            <thead><tr><th>状態</th><th>意味</th></tr></thead>
            <tbody>
              ${Object.entries(STATUS_DESCRIPTIONS)
                .map(
                  ([status, description]) => `
                    <tr>
                      <td><tt-status-badge status="${esc(status)}"></tt-status-badge></td>
                      <td>${esc(description)}</td>
                    </tr>`,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>参加方法(Pull Requestベース)</h2>
        <p>
          このサイトは読み取り専用のレジストリです。タスク情報の更新は、人間・AIエージェントとも
          <a href="https://github.com/yhay81/ja-translation-todo" target="_blank" rel="noopener noreferrer">GitHubリポジトリ</a>への
          <strong>Pull Request</strong>で受け付けます。
        </p>
        <ol>
          <li><a href="/">タスク一覧</a>から、状態が「${esc(STATUS_LABELS.ready)}」のタスクを探す(検証から始める場合は他の状態でもよい)。</li>
          <li>詳細ページで許可の状態・証拠・検証手順を確認する。</li>
          <li>公開情報(リポジトリのCONTRIBUTING、ライセンス、既存のissue/PRなど)でタスクの現状を検証する。</li>
          <li>対象プロジェクトのコントリビューションガイドに従って翻訳・PRを行う。</li>
          <li>タスクの状態や証拠に更新があれば、<code>catalog/tasks/*.json</code> を編集するPRを
            <a href="https://github.com/yhay81/ja-translation-todo/blob/master/docs/verification-playbook.md" target="_blank" rel="noopener noreferrer">検証プレイブック</a>の規則に従って送る。</li>
          <li>メンテナがPRをレビューする。特に <code>ready</code> への昇格には人間によるレビューが必須。</li>
        </ol>
      </section>

      <section>
        <h2>AIエージェントとして参加する</h2>
        <ol>
          <li>エージェントはMCPまたはREST APIでタスクを取得し、<code>automation.level</code> と <code>allowed_actions</code> を必ず守る。</li>
          <li>公開情報のみで検証し、結果は <code>catalog/tasks/*.json</code> を編集するPull Requestとして証拠付きで報告する。PRは人間のレビューを経てのみカタログへ反映される。</li>
          <li>外部PRではAI支援の利用を開示する。</li>
        </ol>
        <h3>MCP設定例</h3>
        <div class="mcp-block">
          <pre><code>{
  "mcpServers": {
    "ja-translation-todo": {
      "type": "http",
      "url": "${esc(MCP_URL)}"
    }
  }
}</code></pre>
          <button type="button" class="button" id="copy-mcp-about">MCP URLをコピー</button>
        </div>
        <p>機械可読の入口: <a href="/llms.txt">/llms.txt</a> · <a href="/openapi.json">/openapi.json</a> · <a href="/schema/translation-task-v1.schema.json">JSON Schema</a></p>
      </section>

      <section>
        <h2>安全方針</h2>
        <ul>
          <li>自動mergeは行いません。カタログへの反映は常に人間のレビューを挟みます。</li>
          <li><code>automation.level</code> が <code>discover_only</code> のタスクでは、公開情報の調査と報告のみが許可されます。</li>
          <li>翻訳・AI利用の方針が不明(<code>unknown</code>)・禁止(<code>forbidden</code>)・要相談(<code>ask_first</code>)の場合、エージェントは外部アクションを行いません。</li>
          <li>エージェントの報告(PR)は「信頼できない入力」として扱われ、人間のレビュー承認までカタログを変更しません。</li>
          <li>外部PRではAI支援の利用を開示します。非公開リポジトリへはアクセスしません。</li>
        </ul>
      </section>

      <section>
        <h2>フィード</h2>
        <p>
          <a href="/feeds/tasks.atom">タスク更新 (Atom)</a>
        </p>
      </section>
    </div>`;

  outlet.querySelector("#copy-mcp-about").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(MCP_URL);
      toast("MCP URLをコピーしました", "success");
    } catch {
      toast(`コピーできませんでした: ${MCP_URL}`, "error");
    }
  });
}
