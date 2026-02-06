"""log_manager のテスト"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services.log_manager import (
    LOG_TYPES,
    DailyDirectoryHandler,
    LogConfig,
    LogManager,
    get_logger,
    setup_logging,
    shutdown_logging,
)


class TestLogConfig:
    """LogConfig のテスト"""

    def test_from_dict_default(self, tmp_path: Path):
        """デフォルト設定で生成できる"""
        config = LogConfig.from_dict({}, tmp_path)

        assert config.level == "INFO"
        assert config.directory == tmp_path / "logs"
        assert config.console_enabled is True
        assert config.max_size_bytes == 10 * 1024 * 1024
        assert config.backup_count == 3
        assert config.retention_days == 7
        assert config.archive_enabled is True
        assert config.archive_retention_days == 30
        assert config.max_folder_size_bytes == 500 * 1024 * 1024

    def test_from_dict_custom(self, tmp_path: Path):
        """カスタム設定で生成できる"""
        config_dict = {
            "level": "DEBUG",
            "directory": "custom_logs",
            "console": {"enabled": False},
            "max_size_mb": 20,
            "backup_count": 5,
            "retention_days": 14,
            "archive": {
                "enabled": False,
                "directory": "old_logs",
                "retention_days": 60,
            },
            "max_folder_size_mb": 1000,
        }
        config = LogConfig.from_dict(config_dict, tmp_path)

        assert config.level == "DEBUG"
        assert config.directory == tmp_path / "custom_logs"
        assert config.console_enabled is False
        assert config.max_size_bytes == 20 * 1024 * 1024
        assert config.backup_count == 5
        assert config.retention_days == 14
        assert config.archive_enabled is False
        assert config.archive_directory == "old_logs"
        assert config.archive_retention_days == 60

    def test_from_dict_absolute_path(self, tmp_path: Path):
        """絶対パスが正しく処理される"""
        # プラットフォーム非依存のテスト
        absolute_path = tmp_path / "absolute_logs"
        config = LogConfig.from_dict({"directory": str(absolute_path)}, tmp_path)

        # 絶対パスはそのまま使用される（base_pathと結合されない）
        assert config.directory == absolute_path


class TestDailyDirectoryHandler:
    """DailyDirectoryHandler のテスト"""

    def test_creates_daily_directory(self, tmp_path: Path):
        """日付ディレクトリが作成される"""
        handler = DailyDirectoryHandler(
            base_directory=tmp_path,
            log_type="app",
        )

        today = datetime.now().strftime("%Y-%m-%d")
        expected_dir = tmp_path / today
        expected_file = expected_dir / "app.log"

        assert expected_dir.exists()
        assert handler.baseFilename == str(expected_file)

        handler.close()

    def test_writes_to_correct_file(self, tmp_path: Path):
        """正しいファイルに書き込まれる"""
        handler = DailyDirectoryHandler(
            base_directory=tmp_path,
            log_type="resource",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="resource",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        handler.close()

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / today / "resource.log"
        assert log_file.exists()
        assert "Test message" in log_file.read_text()


class TestLogManager:
    """LogManager のテスト"""

    @pytest.fixture
    def log_manager(self, tmp_path: Path) -> LogManager:
        """テスト用 LogManager"""
        config = LogConfig.from_dict({}, tmp_path)
        return LogManager(config)

    def test_archive_path(self, log_manager: LogManager, tmp_path: Path):
        """archive_path が正しい"""
        expected = tmp_path / "logs" / "archive"
        assert log_manager.archive_path == expected

    def test_archive_old_directories(self, tmp_path: Path):
        """古いディレクトリがアーカイブされる"""
        config = LogConfig.from_dict({"retention_days": 7}, tmp_path)
        manager = LogManager(config)

        # 10日前のディレクトリを作成
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_dir = config.directory / old_date
        old_dir.mkdir(parents=True)
        (old_dir / "app.log").write_text("old log")

        # 今日のディレクトリを作成
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = config.directory / today
        today_dir.mkdir(parents=True)
        (today_dir / "app.log").write_text("today log")

        # アーカイブ実行
        archived = manager.archive()

        assert archived == 1
        assert not old_dir.exists()
        assert (manager.archive_path / f"{old_date}.tar.gz").exists()
        assert today_dir.exists()  # 今日のディレクトリは残る

    def test_cleanup_old_archives(self, tmp_path: Path):
        """古いアーカイブが削除される"""
        config = LogConfig.from_dict(
            {"archive": {"retention_days": 30}},
            tmp_path,
        )
        manager = LogManager(config)

        # アーカイブディレクトリを作成
        manager.archive_path.mkdir(parents=True)

        # 40日前のアーカイブを作成
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        old_archive = manager.archive_path / f"{old_date}.tar.gz"
        old_archive.write_bytes(b"dummy")

        # 10日前のアーカイブを作成
        recent_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        recent_archive = manager.archive_path / f"{recent_date}.tar.gz"
        recent_archive.write_bytes(b"dummy")

        # クリーンアップ実行
        _, deleted_archives = manager.cleanup()

        assert deleted_archives == 1
        assert not old_archive.exists()
        assert recent_archive.exists()

    def test_enforce_size_limit(self, tmp_path: Path):
        """フォルダサイズ上限が適用される"""
        # 1MB上限で設定
        config = LogConfig.from_dict({"max_folder_size_mb": 1}, tmp_path)
        manager = LogManager(config)

        # 500KB x 3 = 1.5MB のファイルを作成（上限超過）
        config.directory.mkdir(parents=True)
        for i in range(3):
            date = (datetime.now() - timedelta(days=i + 1)).strftime("%Y-%m-%d")
            daily_dir = config.directory / date
            daily_dir.mkdir()
            (daily_dir / "app.log").write_bytes(b"x" * (500 * 1024))

        # サイズ制限適用
        deleted = manager.enforce_size_limit()

        assert deleted > 0
        # 1MB以下になっているはず
        stats = manager.get_statistics()
        assert stats["total_size_bytes"] <= 1 * 1024 * 1024

    def test_get_statistics(self, tmp_path: Path):
        """統計情報を取得できる"""
        config = LogConfig.from_dict({}, tmp_path)
        manager = LogManager(config)

        # ログディレクトリを作成
        config.directory.mkdir(parents=True)
        today = datetime.now().strftime("%Y-%m-%d")
        daily_dir = config.directory / today
        daily_dir.mkdir()
        (daily_dir / "app.log").write_text("test log content")

        stats = manager.get_statistics()

        assert "total_size_bytes" in stats
        assert "total_size_mb" in stats
        assert "daily_directories" in stats
        assert stats["daily_directories"] == 1


class TestSetupLogging:
    """setup_logging のテスト"""

    def teardown_method(self):
        """各テスト後にシャットダウン"""
        shutdown_logging()

    def test_setup_logging_default(self, tmp_path: Path):
        """デフォルト設定で初期化できる"""
        manager = setup_logging(base_path=tmp_path)

        assert manager is not None
        assert (tmp_path / "logs").exists()

    def test_setup_logging_custom(self, tmp_path: Path):
        """カスタム設定で初期化できる"""
        config = {
            "level": "DEBUG",
            "directory": "custom_logs",
        }
        manager = setup_logging(config=config, base_path=tmp_path)

        assert manager is not None
        assert (tmp_path / "custom_logs").exists()


class TestGetLogger:
    """get_logger のテスト"""

    def teardown_method(self):
        """各テスト後にシャットダウン"""
        shutdown_logging()

    def test_get_logger_valid_types(self, tmp_path: Path):
        """有効なログ種別でロガーを取得できる"""
        setup_logging(base_path=tmp_path)

        for log_type in LOG_TYPES:
            logger = get_logger(log_type)
            assert logger is not None
            assert logger.name == log_type

    def test_get_logger_invalid_type(self, tmp_path: Path):
        """無効なログ種別でエラーが発生する"""
        setup_logging(base_path=tmp_path)

        with pytest.raises(ValueError, match="不正なログ種別"):
            get_logger("invalid")  # type: ignore

    def test_get_logger_auto_init(self, tmp_path: Path, monkeypatch):
        """未初期化でも自動初期化される"""
        monkeypatch.chdir(tmp_path)
        shutdown_logging()

        logger = get_logger("app")
        assert logger is not None
