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
