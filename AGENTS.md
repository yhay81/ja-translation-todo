# AGENTS.md

このリポジトリは、OSSの日本語化機会を人間とAIエージェントが安全に発見・検証・実行するための
公開レジストリです。

## 重要な原則

- `catalog/tasks/*.json` が公開タスク定義の正本です。
- `public/tasks.json` と `src/translation_hub/generated_catalog.py` は生成物です。直接編集しません。
- upstreamの翻訳許可、AI利用方針、既存作業を証拠URL付きで確認できないタスクを `ready` にしません。
- `automation.level` を超えた操作をしません。特に `discover_only` は調査と証拠報告だけを許可します。
- 外部リポジトリへのPRにはAI利用を開示し、自己判断でmergeしません。
- claim、提出、結果報告などの書き込み処理は冪等にします。
- claimは作業範囲を拡張しません。D1へ報告しても、人間のreviewなしにcatalogを変更しません。
- code、public documentation、schemaの識別子は英語を使います。利用者向けUIと説明は日本語を基本にします。

## 変更手順

```powershell
uv sync
uv run python scripts/build_catalog.py
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

catalogだけを変更した場合も生成物を更新し、`--check`が成功することを確認します。

```powershell
uv run python scripts/build_catalog.py --check
```

## Cloudflare

- entrypointは `entry.py`、設定は `wrangler.toml` です。
- Python Workers上ではMCP依存を必ずrequest scopeでlazy importします。
- secret、token、`.dev.vars`をcommitしません。
- D1 schema変更は `migrations/` へ追加し、既存migrationを書き換えません。
- deploy前に `uv run pywrangler dev` または同等のworkerd検証を行います。
- Windowsでは `scripts/prepare_worker.py` で `dist/worker` を作り、そこからplain Wranglerを
  実行します。host用 `.venv` / `.venv-workers` をbundleしません。
- deployは `scripts/deploy_worker.py` を使います。repository rootから `wrangler deploy` を
  直接実行しません。
