# dev-template

開発プロジェクト用のテンプレートリポジトリです。GitHub運用ルールとClaude Code設定が含まれています。

## 含まれる設定

| カテゴリ | ファイル | 説明 |
|---------|---------|------|
| GitHub | `.github/PULL_REQUEST_TEMPLATE.md` | PRテンプレート |
| GitHub | `.github/workflows/pr-changelog.yml` | PRマージ時の自動更新履歴生成 |
| Claude | `.claude/commands/branch.md` | `/branch` コマンド |
| Claude | `.claude/commands/commit.md` | `/commit` コマンド |
| Claude | `.claude/commands/pr.md` | `/pr` コマンド |
| Docs | `docs/仕様書/GitHub運用仕様書.md` | GitHub運用ルール |

## 使い方

### 新規プロジェクト

1. このリポジトリページで **「Use this template」** をクリック
2. **「Create a new repository」** を選択
3. リポジトリ名と所有者（個人/組織）を入力
4. 作成完了

```bash
git clone https://github.com/<owner>/<new-repo>.git
cd <new-repo>

# CLAUDE.mdをプロジェクトに合わせて編集
mv CLAUDE.md.template CLAUDE.md
```

### 既存プロジェクト

```bash
cd <existing-project>
curl -sL https://raw.githubusercontent.com/riki-tohda/dev-template/main/scripts/setup.sh | bash
```

## 運用フロー

```
【開発フロー】
1. /branch でブランチ作成
2. 開発作業
3. /commit でコミット
4. /pr でPR作成
5. レビュー → マージ
6. 自動で更新履歴が生成（docs/更新履歴/pr/）
```

## カスタマイズ

### CLAUDE.md

`CLAUDE.md.template` を `CLAUDE.md` にリネームし、以下をプロジェクトに合わせて編集：

- プロジェクト情報
- コーディング規約（言語、フレームワーク）
- ドキュメント構成

### PR影響度の判定基準

`.claude/commands/pr.md` の「影響度の判定基準」セクションをプロジェクトのディレクトリ構成に合わせて修正。

## ライセンス

MIT License
