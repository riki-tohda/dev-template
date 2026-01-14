# /branch コマンド

GitHub運用ルールに従ってブランチを作成します。

## 手順

1. 引数からブランチの種類と名前を判定
2. 適切なプレフィックスを付与
3. `main` から新しいブランチを作成

## ブランチ命名規則

| 種類 | プレフィックス | 例 |
|------|---------------|-----|
| 新機能 | `feature/` | `feature/email-notification` |
| バグ修正 | `fix/` | `fix/network-reconnect` |
| ドキュメント | `docs/` | `docs/api-reference` |
| リファクタリング | `refactor/` | `refactor/error-handler` |
| 緊急修正 | `hotfix/` | `hotfix/critical-bug` |

## 使用例

```
/branch feature メール通知
/branch fix ネットワーク再接続
/branch docs API仕様書
```

## 実行コマンド

```bash
git checkout main
git pull origin main
git checkout -b <prefix>/<name>
```

---

$ARGUMENTS
