@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM POL Lab Portal - インストールスクリプト (Windows)
REM ============================================================
REM
REM 使用方法:
REM   curl -fsSL https://raw.githubusercontent.com/Neopolalis/pol-lab-portal/master/scripts/install.bat -o install.bat
REM   install.bat
REM
REM ============================================================

REM --- 定数 ---
set "SEP64================================================================="
set "SUB64=-----------------------------------------------------------------"
set "EXIT_CODE=0"

set "INSTALL_ROOT=C:\neopolalis"
set "PORTAL_DIR=%INSTALL_ROOT%\pol-lab-portal"
set "GITHUB_ZIP=https://github.com/Neopolalis/pol-lab-portal/archive/refs/heads/master.zip"
set "TEMP_DIR=%TEMP%\pol-lab-portal-install"

REM ============================================================
REM 出力関数
REM ============================================================

goto :main

:log_ok
echo [OK]   %~1
exit /b 0

:log_fail
echo [FAIL] %~1 1>&2
exit /b 0

:log_warn
echo [WARN] %~1
exit /b 0

:log_info
echo [INFO] %~1
exit /b 0

:section
echo.
echo %SEP64%
echo %~1
echo %SEP64%
exit /b 0

:timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "DT=%%I"
if defined DT (
    set "TIMESTAMP=[!DT:~0,4!-!DT:~4,2!-!DT:~6,2! !DT:~8,2!:!DT:~10,2!:!DT:~12,2!]"
) else (
    set "TIMESTAMP=[%DATE% %TIME:~0,8%]"
)
exit /b 0

REM ============================================================
REM メイン処理
REM ============================================================

:main

echo.
echo %SEP64%
echo POL Lab Portal - インストーラー
echo %SEP64%
echo インストール先: %INSTALL_ROOT%

call :timestamp
echo %TIMESTAMP%

REM ============================================================
REM [1/6] 管理者権限チェック
REM ============================================================
call :section "[1/6] 管理者権限チェック"

net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    call :log_warn "管理者権限なしで実行しています"
    call :log_info "D:\polalis への書き込みに失敗する場合は管理者として実行してください"
) else (
    call :log_ok "管理者権限で実行中"
)

REM ============================================================
REM [2/6] 事前条件チェック
REM ============================================================
call :section "[2/6] 事前条件チェック"

REM --- curl チェック ---
where curl >nul 2>&1
if %ERRORLEVEL% neq 0 (
    call :log_fail "curl が見つかりません"
    call :log_info "Windows 10以降では標準でインストールされています"
    exit /b 3
)
call :log_ok "curl"

REM --- tar チェック (zip展開用) ---
where tar >nul 2>&1
if %ERRORLEVEL% neq 0 (
    call :log_fail "tar が見つかりません"
    call :log_info "Windows 10以降では標準でインストールされています"
    exit /b 3
)
call :log_ok "tar"

REM --- uv チェック ---
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    call :log_fail "uv が見つかりません"
    echo.
    echo uvのインストール方法:
    echo   PowerShell: irm https://astral.sh/uv/install.ps1 ^| iex
    echo   詳細: https://docs.astral.sh/uv/
    exit /b 3
)
for /f "tokens=*" %%V in ('uv --version 2^>nul') do set "UV_VERSION=%%V"
call :log_ok "uv: !UV_VERSION!"

REM --- Python チェック ---
for /f "tokens=2" %%V in ('uv run python --version 2^>nul') do set "PYTHON_VERSION=%%V"
if not defined PYTHON_VERSION (
    call :log_fail "Python が見つかりません"
    exit /b 3
)

REM Python バージョン検証 (3.9以上)
for /f "tokens=1,2 delims=." %%A in ("!PYTHON_VERSION!") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)
if !PY_MAJOR! lss 3 (
    call :log_fail "Python 3.9以上が必要です（現在: !PYTHON_VERSION!）"
    exit /b 3
)
if !PY_MAJOR! equ 3 if !PY_MINOR! lss 9 (
    call :log_fail "Python 3.9以上が必要です（現在: !PYTHON_VERSION!）"
    exit /b 3
)
call :log_ok "Python: !PYTHON_VERSION!"

REM ============================================================
REM [3/6] 既存インストールチェック
REM ============================================================
call :section "[3/6] 既存インストールチェック"

if exist "%PORTAL_DIR%" (
    call :log_warn "既存のインストールが見つかりました: %PORTAL_DIR%"
    echo.
    set /p "OVERWRITE=上書きしますか？ (y/N): "
    if /i not "!OVERWRITE!"=="y" (
        call :log_info "インストールを中止しました"
        exit /b 0
    )
    call :log_info "既存のインストールを上書きします"
) else (
    call :log_ok "既存インストールなし"
)

REM ============================================================
REM [4/6] ディレクトリ作成
REM ============================================================
call :section "[4/6] ディレクトリ作成"

REM --- インストールルート ---
if not exist "%INSTALL_ROOT%" (
    mkdir "%INSTALL_ROOT%"
    if %ERRORLEVEL% neq 0 (
        call :log_fail "ディレクトリ作成に失敗: %INSTALL_ROOT%"
        exit /b 1
    )
)
call :log_ok "%INSTALL_ROOT%"

REM --- サブディレクトリ ---
for %%D in (data logs) do (
    if not exist "%INSTALL_ROOT%\%%D" (
        mkdir "%INSTALL_ROOT%\%%D"
    )
    call :log_ok "%INSTALL_ROOT%\%%D"
)

REM --- 一時ディレクトリ ---
if exist "%TEMP_DIR%" (
    rmdir /s /q "%TEMP_DIR%"
)
mkdir "%TEMP_DIR%"
call :log_ok "一時ディレクトリ: %TEMP_DIR%"

REM ============================================================
REM [5/6] ダウンロードと展開
REM ============================================================
call :section "[5/6] ダウンロードと展開"

REM --- ダウンロード ---
call :log_info "GitHubからダウンロード中..."
curl -fsSL "%GITHUB_ZIP%" -o "%TEMP_DIR%\master.zip"
if %ERRORLEVEL% neq 0 (
    call :log_fail "ダウンロードに失敗しました"
    rmdir /s /q "%TEMP_DIR%"
    exit /b 1
)
call :log_ok "ダウンロード完了"

REM --- 展開 ---
call :log_info "展開中..."
tar -xf "%TEMP_DIR%\master.zip" -C "%TEMP_DIR%"
if %ERRORLEVEL% neq 0 (
    call :log_fail "展開に失敗しました"
    rmdir /s /q "%TEMP_DIR%"
    exit /b 1
)
call :log_ok "展開完了"

REM --- 既存ディレクトリの削除 ---
if exist "%PORTAL_DIR%" (
    rmdir /s /q "%PORTAL_DIR%"
)

REM --- 配置 ---
call :log_info "インストール先に配置中..."
move "%TEMP_DIR%\pol-lab-portal-master" "%PORTAL_DIR%" >nul
if %ERRORLEVEL% neq 0 (
    call :log_fail "配置に失敗しました"
    rmdir /s /q "%TEMP_DIR%"
    exit /b 1
)
call :log_ok "配置完了: %PORTAL_DIR%"

REM --- 一時ディレクトリ削除 ---
rmdir /s /q "%TEMP_DIR%"

REM ============================================================
REM [6/6] セットアップ実行
REM ============================================================
call :section "[6/6] セットアップ実行"

call :log_info "セットアップスクリプトを実行中..."
cd /d "%PORTAL_DIR%"
call "%PORTAL_DIR%\scripts\setup\setup.bat"
set "SETUP_RESULT=%ERRORLEVEL%"

if !SETUP_RESULT! neq 0 (
    call :log_fail "セットアップに失敗しました (終了コード: !SETUP_RESULT!)"
    set "EXIT_CODE=!SETUP_RESULT!"
)

REM ============================================================
REM 完了
REM ============================================================
echo.
echo %SEP64%
if !EXIT_CODE! equ 0 (
    echo インストール完了
) else (
    echo インストール完了（警告あり）
)
echo %SEP64%

call :timestamp
echo %TIMESTAMP%

echo.
echo インストール先: %PORTAL_DIR%
echo.

if !EXIT_CODE! equ 0 (
    echo 次のステップ:
    echo   1. 環境変数を設定（オプション）: set POL_GITHUB_TOKEN=^<your_token^>
    echo   2. サーバー起動:
    echo      cd %PORTAL_DIR%
    echo      bin\windows\web_only.bat
    echo   3. ブラウザでアクセス: http://localhost:8000
    echo.
    echo 初回ログイン:
    echo   ユーザー名: admin
    echo   パスワード: admin
)

endlocal & exit /b %EXIT_CODE%
