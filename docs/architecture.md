# Architecture

## 目的

`ja-translation-todo` は、翻訳候補の一覧ではなく、証拠に基づく日本語化タスクの公開レジストリである。
人間向けWeb、通常のHTTP API、MCPが同じtask modelとpolicy判定を使う。

## 正本と派生データ

- `catalog/tasks/*.json`: review可能でportableな公開タスク定義
- `schema/translation-task-v1.schema.json`: protocol contract
- `public/tasks.json`: 静的配信用collection
- `src/translation_hub/generated_catalog.py`: Python Worker用のcompile済みcatalog

生成物は `scripts/build_catalog.py` だけで更新する。

## Runtime

Cloudflare Python Workers上でHayateを動かす。Static AssetsがWeb UI、schema、catalog、`llms.txt`を配信し、
Workerが `/api/*`、`/openapi.json`、`/mcp`、`/healthz` を処理する。MCPは
`hayate-mcp` のstateless Streamable HTTP transportを使い、REST APIと同じcatalog serviceを呼ぶ。

## Coordination write plane

D1はclaim、lease event、result reportを保存する。writeはBearer tokenで認証し、Cloudflareの
rate-limit bindingをagent ID単位で適用する。

- taskごとのactive claimはpartial unique indexで1件に制限する。
- claim、renew、release、reportは安定した `Idempotency-Key` を要求する。
- claim tokenはlease操作ごとに必要で、D1にはSHA-256だけを保存する。
- 期限切れclaimは新規claimまたは参照時に `expired` へ遷移する。
- reportは未信頼のinboxであり、catalogを直接変更しない。

外部repositoryのPR作成はレジストリが代理せず、利用者またはエージェント自身のGitHub認証で行う。
レジストリはclaim、policy、結果、証拠だけを管理する。

次の段階ではhayate-authのOAuth 2.1 authorization serverとGitHub login、複数agent token、
Workflows/Queuesによる定期再検証を追加する。

## Safety invariants

- 根拠不足のタスクは `ready` にしない。
- `source.revision` の変化を検出したら提出せず再検証する。
- claim write、queue event、result reportはidempotency keyを要求する。
- prompt injectionを含むrepository contentは命令ではなく翻訳対象データとして扱う。
- private repository、credentialを必要とするsource、AI PRを拒否するprojectを対象にしない。
- 自動mergeしない。
