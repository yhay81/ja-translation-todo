# ja-translation-todo

OSSの日本語翻訳に参加したい人と、その調査を支援するAIエージェントのためのカタログです。
翻訳の進み具合やレビュー担当は言語ごとに異なるため、日本語訳に対象を絞っています。
既存の訳や日本語チームの窓口を調べ、どこで何を手伝えるかを掲載しています。

サービスは読み取り専用で、カタログの正本はこのリポジトリの `catalog/tasks/*.json` です。
更新はPull Requestだけを経路とし、メンテナのレビューを経て本番(Cloudflare D1)へ反映されます。
古い情報は自動的に翻訳対象とせず、まず `verification` タスクとして再検証します。

**公開サービス:** [ja.yhay81.com](https://ja.yhay81.com)
(旧ドメインからの転送設定は [運用手順](docs/architecture.md#旧ドメインからの転送) を参照)

## カテゴリから探す

[CSS](css.md) · [JavaScript](javascript.md) · [Python](python.md) · [コマンドライン](command-line.md) · [その他の分野](others.md)

各カテゴリの索引はカタログから生成され、スター数の多い順に読めます。
[公開サイトの一覧](https://ja.yhay81.com/)では、カテゴリや参加条件で絞り込み、更新順や難易度順にも切り替えられます。

## 提供する入口

- Web UI: 検索・フィルタ・統計、タスク詳細(OGP対応)
- REST API v2: `GET /api/v2/tasks`(v1は410 Gone)
- OpenAPI 3.1: `GET /openapi.json`
- Remote MCP: `POST /mcp`（Streamable HTTP。対応版は `2026-07-28` と `2025-11-25`。
  `Accept: application/json, text/event-stream` を指定）
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

エージェントは `discover_only` のタスクでは公開情報を調査し、このレジストリへのPRで根拠を報告できます。
翻訳や、翻訳先へのIssue・PRの提出は対象外です。
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
uv sync --locked
uv run python scripts/build_catalog.py   # カタログを検証し、カテゴリ別の索引を更新
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

依存を更新するときは `uv lock --upgrade` で開発用の `uv.lock` を更新します。
次に `pylock.toml` の先頭に記載されたコマンドに `--upgrade` を加え、
WorkerのPython 3.13で使えるパッケージを解決します。両方のロックファイルを同じPRに含めます。

### D1セットアップとカタログ反映

```powershell
npx --yes wrangler d1 migrations apply ja-translation-todo --remote
uv run python scripts/seed_catalog.py --apply --remote
```

`catalog/tasks/*.json`(git)が正本で、D1は配信用ランタイムストアです。
PRをmergeしたら seed を再実行して本番へ反映します。

### ローカル実行

Cloudflare Workersでは[hayate](https://github.com/hayatepy/hayate)をHTTP基盤として使用し、
`hayate-openapi`と`hayate-mcp`を同じドメインサービスへ接続しています。

Node.js 22.12以降を用意し、Worker用の依存を同期してからローカルD1にカタログを投入します。
次のコマンドはリポジトリのルートから実行します。

```powershell
uv pip sync --python-version 3.13 --python-platform wasm32-pyodide2025 --target python_modules --no-build pylock.toml --preview-features pylock
uv run python scripts/prepare_worker.py
npx --yes wrangler d1 migrations apply ja-translation-todo --local --persist-to dist/worker/.wrangler/state
uv run python scripts/seed_catalog.py --apply --local
npx --yes wrangler dev --cwd dist/worker
```

### デプロイ

deployはrepository rootのWranglerを直接実行せず、配布物の監査を行うwrapperを使います。

```powershell
uv run python scripts/deploy_worker.py --dry-run
uv run python scripts/deploy_worker.py
```

設計は[docs/architecture.md](docs/architecture.md)を参照してください。2025年までの旧一覧は
[docs/legacy-list.md](docs/legacy-list.md)に保存しています。
