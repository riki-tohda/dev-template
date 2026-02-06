# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

POL統合ポータル・リソース管理システム（pol-lab）- IoT端末（Raspberry Pi等）上で動作する軽量Webポータル。各アプリケーション（ラベル印刷指示、ファイル転送、ファイル送受信、ME連携）へのアクセス、端末リソース監視、アプリケーションのライフサイクル管理機能を提供する。

## 技術スタック

| 要素 | 技術 |
|------|------|
| Backend | Flask (Python 3.9+) |
| Frontend | Jinja2 + Vanilla JS |
| CSS | Pico.css（クラスレス軽量CSS） |
| 認証 | Flask-Login + bcrypt |
| リソース監視 | psutil |
| プロセス管理 | subprocess / systemctl |
| パッケージ管理 | uv |

## 開発コマンド

```bash
# 依存関係インストール
uv sync

# 開発サーバー起動
uv run flask --app app run --debug

# テスト実行
uv run pytest

# 単一テスト実行
uv run pytest tests/test_routes/test_auth.py -v
```

## アーキテクチャ

```
pol-lab-portal/
├── app/                        # アプリケーション
│   ├── __init__.py             # Flaskアプリ初期化（create_app）
│   ├── routes/                 # ルート定義
│   │   ├── auth.py             # 認証（/login, /logout）
│   │   ├── dashboard.py        # ダッシュボード（/）
│   │   ├── resources.py        # リソースモニタ（/resources）
│   │   └── apps.py             # アプリ管理（/apps）
│   ├── services/               # ビジネスロジック
│   │   ├── resource_monitor.py # psutilラッパー
│   │   └── app_manager.py      # プロセス/サービス制御
│   ├── templates/              # Jinja2テンプレート
│   └── static/                 # 静的ファイル（CSS/JS）
├── config/
│   ├── config.yaml             # システム設定
│   └── apps.yaml               # 管理対象アプリ定義
└── tests/
```

## コーディング規約

### 基本要件
- Python 3.9以上
- 型ヒント必須
- PEP 8準拠
- IoT端末のリソース制約を考慮（軽量性重視）

### 命名規則
- 変数・関数名: `snake_case`
- クラス名: `PascalCase`
- 定数: `UPPERCASE_WITH_UNDERSCORES`

### パス管理
`pathlib`を使用する（文字列結合でのパス操作は避ける）

```python
# Good
from pathlib import Path
config_path = Path(__file__).parent / "configs" / "config.yaml"

# Bad
config_path = os.path.join(os.path.dirname(__file__), "configs", "config.yaml")
```

### エラー処理
- 具体的な例外型を使用する（bare exceptを避ける）
- エラーメッセージは具体的かつユーザーが理解できるものにする

### 関数設計
- 単一責任の原則に従う
- 理想は30〜50行以内
- 循環的複雑度を低く保つ

## GitHub運用

### ブランチ命名規則

| 種類 | プレフィックス |
|------|---------------|
| 新機能 | `feature/` |
| バグ修正 | `fix/` |
| ドキュメント | `docs/` |
| リファクタリング | `refactor/` |
| 緊急修正 | `hotfix/` |

### コミットメッセージ形式

```
<type>: <subject>

<body>（任意）

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

Type: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`

### Claude Code コマンド

| コマンド | 用途 |
|---------|------|
| `/branch` | ブランチ作成（例: `/branch feature メール通知`） |
| `/commit` | コミット作成 |
| `/pr` | PR作成 |

### 運用フロー

```
1. /branch でブランチ作成
2. 開発作業
3. /commit でコミット
4. /pr でPR作成
5. レビュー → マージ
6. 自動で更新履歴が生成（docs/更新履歴/pr/）
```

## ドキュメント構成

```
docs/
├── アーカイブ/         # 大幅修正・廃止されたドキュメント
├── 仕様書/             # 技術仕様・設計ドキュメント
├── 更新履歴/           # PRマージ時に自動生成
│   └── pr/             # PR別の更新履歴
└── 要件定義/           # 要件定義書
```

## 動作方針

### 問題発見時のプロセス
1. 問題を発見したら**修正前に報告**し、認識が正しいか確認を取る
2. 「〜が原因と考えられますが、この認識で正しいでしょうか？」の形式で確認
3. 確認後に解決策を提示する

### 解決策の提示形式
複数の解決策がある場合は推奨案と代替案を提示する。修正内容は以下を明示：
- ファイルパス
- 修正前のコード
- 修正後のコード
- 変更理由

### コードレビュー
レビュー依頼時は以下の形式で評価：
- 10点満点でスコアリング
- 改善点を具体的に提示
- 良い点も併記

### 透明性
- わからないことは「わからない」と答える
- 疑問や確認事項があればすぐに質問する
