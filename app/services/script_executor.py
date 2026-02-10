"""スクリプト実行サービスモジュール"""

import platform
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.log_manager import get_logger
from app.services.models import AppScript, ScriptExecution

logger = get_logger("app")

# stdout/stderr の最大サイズ (64KB)
MAX_OUTPUT_SIZE = 64 * 1024

# 許可する拡張子
ALLOWED_EXTENSIONS_WINDOWS = {".bat", ".cmd"}
ALLOWED_EXTENSIONS_LINUX = {".sh"}


@dataclass
class ScriptExecutionResult:
    """スクリプト実行結果"""

    success: bool
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    error_message: str | None = None


class ScriptExecutor:
    """スクリプト実行クラス"""

    def __init__(self, allowed_base_dirs: list[Path]) -> None:
        """初期化。

        Args:
            allowed_base_dirs: スクリプト実行を許可するベースディレクトリ
        """
        self.allowed_base_dirs = [d.resolve() for d in allowed_base_dirs]
        self._is_windows = platform.system() == "Windows"

    def validate_script(self, script: AppScript) -> tuple[bool, str]:
        """スクリプトを検証する。

        Args:
            script: スクリプト情報

        Returns:
            (有効かどうか, エラーメッセージ)
        """
        if not script.script_path:
            return False, "スクリプトパスが設定されていません"

        script_path = Path(script.script_path).resolve()

        # 拡張子チェック
        allowed_ext = (
            ALLOWED_EXTENSIONS_WINDOWS
            if self._is_windows
            else ALLOWED_EXTENSIONS_LINUX
        )
        if script_path.suffix.lower() not in allowed_ext:
            return False, (
                f"許可されていない拡張子です: {script_path.suffix} "
                f"(許可: {', '.join(allowed_ext)})"
            )

        # ベースディレクトリチェック
        if not self._is_in_allowed_dirs(script_path):
            return False, (
                f"許可されたディレクトリ外のスクリプトです: {script_path}"
            )

        # 存在確認
        if not script_path.exists():
            return False, f"スクリプトファイルが見つかりません: {script_path}"

        if not script_path.is_file():
            return False, f"スクリプトパスがファイルではありません: {script_path}"

        return True, ""

    def execute_sync(self, script: AppScript) -> ScriptExecutionResult:
        """スクリプトを同期実行する。

        Args:
            script: スクリプト情報

        Returns:
            実行結果
        """
        valid, error_msg = self.validate_script(script)
        if not valid:
            return ScriptExecutionResult(
                success=False, error_message=error_msg
            )

        script_path = Path(script.script_path).resolve()
        cmd = self._build_command(script_path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=script.timeout,
            )

            stdout = self._truncate_output(result.stdout)
            stderr = self._truncate_output(result.stderr)

            return ScriptExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except subprocess.TimeoutExpired:
            return ScriptExecutionResult(
                success=False,
                error_message=f"タイムアウト ({script.timeout}秒)",
            )
        except OSError as e:
            return ScriptExecutionResult(
                success=False,
                error_message=f"実行エラー: {e}",
            )

    def execute_async(
        self,
        script: AppScript,
        execution_id: int,
        db: "Database",  # noqa: F821
    ) -> None:
        """スクリプトを非同期実行する。

        バックグラウンドスレッドで実行し、完了時にDBを更新する。

        Args:
            script: スクリプト情報
            execution_id: 実行レコードID
            db: Databaseインスタンス
        """
        thread = threading.Thread(
            target=self._run_async,
            args=(script, execution_id, db),
            daemon=True,
        )
        thread.start()

    def _run_async(
        self,
        script: AppScript,
        execution_id: int,
        db: "Database",  # noqa: F821
    ) -> None:
        """非同期実行の内部処理。"""
        execution = db.get_script_execution(execution_id)
        if execution is None:
            logger.error(
                "実行レコードが見つかりません execution_id=%d", execution_id
            )
            return

        script_path = Path(script.script_path).resolve()
        cmd = self._build_command(script_path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=script.timeout,
            )

            execution.status = "completed" if result.returncode == 0 else "failed"
            execution.exit_code = result.returncode
            execution.stdout = self._truncate_output(result.stdout)
            execution.stderr = self._truncate_output(result.stderr)
        except subprocess.TimeoutExpired:
            execution.status = "timeout"
            execution.stderr = f"タイムアウト ({script.timeout}秒)"
        except OSError as e:
            execution.status = "failed"
            execution.stderr = f"実行エラー: {e}"

        execution.finished_at = datetime.now()

        try:
            db.update_script_execution(execution)
        except Exception:
            logger.exception(
                "実行結果の保存に失敗しました execution_id=%d", execution_id
            )

    def _build_command(self, script_path: Path) -> list[str]:
        """実行コマンドを構築する。

        Args:
            script_path: スクリプトファイルパス

        Returns:
            コマンドリスト
        """
        if self._is_windows:
            return ["cmd", "/c", str(script_path)]
        return ["bash", str(script_path)]

    def _is_in_allowed_dirs(self, script_path: Path) -> bool:
        """スクリプトパスが許可ディレクトリ内かチェックする。

        Args:
            script_path: 解決済みのスクリプトパス

        Returns:
            許可ディレクトリ内ならTrue
        """
        for base_dir in self.allowed_base_dirs:
            try:
                script_path.relative_to(base_dir)
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _truncate_output(output: str | None) -> str | None:
        """出力を最大サイズに切り詰める。

        Args:
            output: 出力文字列

        Returns:
            切り詰め後の文字列
        """
        if output is None:
            return None
        if len(output) > MAX_OUTPUT_SIZE:
            return output[:MAX_OUTPUT_SIZE] + "\n... (truncated)"
        return output
