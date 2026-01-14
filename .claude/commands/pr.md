# /pr コマンド

GitHub運用ルールに従ってプルリクエストを作成します。

## 手順

1. 現在のブランチを確認
2. `main` との差分を確認
3. コミット履歴を確認
4. PRタイトルと説明を生成
5. `gh pr create` でPRを作成

## PRタイトル形式

```
<type>: <subject>
```

コミットメッセージと同じ形式を使用。

## PR説明テンプレート

```markdown
## 概要
<!-- 変更内容を1〜2文で簡潔に説明 -->

## 変更種別
- [ ] 新機能 (feat)
- [ ] バグ修正 (fix)
- [ ] ドキュメント (docs)
- [ ] リファクタリング (refactor)
- [ ] その他

## 関連Issue
Closes #

## 備考
```

## 注意事項

- `main` ブランチからPRは作成しない
- feature/fix/docs ブランチから `main` へのPRを作成
- PRテンプレートは最低限でOK（詳細は自動生成される）

## 実行例

```bash
gh pr create --title "feat: メール通知機能を追加" --body "..."
```

---

$ARGUMENTS
