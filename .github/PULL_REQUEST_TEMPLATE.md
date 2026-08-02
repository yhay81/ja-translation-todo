# タスク更新 PR

## 対象タスク

<!-- 例: verify-facebook-react -->

## 変更内容

<!-- status / permissions / evidence など、何をどう変えたか -->

## 根拠

<!-- 追加した evidence の URL と、確認した内容の要約。observed_at は調査日 -->

## チェックリスト

- [ ] [docs/verification-playbook.md](../docs/verification-playbook.md) の判定規則に従った
- [ ] 確認した根拠をすべて `evidence` に記録した(url / kind / observed_at / note_ja)
- [ ] このタスク id を含む open PR / issue が他にないことを確認した
- [ ] `uv run python scripts/build_catalog.py` がローカルで成功した
- [ ] `ready` への変更を含む場合: evidence 3件以上 + `provenance.last_verified_at` を設定した

## AI 利用の開示

<!-- AI を利用した場合は、どのツールをどの工程で使ったか明記(必須) -->
