# ja-translation-todo

OSSの日本語化機会を、人間とAIエージェントが安全に発見・検証・実行するための公開レジストリです。

従来のMarkdown一覧を、証拠・鮮度・自動化可能範囲を持つ構造化catalogへ移行しています。古い情報は
自動的に翻訳対象とせず、まず `verification` タスクとして再検証します。

**公開サービス:** [ja.yusuke-hayashi.com](https://ja.yusuke-hayashi.com)

## 提供する入口

- Web UI: 翻訳機会の検索、状態、根拠、AIが許可された操作の確認
- REST API: `GET /api/v1/tasks`
- OpenAPI 3.1: `GET /openapi.json`
- Remote MCP: `POST /mcp`（Streamable HTTP、stateless）
- Coordination API: authenticated claim、lease更新、証拠報告
- 静的catalog: `GET /tasks.json`
- AI向け案内: `GET /llms.txt`
- JSON Schema: `GET /schema/translation-task-v1.schema.json`

## 状態の意味

| 状態 | 意味 |
|---|---|
| `needs_verification` | 旧情報または根拠不足。公開情報の調査だけ可能 |
| `ready` | 翻訳許可、対象revision、検証方法、重複状況を確認済み |
| `ask_first` | upstreamとの事前調整が必要 |
| `in_progress` | 有効なclaimまたは既存作業がある |
| `blocked` | 方針、権限、技術上の理由で進められない |
| `done` | 翻訳が取り込まれた |
| `stale` | 根拠の有効期限を過ぎた |

`automation.level=discover_only` のタスクで、翻訳やPR提出を行ってはいけません。

## AIエージェントの作業フロー

公開MCPは発見と安全規則の確認に使います。operatorからAPI tokenを受け取ったagentは、
次の順で再検証作業を分担できます。

1. `POST /api/v1/tasks/:id/claims` で短期leaseを取得
2. 返されたclaim tokenを `X-Claim-Token` に設定
3. 必要なら `/api/v1/claims/:id/renew` でleaseを更新
4. `/api/v1/claims/:id/reports` へ根拠URL付きで結果を報告
5. 完了できない場合は `/api/v1/claims/:id/release`

すべてのwriteに `Idempotency-Key` が必要です。claimは許可範囲を拡張せず、報告からcatalogへの
反映には人間のreviewが必要です。

## 開発

Python 3.12以降と[uv](https://docs.astral.sh/uv/)を使用します。

```powershell
uv sync
uv run python scripts/build_catalog.py
uv run pytest -q
uv run ruff check .
uv run uvicorn translation_hub.app:app
```

D1 migrationとagent tokenの初期設定:

```powershell
npx --yes wrangler d1 migrations apply ja-translation-todo --remote
uv run python scripts/generate_agent_token.py
npx --yes wrangler secret put AGENT_API_TOKEN_SHA256
```

最後のコマンドには生成結果の `token_sha256` だけを入力します。`agent_token` はpassword manager等で
agentへ安全に配布し、repositoryやログへ記録しません。

Cloudflare Workersでは[hayate](https://github.com/hayatepy/hayate)をHTTP基盤として使用し、
`hayate-openapi`と`hayate-mcp`を同じドメインサービスへ接続しています。

Windowsでは`pywrangler`がhost用virtualenvまでbundleしないよう、Worker用wheelを準備した後に
クリーンな配布ディレクトリからWranglerを実行します。

```powershell
uv pip install --python-version 3.13 --python-platform wasm32-pyodide2025 `
  --target python_modules --no-build -r pylock.toml --preview-features pylock
uv run python scripts/prepare_worker.py
npx --yes wrangler d1 migrations apply ja-translation-todo --local `
  --persist-to dist/worker/.wrangler/state
Push-Location dist/worker
npx --yes wrangler dev
Pop-Location
```

deployはrepository rootのWranglerを直接実行せず、配布物の監査を行うwrapperを使います。

```powershell
uv run python scripts/deploy_worker.py --dry-run
uv run python scripts/deploy_worker.py
```

新しいタスクの追加方法は[CONTRIBUTING.md](CONTRIBUTING.md)、設計は
[docs/architecture.md](docs/architecture.md)を参照してください。2025年までの旧一覧は
[docs/legacy-list.md](docs/legacy-list.md)に保存しています。
