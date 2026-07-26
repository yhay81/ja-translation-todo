# Contributing

## タスクを追加・更新する

1. `catalog/tasks/` に `translation-task/v1` のJSONファイルを追加します。
2. upstreamの翻訳方針、CONTRIBUTING、関連Issue/PRを `evidence` に記録します。
3. `observed_at` と、翻訳対象のcommit SHAまたはrevisionを記録します。
4. 既存のassignee、open PR、保留指示がないことを確認します。
5. catalogとテストを更新します。

```powershell
uv run python scripts/build_catalog.py
uv run pytest -q
uv run ruff check .
```

## `ready` に必要なもの

- 翻訳を受け付ける明示的な根拠
- AI支援に関する方針、または確認が必要であるという明示
- 対象repository、base revision、対象path
- 用語・文体・変更禁止部分
- 再現可能なvalidation手順
- 重複作業がないことを示す確認
- PR提出方法とAI利用開示

ひとつでも不明なら `needs_verification` または `ask_first` にします。

## AIエージェントによる貢献

`discover_only` で許可されるのは、公開情報の調査と証拠付きcatalog更新です。upstreamへのコメント、
Issue作成、PR提出は含みません。外部操作を伴う場合は、タスクの `allowed_actions` とupstream方針を
必ず確認してください。

## Agentによる検証報告

Agentはtask bundleの `automation.allowed_actions` を確認してからclaimします。claimは作業予約であり、
翻訳・Issue・PR作成の許可ではありません。`discover_only` の報告に外部writeを含めるとAPIが拒否します。

報告された根拠はそのまま正本へ反映しません。人間がURL、観測日、upstreamの権限者、既存作業を確認し、
必要な場合だけ `catalog/tasks/*.json` を更新します。
