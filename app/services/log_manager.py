"""ログ管理サービス

ログの出力・ローテーション・アーカイブ・クリーンアップを管理する。

ディレクトリ構成:
    logs/
    ├── YYYY-MM-DD/
    │   ├── app.log
    │   ├── resource.log
    │   ├── auth.log
    │   ├── access.log
    │   └── install.log
    └── archive/
        └── YYYY-MM-DD.tar.gz
"""

import logging
import shutil
import tarfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

# ログ種別
LogType = Literal["app", "resource", "auth", "access", "install"]
LOG_TYPES: list[LogType] = ["app", "resource", "auth", "access", "install"]

# デフォルト設定
DEFAULT_CONFIG = {
    "level": "INFO",
    "directory": "logs",
    "console": {"enabled": True},
    "max_size_mb": 10,
    "backup_count": 3,
    "retention_days": 7,
    "archive": {
        "enabled": True,
        "directory": "archive",
        "retention_days": 30,
    },
    "max_folder_size_mb": 500,
    "maintenance_interval_hours": 24,
}

# フォーマット
LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s"
ACCESS_LOG_FORMAT = "%(asctime)s.%(msecs)03d %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class LogConfig:
    """ログ設定"""

    level: str
    directory: Path
    console_enabled: bool
    max_size_bytes: int
    backup_count: int
    retention_days: int
    archive_enabled: bool
    archive_directory: str
    archive_retention_days: int
    max_folder_size_bytes: int
    maintenance_interval_hours: int

    @classmethod
    def from_dict(cls, config: dict, base_path: Path) -> "LogConfig":
        """辞書から設定を生成する。

        Args:
            config: 設定辞書
            base_path: ベースパス（相対パス解決用）

        Returns:
            LogConfig インスタンス
        """
        # デフォルト値とマージ
        merged = {**DEFAULT_CONFIG, **config}
        if "console" in config:
            merged["console"] = {**DEFAULT_CONFIG["console"], **config["console"]}
        if "archive" in config:
            merged["archive"] = {**DEFAULT_CONFIG["archive"], **config["archive"]}

        # ディレクトリパスの解決
        directory = Path(merged["directory"])
        if not directory.is_absolute():
            directory = base_path / directory

        return cls(
            level=merged["level"],
            directory=directory,
            console_enabled=merged["console"]["enabled"],
            max_size_bytes=merged["max_size_mb"] * 1024 * 1024,
            backup_count=merged["backup_count"],
            retention_days=merged["retention_days"],
            archive_enabled=merged["archive"]["enabled"],
            archive_directory=merged["archive"]["directory"],
            archive_retention_days=merged["archive"]["retention_days"],
            max_folder_size_bytes=merged["max_folder_size_mb"] * 1024 * 1024,
            maintenance_interval_hours=merged["maintenance_interval_hours"],
        )


class DailyDirectoryHandler(RotatingFileHandler):
    """日付ディレクトリにログを出力するハンドラー

    logs/YYYY-MM-DD/{log_type}.log 形式で出力する。
    日付が変わると新しいディレクトリに出力先を切り替える。
    """

    def __init__(
        self,
        base_directory: Path,
        log_type: LogType,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 3,
        encoding: str = "utf-8",
    ):
        """初期化

        Args:
            base_directory: ログのベースディレクトリ
            log_type: ログ種別（app, resource, auth）
            max_bytes: ファイルサイズ上限
            backup_count: 世代数
            encoding: エンコーディング
        """
        self.base_directory = base_directory
        self.log_type = log_type
        self._current_date: str | None = None

        # 初期ファイルパスを設定
        file_path = self._get_current_file_path()

        super().__init__(
            filename=str(file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
        )

    def _get_current_file_path(self) -> Path:
        """現在の日付に対応するファイルパスを取得する。"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._current_date = today

        daily_dir = self.base_directory / today
        daily_dir.mkdir(parents=True, exist_ok=True)

        return daily_dir / f"{self.log_type}.log"

    def emit(self, record: logging.LogRecord) -> None:
        """ログレコードを出力する。

        日付が変わった場合はファイルを切り替える。
        """
        today = datetime.now().strftime("%Y-%m-%d")

        if today != self._current_date:
            # 日付が変わったのでファイルを切り替え
            self.close()
            new_path = self._get_current_file_path()
            self.baseFilename = str(new_path)
            self.stream = self._open()

        super().emit(record)


class LogManager:
    """ログファイルの管理クラス

    ローテーション、アーカイブ、クリーンアップを担当する。
    """

    def __init__(self, config: LogConfig):
        """初期化

        Args:
            config: ログ設定
        """
        self.config = config

    @property
    def archive_path(self) -> Path:
        """アーカイブディレクトリのパス"""
        return self.config.directory / self.config.archive_directory

    def run_maintenance(self) -> dict[str, int]:
        """メンテナンス処理を実行する。

        アーカイブ、クリーンアップ、サイズ制限の適用を行う。

        Returns:
            処理結果の統計
        """
        stats = {
            "archived": 0,
            "deleted_logs": 0,
            "deleted_archives": 0,
        }

        if self.config.archive_enabled:
            stats["archived"] = self.archive()

        stats["deleted_logs"], stats["deleted_archives"] = self.cleanup()
        self.enforce_size_limit()

        return stats

    def archive(self) -> int:
        """古いログディレクトリをアーカイブする。

        retention_days を超えた日付ディレクトリを圧縮してアーカイブへ移動する。

        Returns:
            アーカイブした日付ディレクトリ数
        """
        if not self.config.archive_enabled:
            return 0

        archived_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)

        # アーカイブディレクトリを作成
        self.archive_path.mkdir(parents=True, exist_ok=True)

        for daily_dir in self._get_daily_directories():
            dir_date = self._parse_date_from_path(daily_dir)
            if dir_date is None:
                continue

            if dir_date < cutoff_date:
                archive_file = self.archive_path / f"{daily_dir.name}.tar.gz"
                self._create_archive(daily_dir, archive_file)
                shutil.rmtree(daily_dir)
                archived_count += 1

        return archived_count

    def cleanup(self) -> tuple[int, int]:
        """期限切れファイルを削除する。

        Returns:
            (削除したログディレクトリ数, 削除したアーカイブ数)
        """
        deleted_logs = 0
        deleted_archives = 0

        # アーカイブの削除
        if self.config.archive_enabled and self.archive_path.exists():
            cutoff_date = datetime.now() - timedelta(
                days=self.config.archive_retention_days
            )

            for archive_file in self.archive_path.glob("*.tar.gz"):
                # ファイル名から日付を取得（YYYY-MM-DD.tar.gz）
                date_str = archive_file.stem.replace(".tar", "")
                archive_date = self._parse_date_string(date_str)

                if archive_date is not None and archive_date < cutoff_date:
                    archive_file.unlink()
                    deleted_archives += 1

        return deleted_logs, deleted_archives

    def enforce_size_limit(self) -> int:
        """フォルダサイズ上限を適用する。

        上限を超えた場合、古いファイルから削除する。

        Returns:
            削除したファイル/ディレクトリ数
        """
        deleted_count = 0
        current_size = self._get_directory_size(self.config.directory)

        if current_size <= self.config.max_folder_size_bytes:
            return 0

        # アーカイブから古い順に削除
        if self.archive_path.exists():
            archives = sorted(self.archive_path.glob("*.tar.gz"))
            for archive_file in archives:
                if current_size <= self.config.max_folder_size_bytes:
                    break
                file_size = archive_file.stat().st_size
                archive_file.unlink()
                current_size -= file_size
                deleted_count += 1

        # まだ超過している場合は古いログディレクトリから削除
        if current_size > self.config.max_folder_size_bytes:
            daily_dirs = sorted(self._get_daily_directories())
            # 今日のディレクトリは除外
            today = datetime.now().strftime("%Y-%m-%d")

            for daily_dir in daily_dirs:
                if daily_dir.name == today:
                    continue
                if current_size <= self.config.max_folder_size_bytes:
                    break
                dir_size = self._get_directory_size(daily_dir)
                shutil.rmtree(daily_dir)
                current_size -= dir_size
                deleted_count += 1

        return deleted_count

    def get_statistics(self) -> dict:
        """ログディレクトリの統計情報を取得する。

        Returns:
            統計情報の辞書
        """
        total_size = self._get_directory_size(self.config.directory)
        daily_dirs = list(self._get_daily_directories())
        archive_count = (
            len(list(self.archive_path.glob("*.tar.gz")))
            if self.archive_path.exists()
            else 0
        )

        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "daily_directories": len(daily_dirs),
            "archive_count": archive_count,
            "max_size_mb": self.config.max_folder_size_bytes // (1024 * 1024),
            "usage_percent": round(
                total_size / self.config.max_folder_size_bytes * 100, 1
            )
            if self.config.max_folder_size_bytes > 0
            else 0,
        }

    def _get_daily_directories(self) -> list[Path]:
        """日付ディレクトリの一覧を取得する。"""
        if not self.config.directory.exists():
            return []

        directories = []
        for item in self.config.directory.iterdir():
            if item.is_dir() and self._is_date_directory(item):
                directories.append(item)

        return directories

    def _is_date_directory(self, path: Path) -> bool:
        """日付形式のディレクトリかどうかを判定する。"""
        return self._parse_date_string(path.name) is not None

    def _parse_date_from_path(self, path: Path) -> datetime | None:
        """パスから日付を取得する。"""
        return self._parse_date_string(path.name)

    def _parse_date_string(self, date_str: str) -> datetime | None:
        """日付文字列をパースする。"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

    def _create_archive(self, source_dir: Path, archive_file: Path) -> None:
        """ディレクトリをtar.gzアーカイブにする。"""
        with tarfile.open(archive_file, "w:gz") as tar:
            tar.add(source_dir, arcname=source_dir.name)

    def _get_directory_size(self, directory: Path) -> int:
        """ディレクトリの合計サイズを取得する。"""
        if not directory.exists():
            return 0

        total_size = 0
        for item in directory.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size

        return total_size


class MaintenanceScheduler:
    """ログメンテナンスの定期実行スケジューラ

    threading.Timer を使って一定間隔で run_maintenance() を実行する。
    デーモンスレッドで動作するため、アプリ終了時に自動停止する。
    """

    def __init__(self, log_manager: LogManager, interval_hours: int):
        """初期化

        Args:
            log_manager: LogManager インスタンス
            interval_hours: 実行間隔（時間）。0の場合は無効。
        """
        self._log_manager = log_manager
        self._interval_seconds = interval_hours * 3600
        self._timer: threading.Timer | None = None
        self._running = False
        self._next_run: datetime | None = None
        self._logger = logging.getLogger("app")

    @property
    def is_running(self) -> bool:
        """スケジューラが実行中かどうか"""
        return self._running

    @property
    def next_run(self) -> datetime | None:
        """次回実行予定時刻"""
        return self._next_run

    @property
    def interval_hours(self) -> int:
        """実行間隔（時間）"""
        return self._interval_seconds // 3600

    def start(self) -> None:
        """スケジューラを開始する。"""
        if self._interval_seconds <= 0:
            return
        self._running = True
        self._schedule_next()
        self._logger.info(
            "ログメンテナンススケジューラを開始しました interval=%dh",
            self.interval_hours,
        )

    def stop(self) -> None:
        """スケジューラを停止する。"""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._next_run = None

    def _schedule_next(self) -> None:
        """次回実行をスケジュールする。"""
        if not self._running:
            return
        self._next_run = datetime.now() + timedelta(seconds=self._interval_seconds)
        self._timer = threading.Timer(self._interval_seconds, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self) -> None:
        """メンテナンスを実行し、次回をスケジュールする。"""
        try:
            result = self._log_manager.run_maintenance()
            self._logger.info("定期メンテナンスを実行しました result=%s", result)
        except Exception:
            self._logger.exception("定期メンテナンスでエラーが発生しました")
        self._schedule_next()


# モジュールレベルの状態
_config: LogConfig | None = None
_log_manager: LogManager | None = None
_scheduler: MaintenanceScheduler | None = None
_handlers: dict[LogType, DailyDirectoryHandler] = {}
_initialized: bool = False


def setup_logging(
    config: dict | None = None,
    base_path: Path | None = None,
) -> LogManager:
    """ロギングを初期化する。

    Args:
        config: ログ設定辞書。Noneの場合はデフォルト設定を使用。
        base_path: ベースパス。Noneの場合はカレントディレクトリ。

    Returns:
        LogManager インスタンス
    """
    global _config, _log_manager, _scheduler, _handlers, _initialized

    if base_path is None:
        base_path = Path.cwd()

    # 設定を生成
    _config = LogConfig.from_dict(config or {}, base_path)

    # ログレベルを設定
    log_level = getattr(logging, _config.level.upper(), logging.INFO)

    # フォーマッターを作成
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    access_formatter = logging.Formatter(ACCESS_LOG_FORMAT, DATE_FORMAT)

    # 各ログ種別のハンドラーを設定
    for log_type in LOG_TYPES:
        logger = logging.getLogger(log_type)
        logger.setLevel(log_level)
        logger.handlers.clear()

        # ファイルハンドラー
        handler = DailyDirectoryHandler(
            base_directory=_config.directory,
            log_type=log_type,
            max_bytes=_config.max_size_bytes,
            backup_count=_config.backup_count,
        )
        current_formatter = access_formatter if log_type == "access" else formatter
        handler.setFormatter(current_formatter)
        handler.setLevel(log_level)
        logger.addHandler(handler)
        _handlers[log_type] = handler

        # コンソールハンドラー
        if _config.console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(current_formatter)
            console_handler.setLevel(log_level)
            logger.addHandler(console_handler)

    # LogManager を初期化
    _log_manager = LogManager(_config)
    _initialized = True

    # 起動時のメンテナンス実行
    _log_manager.run_maintenance()

    # 定期メンテナンススケジューラの開始
    if _config.maintenance_interval_hours > 0:
        _scheduler = MaintenanceScheduler(
            _log_manager, _config.maintenance_interval_hours
        )
        _scheduler.start()

    return _log_manager


def get_logger(name: LogType) -> logging.Logger:
    """指定された種別のロガーを取得する。

    Args:
        name: ログ種別（"app", "resource", "auth", "access", "install"）

    Returns:
        Logger インスタンス

    Raises:
        ValueError: 不正なログ種別が指定された場合
    """
    if name not in LOG_TYPES:
        raise ValueError(f"不正なログ種別です: {name}. 有効な値: {LOG_TYPES}")

    if not _initialized:
        # 未初期化の場合はデフォルト設定で初期化
        setup_logging()

    return logging.getLogger(name)


def get_log_manager() -> LogManager | None:
    """LogManager インスタンスを取得する。

    Returns:
        LogManager インスタンス。未初期化の場合は None。
    """
    return _log_manager


def get_scheduler() -> MaintenanceScheduler | None:
    """MaintenanceScheduler インスタンスを取得する。

    Returns:
        MaintenanceScheduler インスタンス。未初期化の場合は None。
    """
    return _scheduler


def list_log_dates() -> list[str]:
    """利用可能なログ日付一覧を取得する（降順）。

    Returns:
        日付文字列のリスト（例: ["2025-01-15", "2025-01-14"]）
    """
    if _config is None or not _config.directory.exists():
        return []

    dates = []
    for item in _config.directory.iterdir():
        if item.is_dir():
            try:
                datetime.strptime(item.name, "%Y-%m-%d")
                dates.append(item.name)
            except ValueError:
                continue

    return sorted(dates, reverse=True)


def list_log_files(date: str) -> list[str]:
    """指定日付のログファイル一覧を取得する。

    Args:
        date: 日付文字列（YYYY-MM-DD）

    Returns:
        ログ種別名のリスト（例: ["app", "auth", "access"]）
    """
    if _config is None:
        return []

    daily_dir = _config.directory / date
    if not daily_dir.exists():
        return []

    files = []
    for log_file in sorted(daily_dir.glob("*.log")):
        files.append(log_file.stem)

    return files


def read_log_tail(date: str, log_type: str, lines: int = 500) -> list[str]:
    """ログファイルの末尾N行を取得する。

    Args:
        date: 日付文字列（YYYY-MM-DD）
        log_type: ログ種別
        lines: 取得する行数

    Returns:
        ログ行のリスト
    """
    if _config is None:
        return []

    log_file = _config.directory / date / f"{log_type}.log"
    if not log_file.exists():
        return []

    all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return all_lines[-lines:]


def shutdown_logging() -> None:
    """ロギングをシャットダウンする。"""
    global _initialized, _handlers, _scheduler

    if _scheduler is not None:
        _scheduler.stop()
        _scheduler = None

    for handler in _handlers.values():
        handler.close()

    _handlers.clear()
    _initialized = False
