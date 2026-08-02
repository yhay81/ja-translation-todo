# 検証プレイブック

タスクを `needs_verification` から他の状態へ動かすときの判定規則と記録規約。
人間・AIエージェントの双方がこの手順に従う。**`ready` への昇格は必ず人間の
レビューを経る**(エージェントは提案までしかできない)。

## 確認項目と対応フィールド

| 確認項目 | 見る場所 | 決まるフィールド |
|---|---|---|
| 翻訳受付方針 | CONTRIBUTING / TRANSLATING / i18n ガイド / 翻訳リポジトリの README | `permissions.translation`、evidence `translation_policy` |
| PR 受付経路 | 翻訳ガイドの手順(直接 PR / 専用リポジトリ / プラットフォーム) | `permissions.pull_request`、`workflow.platform` |
| AI 利用方針 | CONTRIBUTING 内の AI/LLM ポリシー、`.github/` の方針ファイル | `permissions.ai_assistance`、evidence `ai_policy` |
| 日本語チームの存在と活性 | ja 系リポジトリの直近コミット・merged PR(90日以内か)、メンバー数 | `community.japanese_team`、evidence `team_activity` |
| 既存作業・重複 | open PR / issue の "japanese" "日本語" 検索 | evidence `issue` / `pull_request` |
| 対象範囲と revision | 翻訳対象ディレクトリ、追従すべき upstream revision | `source.revision` / `source.paths` / `target.paths` |
| ライセンス | LICENSE + ドキュメント個別ライセンス | `project.license` |

## status 判定規則

- 明示的な翻訳受付方針 + 受付経路が明確 + 未着手領域あり → **`ready`**
  (automation は AI 許容が明示なら `draft_pr`、明記なしは `draft_only`)
- 方針はあるがメンテナ合意が前提(issue で宣言する文化など) → **`ask_first`**
- 日本語チームが活発に全量をカバー中 → **`in_progress`**(参加窓口を evidence に)
- 翻訳または AI 利用の禁止が明示 → **`blocked`**(automation は `blocked`)
- 判断材料不足 → **`needs_verification`** のまま
- 証拠の観測日から 180 日超で upstream が動いている → **`stale`** に降格を提案する
- upstream リポジトリが archived → **`blocked`**

## 昇格タスクの evidence 最低要件

`ready` / `ask_first` / `in_progress` へ動かすタスクは最低 3 件:

1. `translation_policy` — 方針 URL + 該当文言の要旨を note_ja に
2. `repository` — 対象 revision を確認した記録
3. `issue` または `pull_request` または `team_activity` — 重複・既存作業の確認

すべての evidence に `observed_at`(調査日)必須。昇格時は
`provenance.last_verified_at` を調査日に、`provenance.revision` を +1 する。

## 難易度の付け方

`difficulty.score`(1〜5)は factors の重み付き平均から丸める:

- `volume`(0.4): small=1, medium=3, large=5(旧一覧の文章量 少/中/多 に対応)
- `workflow`(0.3): platform=1, direct_pr=3, fork_hosted=5, negotiated は +1 補正
- `domain`(0.2): tutorial=1, framework_docs=3, specification/book=5
- 補正(0.1): 日本語チームが active なら −1、方針不明・停滞なら +1

## 反映経路

1. 貢献者(人間・AIエージェント): 公開情報で調査 → `catalog/tasks/<id>.json` を編集し
   evidence を追記する PR を送る(AI 利用は PR 本文で開示)
2. PR を送る前に、タスク id を含む open PR / issue を確認して重複を避ける
3. メンテナ: PR をレビューして merge(`ready` への昇格はここで人間が確定する)
4. メンテナ: `uv run python scripts/seed_catalog.py --apply --remote` で本番 D1 へ反映
