#!/bin/bash
#
# dev-template セットアップスクリプト
# 既存プロジェクトにGitHub運用・Claude Code設定を追加します
#

set -e

TEMPLATE_REPO="https://raw.githubusercontent.com/riki-tohda/dev-template/main"

# 色付け
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== dev-template セットアップ ===${NC}"
echo ""

# Gitリポジトリかチェック
if [ ! -d ".git" ]; then
    echo -e "${RED}エラー: Gitリポジトリ内で実行してください${NC}"
    exit 1
fi

# ディレクトリ作成
echo "ディレクトリを作成中..."
mkdir -p .github/workflows
mkdir -p .claude/commands
mkdir -p docs/仕様書

# ファイルダウンロード関数
download_file() {
    local remote_path=$1
    local local_path=$2

    if [ -f "$local_path" ]; then
        echo -e "${YELLOW}  スキップ: $local_path (既に存在)${NC}"
        return
    fi

    echo "  ダウンロード: $local_path"
    curl -sL "$TEMPLATE_REPO/$remote_path" -o "$local_path"
}

# GitHub設定
echo ""
echo "GitHub設定をダウンロード中..."
download_file ".github/PULL_REQUEST_TEMPLATE.md" ".github/PULL_REQUEST_TEMPLATE.md"
download_file ".github/workflows/pr-changelog.yml" ".github/workflows/pr-changelog.yml"

# Claude Code設定
echo ""
echo "Claude Code設定をダウンロード中..."
download_file ".claude/commands/branch.md" ".claude/commands/branch.md"
download_file ".claude/commands/commit.md" ".claude/commands/commit.md"
download_file ".claude/commands/pr.md" ".claude/commands/pr.md"

# ドキュメント
echo ""
echo "ドキュメントをダウンロード中..."
download_file "docs/仕様書/GitHub運用仕様書.md" "docs/仕様書/GitHub運用仕様書.md"

# CLAUDE.md
echo ""
if [ ! -f "CLAUDE.md" ]; then
    echo "CLAUDE.md.templateをダウンロード中..."
    curl -sL "$TEMPLATE_REPO/CLAUDE.md.template" -o "CLAUDE.md"
    echo -e "${YELLOW}  注意: CLAUDE.md をプロジェクトに合わせて編集してください${NC}"
else
    echo -e "${YELLOW}CLAUDE.md は既に存在します（スキップ）${NC}"
fi

echo ""
echo -e "${GREEN}=== セットアップ完了 ===${NC}"
echo ""
echo "次のステップ:"
echo "  1. CLAUDE.md をプロジェクトに合わせて編集"
echo "  2. git add . && git commit -m 'chore: 開発テンプレートを追加'"
echo ""
