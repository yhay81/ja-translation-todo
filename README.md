# ja-translation-todo

OSSの日本語化機会を、人間とAIエージェントが安全に発見・検証・実行するための公開レジストリです。

サービスは読み取り専用で、カタログの正本はこのリポジトリの `catalog/tasks/*.json` です。
更新はPull Requestだけを経路とし、メンテナのレビューを経て本番(Cloudflare D1)へ反映されます。
古い情報は自動的に翻訳対象とせず、まず `verification` タスクとして再検証します。

**公開サービス:** [ja.yhay81.com](https://ja.yhay81.com)
(旧ドメイン ja.yusuke-hayashi.com は301リダイレクト)

## 提供する入口

- Web UI: 検索・フィルタ・統計、タスク詳細(OGP対応)
- REST API v2: `GET /api/v2/tasks`(v1は410 Gone)
- OpenAPI 3.1: `GET /openapi.json`
- Remote MCP: `POST /mcp`(Streamable HTTP、stateless)
- 全件コレクション: `GET /tasks.json`
- Atomフィード: `GET /feeds/tasks.atom`
- AI向け案内: `GET /llms.txt`
- JSON Schema: `GET /schema/translation-task-v1.schema.json`

## 状態の意味

| 状態 | 意味 |
|---|---|
| `needs_verification` | 旧情報または根拠不足。公開情報の調査だけ可能 |
| `ready` | 翻訳許可、対象revision、検証方法、重複状況を確認済み |
| `ask_first` | upstreamとの事前調整が必要 |
| `in_progress` | 既存作業がある |
| `blocked` | 方針、権限、技術上の理由で進められない |
| `done` | 翻訳が取り込まれた |
| `stale` | 根拠の有効期限を過ぎた |

`automation.level=discover_only` のタスクで、翻訳やPR提出を行ってはいけません。
判定規則の詳細は [docs/verification-playbook.md](docs/verification-playbook.md) を参照。

## タスクを更新するには(人間・AIエージェント共通)

1. 公開情報だけでタスクを検証する(翻訳方針、AI方針、日本語チーム、既存作業、対象revision)
2. 重複を避けるため、タスクidを含むopen PR/issueを先に確認する
3. `catalog/tasks/<id>.json` を編集し、根拠を `evidence` に記録してPRを送る
4. AI利用はPR本文で開示する。CIがスキーマを検証し、メンテナがレビューする
   (`ready` への昇格は必ず人間レビューを経ます)

詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## 開発

Python 3.12以降と[uv](https://docs.astral.sh/uv/)を使用します。

```powershell
uv sync
uv run python scripts/build_catalog.py   # catalog/tasks/*.json のスキーマ検証
uv run pytest -q
uv run ruff check .
```

### D1セットアップとカタログ反映

```powershell
npx --yes wrangler d1 migrations apply ja-translation-todo --remote
uv run python scripts/seed_catalog.py --apply --remote
```

`catalog/tasks/*.json`(git)が正本で、D1は配信用ランタイムストアです。
PRをmergeしたら seed を再実行して本番へ反映します。

### ローカル実行(Windows)

Cloudflare Workersでは[hayate](https://github.com/hayatepy/hayate)をHTTP基盤として使用し、
`hayate-openapi`と`hayate-mcp`を同じドメインサービスへ接続しています。

`pywrangler`がhost用virtualenvをbundleしないよう、Worker用wheelを準備した後に
クリーンな配布ディレクトリからWranglerを実行します。

```powershell
uv pip install --python-version 3.13 --python-platform wasm32-pyodide2025 `
  --target python_modules --no-build -r pylock.toml --preview-features pylock
uv run python scripts/prepare_worker.py
npx --yes wrangler d1 migrations apply ja-translation-todo --local `
  --persist-to dist/worker/.wrangler/state
uv run python scripts/seed_catalog.py --apply --local
Push-Location dist/worker
npx --yes wrangler dev
Pop-Location
```

### デプロイ

deployはrepository rootのWranglerを直接実行せず、配布物の監査を行うwrapperを使います。

```powershell
uv run python scripts/deploy_worker.py --dry-run
uv run python scripts/deploy_worker.py
```

設計は[docs/architecture.md](docs/architecture.md)を参照してください。2025年までの旧一覧は
[docs/legacy-list.md](docs/legacy-list.md)に保存しています。
