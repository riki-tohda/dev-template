#!/bin/bash
#
# POL Lab Portal - インストールスクリプト (Linux)
#
# 使用方法:
#   curl -fsSL https://raw.githubusercontent.com/Neopolalis/pol-lab-portal/master/scripts/install.sh | sudo bash
#
# または
#   curl -fsSL https://raw.githubusercontent.com/Neopolalis/pol-lab-portal/master/scripts/install.sh -o install.sh
#   chmod +x install.sh
#   sudo ./install.sh
#

set -e

# === 定数 ===
SEP64="================================================================"
SUB64="----------------------------------------------------------------"
EXIT_CODE=0

INSTALL_ROOT="/opt/polalis"
PORTAL_DIR="$INSTALL_ROOT/pol-lab-portal"
GITHUB_ZIP="https://github.com/Neopolalis/pol-lab-portal/archive/refs/heads/master.zip"
TEMP_DIR="/tmp/pol-lab-portal-install"
SERVICE_USER="polalis"

# === 出力関数 ===
log_ok()    { echo "[OK]   $1"; }
log_fail()  { echo "[FAIL] $1" >&2; }
log_warn()  { echo "[WARN] $1"; }
log_info()  { echo "[INFO] $1"; }

section() {
    echo ""
    echo "$SEP64"
    echo "$1"
    echo "$SEP64"
}

timestamp() {
    date '+[%Y-%m-%d %H:%M:%S]'
}

# === メイン処理 ===

echo ""
echo "$SEP64"
echo "POL Lab Portal - インストーラー"
echo "$SEP64"
echo "インストール先: $INSTALL_ROOT"
timestamp

# ==============================================================
# [1/7] root権限チェック
# ==============================================================
section "[1/7] root権限チェック"

if [ "$(id -u)" -ne 0 ]; then
    log_fail "このスクリプトはroot権限で実行してください"
    echo ""
    echo "使用方法:"
    echo "  sudo $0"
    exit 1
fi
log_ok "root権限で実行中"

# ==============================================================
# [2/7] 事前条件チェック
# ==============================================================
section "[2/7] 事前条件チェック"

# --- curl チェック ---
if ! command -v curl &>/dev/null; then
    log_fail "curl が見つかりません"
    echo ""
    echo "インストール方法:"
    echo "  Ubuntu/Debian: apt install curl"
    echo "  CentOS/RHEL:   yum install curl"
    exit 3
fi
log_ok "curl"

# --- unzip チェック ---
if ! command -v unzip &>/dev/null; then
    log_fail "unzip が見つかりません"
    echo ""
    echo "インストール方法:"
    echo "  Ubuntu/Debian: apt install unzip"
    echo "  CentOS/RHEL:   yum install unzip"
    exit 3
fi
log_ok "unzip"

# --- uv チェック ---
if ! command -v uv &>/dev/null; then
    log_fail "uv が見つかりません"
    echo ""
    echo "インストール方法:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  詳細: https://docs.astral.sh/uv/"
    exit 3
fi
UV_VERSION=$(uv --version 2>/dev/null)
log_ok "uv: $UV_VERSION"

# --- Python チェック ---
PYTHON_VERSION=$(uv run python --version 2>/dev/null | awk '{print $2}')
if [ -z "$PYTHON_VERSION" ]; then
    log_fail "Python が見つかりません"
    exit 3
fi

# Python バージョン検証 (3.9以上)
PY_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    log_fail "Python 3.9以上が必要です（現在: $PYTHON_VERSION）"
    exit 3
fi
log_ok "Python: $PYTHON_VERSION"

# ==============================================================
# [3/7] 既存インストールチェック
# ==============================================================
section "[3/7] 既存インストールチェック"

if [ -d "$PORTAL_DIR" ]; then
    log_warn "既存のインストールが見つかりました: $PORTAL_DIR"
    echo ""
    read -p "上書きしますか？ (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        log_info "インストールを中止しました"
        exit 0
    fi
    log_info "既存のインストールを上書きします"
else
    log_ok "既存インストールなし"
fi

# ==============================================================
# [4/7] ディレクトリ作成
# ==============================================================
section "[4/7] ディレクトリ作成"

# --- インストールルート ---
if [ ! -d "$INSTALL_ROOT" ]; then
    mkdir -p "$INSTALL_ROOT"
fi
log_ok "$INSTALL_ROOT"

# --- サブディレクトリ ---
for dir in data logs etc/systemd; do
    if [ ! -d "$INSTALL_ROOT/$dir" ]; then
        mkdir -p "$INSTALL_ROOT/$dir"
    fi
    log_ok "$INSTALL_ROOT/$dir"
done

# --- 一時ディレクトリ ---
if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
fi
mkdir -p "$TEMP_DIR"
log_ok "一時ディレクトリ: $TEMP_DIR"

# ==============================================================
# [5/7] ダウンロードと展開
# ==============================================================
section "[5/7] ダウンロードと展開"

# --- ダウンロード ---
log_info "GitHubからダウンロード中..."
if ! curl -fsSL "$GITHUB_ZIP" -o "$TEMP_DIR/master.zip"; then
    log_fail "ダウンロードに失敗しました"
    rm -rf "$TEMP_DIR"
    exit 1
fi
log_ok "ダウンロード完了"

# --- 展開 ---
log_info "展開中..."
if ! unzip -q "$TEMP_DIR/master.zip" -d "$TEMP_DIR"; then
    log_fail "展開に失敗しました"
    rm -rf "$TEMP_DIR"
    exit 1
fi
log_ok "展開完了"

# --- 既存ディレクトリの削除 ---
if [ -d "$PORTAL_DIR" ]; then
    rm -rf "$PORTAL_DIR"
fi

# --- 配置 ---
log_info "インストール先に配置中..."
mv "$TEMP_DIR/pol-lab-portal-master" "$PORTAL_DIR"
log_ok "配置完了: $PORTAL_DIR"

# --- 一時ディレクトリ削除 ---
rm -rf "$TEMP_DIR"

# ==============================================================
# [6/7] セットアップ実行
# ==============================================================
section "[6/7] セットアップ実行"

log_info "セットアップスクリプトを実行中..."
cd "$PORTAL_DIR"
chmod +x "$PORTAL_DIR/scripts/setup/setup.sh"
if ! "$PORTAL_DIR/scripts/setup/setup.sh"; then
    log_fail "セットアップに失敗しました"
    EXIT_CODE=1
fi

# ==============================================================
# [7/7] systemdサービス登録（オプション）
# ==============================================================
section "[7/7] systemdサービス登録"

if command -v systemctl &>/dev/null; then
    echo ""
    read -p "systemdサービスとして登録しますか？ (y/N): " REGISTER_SERVICE

    if [ "$REGISTER_SERVICE" = "y" ] || [ "$REGISTER_SERVICE" = "Y" ]; then
        # --- サービスユーザー作成 ---
        if ! id "$SERVICE_USER" &>/dev/null; then
            log_info "サービスユーザーを作成中: $SERVICE_USER"
            useradd -r -s /bin/false -d "$INSTALL_ROOT" "$SERVICE_USER"
            log_ok "ユーザー作成: $SERVICE_USER"
        else
            log_ok "ユーザー存在: $SERVICE_USER"
        fi

        # --- 所有権設定 ---
        chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_ROOT"
        log_ok "所有権設定: $SERVICE_USER"

        # --- サービスファイルコピー ---
        if [ -f "$PORTAL_DIR/scripts/pol-lab-portal.service" ]; then
            cp "$PORTAL_DIR/scripts/pol-lab-portal.service" /etc/systemd/system/
            cp "$PORTAL_DIR/scripts/pol-lab-portal.service" "$INSTALL_ROOT/etc/systemd/"

            systemctl daemon-reload
            log_ok "サービスファイル登録"

            read -p "サービスを今すぐ起動しますか？ (y/N): " START_SERVICE
            if [ "$START_SERVICE" = "y" ] || [ "$START_SERVICE" = "Y" ]; then
                systemctl enable pol-lab-portal
                systemctl start pol-lab-portal
                log_ok "サービス起動"

                # サービス状態確認
                sleep 2
                if systemctl is-active --quiet pol-lab-portal; then
                    log_ok "サービス稼働中"
                else
                    log_warn "サービスが起動していない可能性があります"
                    echo "確認: systemctl status pol-lab-portal"
                fi
            else
                log_info "サービスは手動で起動してください"
                echo "  systemctl enable pol-lab-portal"
                echo "  systemctl start pol-lab-portal"
            fi
        else
            log_warn "サービスファイルが見つかりません"
        fi
    else
        log_info "systemdサービス登録をスキップ"
    fi
else
    log_info "systemdが見つかりません（スキップ）"
fi

# ==============================================================
# 完了
# ==============================================================
echo ""
echo "$SEP64"
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "インストール完了"
else
    echo "インストール完了（警告あり）"
fi
echo "$SEP64"
timestamp

echo ""
echo "インストール先: $PORTAL_DIR"
echo ""

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "次のステップ:"
    echo "  1. 環境変数を設定（オプション）: export POL_GITHUB_TOKEN=<your_token>"
    echo "  2. サーバー起動:"
    echo "     cd $PORTAL_DIR"
    echo "     bin/linux/web_only.sh"
    echo "  3. ブラウザでアクセス: http://localhost:8000"
    echo ""
    echo "初回ログイン:"
    echo "  ユーザー名: admin"
    echo "  パスワード: admin"
    echo ""

    if command -v systemctl &>/dev/null; then
        echo "systemdサービス管理:"
        echo "  起動: systemctl start pol-lab-portal"
        echo "  停止: systemctl stop pol-lab-portal"
        echo "  状態: systemctl status pol-lab-portal"
    fi
fi

exit $EXIT_CODE
