# GitHub運用仕様書

## 概要

本プロジェクトのGitHub運用ルールを定義する。

## 基本ルール

- 全ての変更はPR（Pull Request）経由で行う
- `main` ブランチへの直接プッシュは禁止
- hotfix（緊急修正）もPR必須

## ブランチ運用

### 命名規則

| 種類 | プレフィックス | 例 |
|------|---------------|-----|
| 新機能 | `feature/` | `feature/email-notification` |
| バグ修正 | `fix/` | `fix/network-reconnect` |
| ドキュメント | `docs/` | `docs/api-reference` |
| リファクタリング | `refactor/` | `refactor/error-handler` |
| 緊急修正 | `hotfix/` | `hotfix/critical-bug` |

### ブランチフロー

```
main（保護）
  ↑
feature/xxx → PR → レビュー → マージ → main
fix/xxx     → PR → レビュー → マージ → main
hotfix/xxx  → PR → レビュー → マージ → main
```

## コミット運用

### コミットメッセージ形式

```
<type>: <subject>

<body>（任意）

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### Type一覧

| Type | 説明 |
|------|------|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメント |
| `refactor` | リファクタリング |
| `test` | テスト |
| `chore` | 雑務 |
| `style` | スタイル |
| `perf` | パフォーマンス |

### ルール

- subject は日本語で簡潔に（50文字以内推奨）
- 1コミット = 1つの論理的な変更
- 動作する状態でコミット

## PR（Pull Request）運用

### 承認フロー

```
開発者 → PR作成 → 非開発者レビュー → 開発者レビュー → マージ
                   (内容・影響確認)    (技術確認)
```

### PRに含める情報

| 項目 | 説明 | 生成方法 |
|------|------|---------|
| 概要 | 変更内容の要約 | AI自動生成 |
| ユーザーへの影響 | 非開発者向けの影響説明 | AI自動生成 |
| 種別 | feat/fix/docs等 | コミットから自動判定 |
| 修正範囲 | 変更ファイル一覧 | 自動生成 |
| 影響度 | 高/中/低 | AI自動判定 |
| テスト内容 | テスト項目一覧 | AI自動生成 |

### 影響度の判定基準

| 影響度 | 条件例 |
|--------|--------|
| 高 | DB変更、API変更、コア機能変更 |
| 中 | UI変更、設定ファイル変更 |
| 低 | ドキュメント、スタイルのみ |

※ 具体的なディレクトリパターンはプロジェクトに応じて `/pr` コマンドでカスタマイズ

## 自動化

### PR作成時（GitHub Actions）

- 変更ファイルのカテゴリ分類
- 統計情報の生成
- テストチェックリストの自動生成
- PRコメントとして追加

### PRマージ時（GitHub Actions）

自動的に `docs/更新履歴/pr/YYYY-MM-DD_PR{番号}.md` を生成。

#### 生成される内容

| セクション | 内容 |
|-----------|------|
| 基本情報 | PR番号、作成者、マージ日、変更量 |
| レビュー | 承認者、レビュー参加者 |
| 概要 | PR本文（概要、影響、テスト内容） |
| コミット一覧 | 含まれるコミット |
| 変更ファイル | ファイル一覧と変更量 |

## ドキュメント管理

### 更新履歴の構成

```
docs/更新履歴/
└── pr/
    ├── 2026-01-14_PR1.md
    ├── 2026-01-14_PR2.md
    └── ...
```

### 手動更新履歴（廃止）

以下は廃止し、PRマージ時の自動生成に統一：
- `docs/更新履歴/YYYY-MM-DD_内容.md`（手動作成）
- `docs/更新履歴/YYYY-MM_微修正.md`（手動作成）

## Claude Code コマンド

| コマンド | 用途 | ファイル |
|---------|------|---------|
| `/branch` | ブランチ作成 | `.claude/commands/branch.md` |
| `/commit` | コミット作成 | `.claude/commands/commit.md` |
| `/pr` | PR作成 | `.claude/commands/pr.md` |

## ブランチ保護ルール

`main` ブランチに以下の保護を設定：

- [ ] 直接プッシュを禁止
- [ ] PRマージにレビュー必須
- [ ] ステータスチェック必須（CI通過）

## 関連ファイル

| ファイル | 用途 |
|---------|------|
| `.github/PULL_REQUEST_TEMPLATE.md` | PRテンプレート |
| `.github/workflows/pr-review-flow.yml` | PR作成時の自動コメント |
| `.github/workflows/pr-changelog.yml` | PRマージ時の更新履歴生成 |
| `.github/ISSUE_TEMPLATE/` | Issueテンプレート |
