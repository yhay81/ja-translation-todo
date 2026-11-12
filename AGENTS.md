# AGENTS.md

このリポジトリは、OSSの日本語化機会を人間とAIエージェントが安全に発見・検証・実行するための
公開レジストリです。配信は https://ja.yhay81.com(Cloudflare Python Workers + D1)。

## 重要な原則

- カタログの正本は `catalog/tasks/*.json` です。PRをレビューしてmergeした後、
  `scripts/seed_catalog.py` で配信用のD1へ反映します。
- upstreamの翻訳許可、AI利用方針、既存作業を証拠URL付きで確認できないタスクを `ready` に
  しません。`ready` への昇格は必ず人間のPRレビューを経ます。
  判定規則は `docs/verification-playbook.md`。
- `automation.level` を超えた操作をしません。特に `discover_only` は調査と証拠報告だけを
  許可します。
- 外部リポジトリへのPRにはAI利用を開示し、自己判断でmergeしません。
- code、public documentation、schemaの識別子は英語を使います。利用者向けUIと説明は
  日本語を基本にします。

## 変更手順

```powershell
uv sync --locked
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
- `routes_catalog.py`: 読み取り専用のAPI v2
- `catalog_store.py`: D1アダプターとテスト用のインメモリストア
- `mcp_server.py`: REST APIと同じストアを使うMCPツール
- `taskschema.py`: Worker内バリデータ。CPython側のフルJSON Schema検証
  (`scripts/build_catalog.py`)と整合を保つこと
- `pages.py`: `/tasks/:id` のOGP注入(`public/index.html` の `<!--ssr:head-->`、
  `<!--ssr:head:end-->`、`<!--ssr:data-->` マーカーが前提)

## Cloudflare

- entrypointは `entry.py`(fetch)、設定は `wrangler.toml` です。
- Python Workers上ではMCP等の重い依存を必ずrequest scopeでlazy importします。
- secret、token、`.dev.vars` をcommitしません。
- D1 schema変更は `migrations/` へ追加し、既存migrationを書き換えません。
- 依存を追加したら pylock.toml を再生成し(wasm32-pyodide2025 ターゲットの
  `uv pip compile`)、`python_modules/` へ vendoring します(README参照)。
- `scripts/prepare_worker.py` で `dist/worker` を作り、そこからplain Wranglerを
  実行します。host用 `.venv` / `.venv-workers` をbundleしません。
- deployは `scripts/deploy_worker.py` を使います。repository rootから `wrangler deploy` を
  直接実行しません。
