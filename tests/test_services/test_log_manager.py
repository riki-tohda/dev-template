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
    MaintenanceScheduler,
    get_archive_file_path,
    get_log_file_metadata,
    get_log_file_path,
    get_logger,
    get_scheduler,
    list_archive_files,
    list_log_dates,
    list_log_files,
    list_log_files_with_metadata,
    get_date_range_statistics,
    read_log_tail,
    read_log_with_levels,
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


class TestMaintenanceScheduler:
    """MaintenanceScheduler のテスト"""

    @pytest.fixture
    def log_manager(self, tmp_path: Path) -> LogManager:
        """テスト用 LogManager"""
        config = LogConfig.from_dict({}, tmp_path)
        return LogManager(config)

    def test_start_and_stop(self, log_manager: LogManager):
        """スケジューラの開始と停止"""
        scheduler = MaintenanceScheduler(log_manager, interval_hours=1)

        assert not scheduler.is_running
        assert scheduler.next_run is None

        scheduler.start()
        assert scheduler.is_running
        assert scheduler.next_run is not None
        assert scheduler.interval_hours == 1

        scheduler.stop()
        assert not scheduler.is_running
        assert scheduler.next_run is None

    def test_zero_interval_disables(self, log_manager: LogManager):
        """interval_hours=0 ではスケジューラが開始されない"""
        scheduler = MaintenanceScheduler(log_manager, interval_hours=0)
        scheduler.start()
        assert not scheduler.is_running

    def test_next_run_is_future(self, log_manager: LogManager):
        """次回実行予定時刻は未来の時刻"""
        scheduler = MaintenanceScheduler(log_manager, interval_hours=1)
        scheduler.start()

        assert scheduler.next_run is not None
        assert scheduler.next_run > datetime.now()

        scheduler.stop()

    def test_setup_logging_creates_scheduler(self, tmp_path: Path):
        """setup_logging で interval > 0 の場合スケジューラが作成される"""
        try:
            setup_logging(
                config={"maintenance_interval_hours": 1},
                base_path=tmp_path,
            )
            scheduler = get_scheduler()
            assert scheduler is not None
            assert scheduler.is_running
        finally:
            shutdown_logging()

    def test_setup_logging_no_scheduler_when_zero(self, tmp_path: Path):
        """setup_logging で interval=0 の場合スケジューラが作成されない"""
        try:
            setup_logging(
                config={"maintenance_interval_hours": 0},
                base_path=tmp_path,
            )
            scheduler = get_scheduler()
            assert scheduler is None
        finally:
            shutdown_logging()

    def test_shutdown_stops_scheduler(self, tmp_path: Path):
        """shutdown_logging でスケジューラが停止される"""
        setup_logging(
            config={"maintenance_interval_hours": 1},
            base_path=tmp_path,
        )
        scheduler = get_scheduler()
        assert scheduler is not None
        assert scheduler.is_running

        shutdown_logging()
        assert not scheduler.is_running
        assert get_scheduler() is None


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


class TestNewLogTypes:
    """access/install ログ種別のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_access_in_log_types(self):
        """access が LOG_TYPES に含まれる"""
        assert "access" in LOG_TYPES

    def test_install_in_log_types(self):
        """install が LOG_TYPES に含まれる"""
        assert "install" in LOG_TYPES

    def test_get_access_logger(self, tmp_path: Path):
        """access ロガーを取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("access")
        assert logger is not None
        assert logger.name == "access"

    def test_get_install_logger(self, tmp_path: Path):
        """install ロガーを取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("install")
        assert logger is not None
        assert logger.name == "install"

    def test_access_log_writes_to_file(self, tmp_path: Path):
        """access ロガーがファイルに書き込める"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("access")
        logger.info("test access entry")

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / "logs" / today / "access.log"
        assert log_file.exists()
        assert "test access entry" in log_file.read_text()

    def test_install_log_writes_to_file(self, tmp_path: Path):
        """install ロガーがファイルに書き込める"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("install")
        logger.info("test install entry")

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / "logs" / today / "install.log"
        assert log_file.exists()
        assert "test install entry" in log_file.read_text()


class TestLogViewerFunctions:
    """ログビューア関数のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_list_log_dates(self, tmp_path: Path):
        """日付一覧を取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test entry")

        dates = list_log_dates()
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in dates

    def test_list_log_dates_sorted_descending(self, tmp_path: Path):
        """日付一覧が降順にソートされる"""
        setup_logging(base_path=tmp_path)

        # 複数の日付ディレクトリを作成
        logs_dir = tmp_path / "logs"
        (logs_dir / "2025-01-01").mkdir(parents=True, exist_ok=True)
        (logs_dir / "2025-01-03").mkdir(parents=True, exist_ok=True)
        (logs_dir / "2025-01-02").mkdir(parents=True, exist_ok=True)

        dates = list_log_dates()
        # 降順であること（今日の日付も含む場合があるのでサブセットで確認）
        test_dates = [d for d in dates if d.startswith("2025-01")]
        assert test_dates == sorted(test_dates, reverse=True)

    def test_list_log_files(self, tmp_path: Path):
        """指定日付のファイル一覧を取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test entry")

        today = datetime.now().strftime("%Y-%m-%d")
        files = list_log_files(today)
        assert "app" in files

    def test_list_log_files_nonexistent_date(self, tmp_path: Path):
        """存在しない日付は空リストを返す"""
        setup_logging(base_path=tmp_path)
        files = list_log_files("1999-01-01")
        assert files == []

    def test_read_log_tail(self, tmp_path: Path):
        """ログ末尾を取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        for i in range(10):
            logger.info("line %d", i)

        today = datetime.now().strftime("%Y-%m-%d")
        lines = read_log_tail(today, "app", lines=5)
        assert len(lines) == 5
        assert "line 9" in lines[-1]

    def test_read_log_tail_nonexistent_file(self, tmp_path: Path):
        """存在しないファイルは空リストを返す"""
        setup_logging(base_path=tmp_path)
        lines = read_log_tail("1999-01-01", "app")
        assert lines == []

    def test_read_log_tail_default_lines(self, tmp_path: Path):
        """デフォルト行数で取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("single line")

        today = datetime.now().strftime("%Y-%m-%d")
        lines = read_log_tail(today, "app")
        assert len(lines) >= 1


class TestLogFileMetadata:
    """get_log_file_metadata のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_existing_file(self, tmp_path: Path):
        """存在するファイルのメタデータを取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test entry")

        today = datetime.now().strftime("%Y-%m-%d")
        meta = get_log_file_metadata(today, "app")

        assert meta is not None
        assert meta["size_bytes"] > 0
        assert meta["line_count"] >= 1
        assert "modified_time" in meta

    def test_nonexistent_file(self, tmp_path: Path):
        """存在しないファイルは None を返す"""
        setup_logging(base_path=tmp_path)
        meta = get_log_file_metadata("1999-01-01", "app")
        assert meta is None

    def test_error_count(self, tmp_path: Path):
        """ERROR カウントが正しい"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("normal entry")
        logger.error("error entry 1")
        logger.error("error entry 2")
        logger.warning("warning entry")

        today = datetime.now().strftime("%Y-%m-%d")
        meta = get_log_file_metadata(today, "app")

        assert meta is not None
        assert meta["error_count"] == 2
        assert meta["warning_count"] == 1

    def test_access_log_no_level_count(self, tmp_path: Path):
        """access ログではレベルカウントしない"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("access")
        logger.info("access entry")

        today = datetime.now().strftime("%Y-%m-%d")
        meta = get_log_file_metadata(today, "access")

        assert meta is not None
        assert meta["error_count"] == 0
        assert meta["warning_count"] == 0


class TestListLogFilesWithMetadata:
    """list_log_files_with_metadata のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_returns_metadata(self, tmp_path: Path):
        """メタデータ付きファイル一覧を取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test entry")

        today = datetime.now().strftime("%Y-%m-%d")
        files = list_log_files_with_metadata(today)

        assert len(files) >= 1
        f = files[0]
        assert "type" in f
        assert "name" in f
        assert "size_bytes" in f
        assert "line_count" in f

    def test_empty_date(self, tmp_path: Path):
        """存在しない日付は空リストを返す"""
        setup_logging(base_path=tmp_path)
        files = list_log_files_with_metadata("1999-01-01")
        assert files == []


class TestDateRangeStatistics:
    """get_date_range_statistics のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_single_day(self, tmp_path: Path):
        """単日の統計を取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("info entry")
        logger.error("error entry")

        today = datetime.now().strftime("%Y-%m-%d")
        stats = get_date_range_statistics(today, today)

        assert stats["total_files"] >= 1
        assert stats["total_size_bytes"] > 0
        assert stats["info_count"] >= 1
        assert stats["error_count"] >= 1

    def test_multiple_days(self, tmp_path: Path):
        """複数日の統計を取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test entry")

        # 追加の日付ディレクトリを作成
        logs_dir = tmp_path / "logs"
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_dir = logs_dir / yesterday
        yesterday_dir.mkdir(parents=True, exist_ok=True)
        (yesterday_dir / "app.log").write_text(
            "2025-01-01 12:00:00.000 [INFO] app: test\n"
        )

        today = datetime.now().strftime("%Y-%m-%d")
        stats = get_date_range_statistics(yesterday, today)

        assert stats["total_files"] >= 2

    def test_empty_range(self, tmp_path: Path):
        """空の範囲はゼロ統計を返す"""
        setup_logging(base_path=tmp_path)
        stats = get_date_range_statistics("1999-01-01", "1999-01-02")

        assert stats["total_files"] == 0
        assert stats["total_size_bytes"] == 0


class TestListArchiveFiles:
    """list_archive_files のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_no_archives(self, tmp_path: Path):
        """アーカイブがない場合は空リストを返す"""
        setup_logging(base_path=tmp_path)
        archives = list_archive_files()
        assert archives == []

    def test_with_archives(self, tmp_path: Path):
        """アーカイブファイルを取得できる"""
        setup_logging(base_path=tmp_path)

        # アーカイブディレクトリにダミーファイルを作成
        archive_dir = tmp_path / "logs" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "2025-01-01.tar.gz").write_bytes(b"dummy")
        (archive_dir / "2025-01-02.tar.gz").write_bytes(b"dummy2")

        archives = list_archive_files()
        assert len(archives) == 2
        # 降順
        assert archives[0]["date"] == "2025-01-02"
        assert archives[1]["date"] == "2025-01-01"
        assert "filename" in archives[0]
        assert "size_bytes" in archives[0]


class TestReadLogWithLevels:
    """read_log_with_levels のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_standard_format(self, tmp_path: Path):
        """標準形式のログをパースできる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test message")
        logger.error("error message")

        today = datetime.now().strftime("%Y-%m-%d")
        entries = read_log_with_levels(today, "app")

        assert len(entries) >= 2
        # INFO エントリ（"test message"を含むもの）
        info_entries = [e for e in entries if e["level"] == "INFO" and e["message"] and "test message" in e["message"]]
        assert len(info_entries) >= 1
        info_entry = info_entries[0]
        assert info_entry["timestamp"] is not None
        assert info_entry["logger"] == "app"
        assert info_entry["line_number"] >= 1

        # ERROR エントリ
        error_entry = next(e for e in entries if e["level"] == "ERROR")
        assert "error message" in error_entry["message"]

    def test_access_format(self, tmp_path: Path):
        """アクセスログ形式をパースできる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("access")
        logger.info("method=GET path=/ status=200")

        today = datetime.now().strftime("%Y-%m-%d")
        entries = read_log_with_levels(today, "access")

        assert len(entries) >= 1
        entry = entries[0]
        assert entry["level"] == "ACCESS"
        assert entry["timestamp"] is not None
        assert "method=GET" in entry["message"]

    def test_unparseable_line(self, tmp_path: Path):
        """パース失敗行は level=None で返す"""
        setup_logging(base_path=tmp_path)

        # 直接パース不能な行を書き込み
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / "logs" / today / "app.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("not a standard log line\n")

        entries = read_log_with_levels(today, "app")
        assert len(entries) == 1
        assert entries[0]["level"] is None
        assert entries[0]["raw"] == "not a standard log line"

    def test_empty_log(self, tmp_path: Path):
        """存在しないログは空リストを返す"""
        setup_logging(base_path=tmp_path)
        entries = read_log_with_levels("1999-01-01", "app")
        assert entries == []


class TestLogFilePath:
    """get_log_file_path / get_archive_file_path のテスト"""

    def teardown_method(self):
        shutdown_logging()

    def test_get_log_file_path_exists(self, tmp_path: Path):
        """存在するログファイルのパスを取得できる"""
        setup_logging(base_path=tmp_path)
        logger = get_logger("app")
        logger.info("test")

        today = datetime.now().strftime("%Y-%m-%d")
        path = get_log_file_path(today, "app")
        assert path is not None
        assert path.exists()

    def test_get_log_file_path_not_exists(self, tmp_path: Path):
        """存在しないログファイルは None を返す"""
        setup_logging(base_path=tmp_path)
        path = get_log_file_path("1999-01-01", "app")
        assert path is None

    def test_get_archive_file_path_exists(self, tmp_path: Path):
        """存在するアーカイブのパスを取得できる"""
        setup_logging(base_path=tmp_path)
        archive_dir = tmp_path / "logs" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "2025-01-01.tar.gz").write_bytes(b"dummy")

        path = get_archive_file_path("2025-01-01.tar.gz")
        assert path is not None
        assert path.exists()

    def test_get_archive_file_path_not_exists(self, tmp_path: Path):
        """存在しないアーカイブは None を返す"""
        setup_logging(base_path=tmp_path)
        path = get_archive_file_path("1999-01-01.tar.gz")
        assert path is None
