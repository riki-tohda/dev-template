"""ScriptExecutorのテスト"""

import platform
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.models import AppScript, ScriptExecution
from app.services.script_executor import ScriptExecutor


def _make_script(
    tmp_path: Path,
    content: str,
    filename: str = "test.bat",
) -> tuple[Path, AppScript]:
    """テスト用スクリプトファイルとAppScriptを作成する。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    script_file = scripts_dir / filename
    script_file.write_text(content, encoding="utf-8")

    # Linuxでは実行権限を付与
    if platform.system() != "Windows":
        script_file.chmod(0o755)

    app_script = AppScript(
        id="test-script",
        app_id="test-app",
        name="Test Script",
        script_path=str(script_file),
        mode="sync",
        timeout=10,
    )
    return script_file, app_script


class TestValidateScript:
    """スクリプトバリデーションのテスト"""

    def test_valid_script(self, tmp_path: Path) -> None:
        """有効なスクリプト"""
        ext = ".bat" if platform.system() == "Windows" else ".sh"
        content = "@echo hello" if platform.system() == "Windows" else "#!/bin/bash\necho hello"
        _, script = _make_script(tmp_path, content, f"test{ext}")

        executor = ScriptExecutor([tmp_path])
        valid, msg = executor.validate_script(script)

        assert valid is True
        assert msg == ""

    def test_empty_path(self, tmp_path: Path) -> None:
        """空のスクリプトパス"""
        script = AppScript(
            id="test",
            app_id="app",
            name="Test",
            script_path="",
        )
        executor = ScriptExecutor([tmp_path])
        valid, msg = executor.validate_script(script)

        assert valid is False
        assert "パスが設定されていません" in msg

    def test_invalid_extension(self, tmp_path: Path) -> None:
        """不正な拡張子"""
        script_file = tmp_path / "scripts" / "test.py"
        script_file.parent.mkdir(exist_ok=True)
        script_file.write_text("print('hello')", encoding="utf-8")

        script = AppScript(
            id="test",
            app_id="app",
            name="Test",
            script_path=str(script_file),
        )
        executor = ScriptExecutor([tmp_path])
        valid, msg = executor.validate_script(script)

        assert valid is False
        assert "許可されていない拡張子" in msg

    def test_outside_allowed_dir(self, tmp_path: Path) -> None:
        """許可ディレクトリ外"""
        ext = ".bat" if platform.system() == "Windows" else ".sh"
        content = "@echo hello" if platform.system() == "Windows" else "#!/bin/bash\necho hello"

        # 別のディレクトリに作成
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        script_file = other_dir / f"test{ext}"
        script_file.write_text(content, encoding="utf-8")

        script = AppScript(
            id="test",
            app_id="app",
            name="Test",
            script_path=str(script_file),
        )
        # allowed_dir は tmp_path / "allowed" のみ
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        executor = ScriptExecutor([allowed_dir])
        valid, msg = executor.validate_script(script)

        assert valid is False
        assert "許可されたディレクトリ外" in msg

    def test_nonexistent_script(self, tmp_path: Path) -> None:
        """存在しないスクリプト"""
        ext = ".bat" if platform.system() == "Windows" else ".sh"
        script = AppScript(
            id="test",
            app_id="app",
            name="Test",
            script_path=str(tmp_path / "scripts" / f"nonexistent{ext}"),
        )
        executor = ScriptExecutor([tmp_path])
        valid, msg = executor.validate_script(script)

        assert valid is False
        assert "見つかりません" in msg


class TestExecuteSync:
    """同期実行のテスト"""

    def test_successful_execution(self, tmp_path: Path) -> None:
        """正常な実行"""
        if platform.system() == "Windows":
            content = "@echo off\necho hello"
            ext = ".bat"
        else:
            content = "#!/bin/bash\necho hello"
            ext = ".sh"

        _, script = _make_script(tmp_path, content, f"test{ext}")
        executor = ScriptExecutor([tmp_path])
        result = executor.execute_sync(script)

        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in (result.stdout or "")

    def test_failed_execution(self, tmp_path: Path) -> None:
        """失敗する実行"""
        if platform.system() == "Windows":
            content = "@echo off\nexit /b 1"
            ext = ".bat"
        else:
            content = "#!/bin/bash\nexit 1"
            ext = ".sh"

        _, script = _make_script(tmp_path, content, f"fail{ext}")
        executor = ScriptExecutor([tmp_path])
        result = executor.execute_sync(script)

        assert result.success is False
        assert result.exit_code == 1

    def test_timeout(self, tmp_path: Path) -> None:
        """タイムアウト"""
        if platform.system() == "Windows":
            content = "@echo off\nping -n 30 127.0.0.1 >nul"
            ext = ".bat"
        else:
            content = "#!/bin/bash\nsleep 30"
            ext = ".sh"

        _, script = _make_script(tmp_path, content, f"slow{ext}")
        script.timeout = 1
        executor = ScriptExecutor([tmp_path])
        result = executor.execute_sync(script)

        assert result.success is False
        assert "タイムアウト" in (result.error_message or "")

    def test_invalid_script_returns_error(self, tmp_path: Path) -> None:
        """無効なスクリプトはバリデーションエラー"""
        script = AppScript(
            id="test",
            app_id="app",
            name="Test",
            script_path="",
        )
        executor = ScriptExecutor([tmp_path])
        result = executor.execute_sync(script)

        assert result.success is False
        assert result.error_message is not None


class TestExecuteAsync:
    """非同期実行のテスト"""

    def test_async_execution(self, tmp_path: Path) -> None:
        """非同期実行がスレッドで動作する"""
        if platform.system() == "Windows":
            content = "@echo off\necho async_hello"
            ext = ".bat"
        else:
            content = "#!/bin/bash\necho async_hello"
            ext = ".sh"

        _, script = _make_script(tmp_path, content, f"async_test{ext}")

        mock_db = MagicMock()
        mock_execution = ScriptExecution(
            id=1,
            script_id="test-script",
            app_id="test-app",
            executed_by="admin",
            mode="async",
            status="running",
        )
        mock_db.get_script_execution.return_value = mock_execution

        executor = ScriptExecutor([tmp_path])
        executor.execute_async(script, 1, mock_db)

        # スレッドの完了を待つ
        time.sleep(3)

        mock_db.update_script_execution.assert_called_once()
        updated = mock_db.update_script_execution.call_args[0][0]
        assert updated.status in ("completed", "failed")


class TestTruncateOutput:
    """出力切り詰めのテスト"""

    def test_short_output_unchanged(self) -> None:
        """短い出力はそのまま"""
        result = ScriptExecutor._truncate_output("hello")
        assert result == "hello"

    def test_none_returns_none(self) -> None:
        """Noneはそのまま"""
        result = ScriptExecutor._truncate_output(None)
        assert result is None

    def test_long_output_truncated(self) -> None:
        """長い出力は切り詰められる"""
        long_text = "x" * (64 * 1024 + 100)
        result = ScriptExecutor._truncate_output(long_text)
        assert result is not None
        assert len(result) < len(long_text)
        assert "truncated" in result
