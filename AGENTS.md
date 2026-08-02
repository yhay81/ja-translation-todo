# AGENTS.md

このリポジトリは、OSSの日本語化機会を人間とAIエージェントが安全に発見・検証・実行するための
公開レジストリです。配信は https://ja.yhay81.com(Cloudflare Python Workers + D1)。

## 重要な原則

- 実行時カタログの正本は **D1 の `tasks` テーブル**です。`catalog/tasks/*.json` は
  seed / export / 監査用で、`scripts/seed_catalog.py` で投入、
  `scripts/export_catalog.py` で書き戻します。
- upstreamの翻訳許可、AI利用方針、既存作業を証拠URL付きで確認できないタスクを `ready` に
  しません。`ready` への昇格は必ず人間のレビュー(管理UI承認)を経ます。
  判定規則は `docs/verification-playbook.md`。
- `automation.level` を超えた操作をしません。特に `discover_only` は調査と証拠報告だけを
  許可します。
- 外部リポジトリへのPRにはAI利用を開示し、自己判断でmergeしません。
- claim、提出、結果報告などの書き込み処理は冪等にします(`Idempotency-Key` 必須)。
- claimの整合性トークンはtask単位の `task_revision` です。claimは作業範囲を拡張せず、
  報告(reports)は承認されるまでカタログを変更しません。
- GitHub cronが収集する `repo_snapshots` は機械収集データであり、evidenceに混ぜません。
- code、public documentation、schemaの識別子は英語を使います。利用者向けUIと説明は
  日本語を基本にします。

## 変更手順

```powershell
uv sync
uv run python scripts/build_catalog.py   # catalog/tasks の検証 + public/schema 更新
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

catalogを変更した場合も `--check` が成功することを確認します。

```powershell
uv run python scripts/build_catalog.py --check
```

## コード構成(src/translation_hub)

- `app.py`: アプリ組み立て(旧ドメイン301、v1 410化、MCP、OpenAPI)
- `routes_catalog.py` / `routes_coordination.py` / `routes_me.py` / `routes_admin.py`:
  API v2 のエンドポイント群
- `catalog_store.py` / `coordination.py` / `auth_setup.py` / `github_sync.py`:
  D1実装と、テスト用のMemory実装の二重化(`*_from_env` で注入)
- `taskschema.py`: Worker内バリデータ。CPython側のフルJSON Schema検証
  (`scripts/build_catalog.py`)と整合を保つこと
- `pages.py`: `/tasks/:id` のOGP注入(`public/index.html` の `<!--ssr:head-->` /
  `<!--ssr:data-->` マーカーが前提)

## Cloudflare

- entrypointは `entry.py`(fetch + scheduled)、設定は `wrangler.toml` です。
- Python Workers上ではMCP等の重い依存を必ずrequest scopeでlazy importします。
- secret、token、`.dev.vars` をcommitしません。
  secrets: `AUTH_SECRET`, `GITHUB_OAUTH_CLIENT_ID/SECRET`, `GITHUB_TOKEN`,
  `CLAIM_TOKEN_SECRET`(旧 `AGENT_API_TOKEN_SHA256` は廃止)。
- D1 schema変更は `migrations/` へ追加し、既存migrationを書き換えません。
- 依存を追加したら pylock.toml を再生成し(wasm32-pyodide2025 ターゲットの
  `uv pip compile`)、`python_modules/` へ vendoring します(README参照)。
- Windowsでは `scripts/prepare_worker.py` で `dist/worker` を作り、そこからplain Wranglerを
  実行します。host用 `.venv` / `.venv-workers` をbundleしません。
- deployは `scripts/deploy_worker.py` を使います。repository rootから `wrangler deploy` を
  直接実行しません。
- cronのローカル検証: `curl "http://localhost:8787/cdn-cgi/handler/scheduled?cron=11+*+*+*+*"`
