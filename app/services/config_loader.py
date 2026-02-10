"""設定ファイル読み込み・バリデーションモジュール"""

import logging
import os
import platform
import re
from pathlib import Path
from typing import Any

import yaml

from app.services.models import (
    AppInstallConfig,
    AppScript,
    Application,
    InitialUser,
    LoggingArchiveConfig,
    LoggingConfig,
    LoggingConsoleConfig,
    ResourceMonitorConfig,
    ServerConfig,
    SessionConfig,
    SystemConfig,
    WarningThresholds,
)

logger = logging.getLogger(__name__)

# OS識別キー
OS_WINDOWS = "windows"
OS_LINUX = "linux"


class ConfigValidationError(Exception):
    """設定バリデーションエラー"""

    pass


def get_current_os() -> str:
    """現在のOSを取得する。

    Returns:
        "windows" または "linux"
    """
    return OS_WINDOWS if platform.system() == "Windows" else OS_LINUX


def resolve_os_value(value: Any, current_os: str | None = None) -> Any:
    """OS別設定値を解決する。

    {"windows": "...", "linux": "..."} 形式の値は
    現在のOSに対応する値を返す。それ以外はそのまま返す。

    Args:
        value: 設定値（OS別辞書または単一値）
        current_os: OS識別キー（テスト用、Noneなら自動検出）

    Returns:
        解決後の値
    """
    if current_os is None:
        current_os = get_current_os()

    if isinstance(value, dict) and (OS_WINDOWS in value or OS_LINUX in value):
        resolved = value.get(current_os)
        if resolved is None:
            # 現在のOSのキーがない場合、もう一方のOSの値を使用
            other_os = OS_LINUX if current_os == OS_WINDOWS else OS_WINDOWS
            resolved = value.get(other_os)
            if resolved is not None:
                logger.warning(
                    f"現在のOS ({current_os}) の設定がないため、"
                    f"{other_os} の値を使用します"
                )
        return resolved
    return value


def validate_port(port: int) -> None:
    """ポート番号をバリデートする。

    Args:
        port: ポート番号

    Raises:
        ConfigValidationError: 1024-65535の範囲外の場合
    """
    if not isinstance(port, int) or port < 1024 or port > 65535:
        raise ConfigValidationError(
            f"ポート番号は1024-65535の範囲で指定してください: {port}"
        )


def validate_username(username: str) -> None:
    """ユーザー名をバリデートする。

    Args:
        username: ユーザー名

    Raises:
        ConfigValidationError: 3-32文字、英数字+アンダースコア以外の場合
    """
    if not isinstance(username, str):
        raise ConfigValidationError(f"ユーザー名は文字列で指定してください: {username}")
    if len(username) < 3 or len(username) > 32:
        raise ConfigValidationError(
            f"ユーザー名は3-32文字で指定してください: {username}"
        )
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise ConfigValidationError(
            f"ユーザー名は英数字とアンダースコアのみ使用可能です: {username}"
        )


def validate_password(password: str) -> None:
    """パスワードをバリデートする。

    Args:
        password: パスワード

    Raises:
        ConfigValidationError: 4文字未満の場合
    """
    if not isinstance(password, str) or len(password) < 4:
        raise ConfigValidationError("パスワードは4文字以上で指定してください")


def validate_role(role: str) -> None:
    """権限をバリデートする。

    Args:
        role: 権限

    Raises:
        ConfigValidationError: admin/user以外の場合
    """
    if role not in ("admin", "user"):
        raise ConfigValidationError(f"権限はadminまたはuserで指定してください: {role}")


def validate_session_lifetime(hours: int) -> None:
    """セッション有効時間をバリデートする。

    Args:
        hours: セッション有効時間（時間）

    Raises:
        ConfigValidationError: 1-168の範囲外の場合
    """
    if not isinstance(hours, int) or hours < 1 or hours > 168:
        raise ConfigValidationError(
            f"セッション有効時間は1-168時間の範囲で指定してください: {hours}"
        )


def validate_threshold(value: int, name: str) -> None:
    """閾値をバリデートする。

    Args:
        value: 閾値（%）
        name: 閾値の名前

    Raises:
        ConfigValidationError: 1-100の範囲外の場合
    """
    if not isinstance(value, int) or value < 1 or value > 100:
        raise ConfigValidationError(f"{name}は1-100%の範囲で指定してください: {value}")


def validate_log_level(level: str) -> None:
    """ログレベルをバリデートする。

    Args:
        level: ログレベル

    Raises:
        ConfigValidationError: DEBUG/INFO/WARNING/ERROR/CRITICAL以外の場合
    """
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if level.upper() not in valid_levels:
        raise ConfigValidationError(
            f"ログレベルは{'/'.join(valid_levels)}のいずれかで指定してください: {level}"
        )


class ConfigLoader:
    """設定ファイル読み込みクラス"""

    # OS別デフォルト値
    DEFAULT_VALUES = {
        "app_install.install_dir": {
            OS_WINDOWS: "C:\\pol-apps",
            OS_LINUX: "/opt/pol-apps",
        },
        "resource_monitor.disk_paths": {
            OS_WINDOWS: ["C:\\"],
            OS_LINUX: ["/"],
        },
    }

    def __init__(self, config_dir: Path | None = None) -> None:
        """初期化。

        Args:
            config_dir: 設定ファイルディレクトリ。Noneの場合はデフォルトパスを使用。
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        self.config_dir = config_dir
        self._current_os = get_current_os()

    def _resolve(self, value: Any) -> Any:
        """OS別設定値を解決するヘルパー。"""
        return resolve_os_value(value, self._current_os)

    def _get_default(self, key: str) -> Any:
        """OS別デフォルト値を取得する。"""
        default = self.DEFAULT_VALUES.get(key)
        if default is None:
            return None
        return self._resolve(default)

    def load_environment(self) -> dict[str, str | None]:
        """環境変数を読み込む。

        Returns:
            環境変数の辞書

        Raises:
            ConfigValidationError: 必須環境変数が未設定の場合
        """
        github_token = os.environ.get("POL_GITHUB_TOKEN")
        if not github_token:
            logger.warning(
                "環境変数 POL_GITHUB_TOKEN が設定されていません。"
                "GitHub連携機能は無効になります。"
            )

        return {
            "POL_GITHUB_TOKEN": github_token,
            "POL_SECRET_KEY": os.environ.get("POL_SECRET_KEY"),
        }

    def load_config_yaml(self) -> SystemConfig:
        """config.yamlを読み込む。

        Returns:
            システム設定

        Note:
            ファイルが存在しない場合はデフォルト値を使用
        """
        config_path = self.config_dir / "config.yaml"
        config_data: dict[str, Any] = {}

        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        else:
            logger.warning(f"設定ファイルが見つかりません: {config_path}")

        return self._parse_config(config_data)

    def _parse_config(self, data: dict[str, Any]) -> SystemConfig:
        """設定データをパースする。

        Args:
            data: 生の設定データ

        Returns:
            パース済みのSystemConfig
        """
        # サーバー設定
        server_data = data.get("server", {})
        server = ServerConfig(
            host=server_data.get("host", "0.0.0.0"),
            port=server_data.get("port", 8000),
            debug=server_data.get("debug", False),
        )

        # セッション設定
        session_data = data.get("session", {})
        session = SessionConfig(
            lifetime_hours=session_data.get("lifetime_hours", 24),
        )

        # リソースモニタ設定
        resource_data = data.get("resource_monitor", {})
        thresholds_data = resource_data.get("warning_thresholds", {})
        thresholds = WarningThresholds(
            cpu_percent=thresholds_data.get("cpu_percent", 80),
            memory_percent=thresholds_data.get("memory_percent", 80),
            disk_percent=thresholds_data.get("disk_percent", 90),
        )

        # disk_paths: OS別設定を解決
        disk_paths_raw = resource_data.get("disk_paths")
        if disk_paths_raw is not None:
            disk_paths = self._resolve(disk_paths_raw)
        else:
            disk_paths = self._get_default("resource_monitor.disk_paths")

        resource_monitor = ResourceMonitorConfig(
            disk_paths=disk_paths,
            warning_thresholds=thresholds,
        )

        # アプリインストール設定: OS別設定を解決
        app_install_data = data.get("app_install", {})
        install_dir_raw = app_install_data.get("install_dir")
        if install_dir_raw is not None:
            install_dir = self._resolve(install_dir_raw)
        else:
            install_dir = self._get_default("app_install.install_dir")

        github_api_url = app_install_data.get(
            "github_api_url", "https://api.github.com"
        )

        app_install = AppInstallConfig(
            install_dir=install_dir,
            github_api_url=github_api_url,
        )

        # ログ設定
        logging_data = data.get("logging", {})

        # コンソール設定
        console_data = logging_data.get("console", {})
        console_config = LoggingConsoleConfig(
            enabled=console_data.get("enabled", True),
        )

        # アーカイブ設定
        archive_data = logging_data.get("archive", {})
        archive_config = LoggingArchiveConfig(
            enabled=archive_data.get("enabled", True),
            directory=archive_data.get("directory", "archive"),
            retention_days=archive_data.get("retention_days", 30),
        )

        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            directory=logging_data.get("directory", "logs"),
            console=console_config,
            max_size_mb=logging_data.get("max_size_mb", 10),
            backup_count=logging_data.get("backup_count", 3),
            retention_days=logging_data.get("retention_days", 7),
            archive=archive_config,
            max_folder_size_mb=logging_data.get("max_folder_size_mb", 500),
            maintenance_interval_hours=logging_data.get(
                "maintenance_interval_hours", 24
            ),
        )

        # 初期ユーザー
        auth_data = data.get("auth", {})
        initial_users_data = auth_data.get("initial_users", [])
        initial_users = [
            InitialUser(
                username=user["username"],
                password=user["password"],
                role=user["role"],
            )
            for user in initial_users_data
        ]

        return SystemConfig(
            server=server,
            session=session,
            resource_monitor=resource_monitor,
            app_install=app_install,
            logging=logging_config,
            initial_users=initial_users,
        )

    def load_apps_yaml(self) -> list[Application]:
        """apps.yamlを読み込む。

        Returns:
            アプリケーションリスト

        Note:
            ファイルが存在しない場合は空リストを返す
        """
        apps_data = self._load_apps_raw()
        applications_data = apps_data.get("applications", [])
        applications = []

        for i, app_data in enumerate(applications_data):
            app = Application(
                id=app_data["id"],
                name=app_data["name"],
                github_owner=app_data["github_owner"],
                github_repo=app_data["github_repo"],
                service_name=app_data["service_name"],
                port=app_data["port"],
                description=app_data.get("description"),
                health_check_path=app_data.get("health_check_path"),
                auto_restart=app_data.get("auto_restart", False),
                installed=False,
                installed_version=None,
                installed_at=None,
                sort_order=i,
            )
            applications.append(app)

        return applications

    def load_app_scripts(self) -> list[AppScript]:
        """apps.yamlからスクリプト定義を読み込む。

        Returns:
            スクリプトリスト
        """
        apps_data = self._load_apps_raw()
        applications_data = apps_data.get("applications", [])
        scripts: list[AppScript] = []

        for app_data in applications_data:
            app_id = app_data["id"]
            scripts_data = app_data.get("scripts", [])

            for i, script_data in enumerate(scripts_data):
                path_raw = script_data.get("path", "")
                script_path = self._resolve(path_raw) if path_raw else ""

                script = AppScript(
                    id=script_data["id"],
                    app_id=app_id,
                    name=script_data["name"],
                    script_path=str(script_path) if script_path else "",
                    mode=script_data.get("mode", "sync"),
                    description=script_data.get("description"),
                    timeout=script_data.get("timeout", 60),
                    sort_order=i,
                    enabled=script_data.get("enabled", True),
                )
                scripts.append(script)

        return scripts

    def _load_apps_raw(self) -> dict[str, Any]:
        """apps.yamlの生データを読み込む。

        Returns:
            生の設定データ辞書
        """
        apps_path = self.config_dir / "apps.yaml"

        if not apps_path.exists():
            logger.warning(f"アプリケーション定義ファイルが見つかりません: {apps_path}")
            return {}

        with open(apps_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def validate_config(self, config: SystemConfig) -> None:
        """設定をバリデートする。

        Args:
            config: システム設定

        Raises:
            ConfigValidationError: バリデーションエラー
        """
        # サーバー設定
        validate_port(config.server.port)

        # セッション設定
        validate_session_lifetime(config.session.lifetime_hours)

        # 警告閾値
        validate_threshold(
            config.resource_monitor.warning_thresholds.cpu_percent, "CPU警告閾値"
        )
        validate_threshold(
            config.resource_monitor.warning_thresholds.memory_percent, "メモリ警告閾値"
        )
        validate_threshold(
            config.resource_monitor.warning_thresholds.disk_percent, "ディスク警告閾値"
        )

        # ログ設定
        validate_log_level(config.logging.level)

        # 初期ユーザー
        if not config.initial_users:
            raise ConfigValidationError("初期ユーザーが定義されていません")

        has_admin = False
        for user in config.initial_users:
            validate_username(user.username)
            validate_password(user.password)
            validate_role(user.role)
            if user.role == "admin":
                has_admin = True

        if not has_admin:
            raise ConfigValidationError("admin権限を持つ初期ユーザーが最低1人必要です")

    def validate_applications(self, applications: list[Application]) -> None:
        """アプリケーション定義をバリデートする。

        Args:
            applications: アプリケーションリスト

        Raises:
            ConfigValidationError: バリデーションエラー
        """
        seen_ids = set()
        seen_ports = set()

        for app in applications:
            # ID重複チェック
            if app.id in seen_ids:
                raise ConfigValidationError(
                    f"アプリケーションIDが重複しています: {app.id}"
                )
            seen_ids.add(app.id)

            # ポート番号バリデーション
            validate_port(app.port)

            # ポート重複チェック
            if app.port in seen_ports:
                raise ConfigValidationError(f"ポート番号が重複しています: {app.port}")
            seen_ports.add(app.port)

            # 必須フィールドチェック
            if not app.github_owner:
                raise ConfigValidationError(f"github_ownerが未設定です: {app.id}")
            if not app.github_repo:
                raise ConfigValidationError(f"github_repoが未設定です: {app.id}")

    def get_default_config(self) -> SystemConfig:
        """デフォルト設定を取得する。

        Returns:
            デフォルトのSystemConfig
        """
        return SystemConfig(
            resource_monitor=ResourceMonitorConfig(
                disk_paths=self._get_default("resource_monitor.disk_paths"),
            ),
            app_install=AppInstallConfig(
                install_dir=self._get_default("app_install.install_dir"),
            ),
            initial_users=[
                InitialUser(username="admin", password="admin", role="admin")
            ],
        )
