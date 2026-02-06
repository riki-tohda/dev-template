"""型定義（dataclass）モジュール"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ServerConfig:
    """サーバー設定"""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


@dataclass
class SessionConfig:
    """セッション設定"""

    lifetime_hours: int = 24


@dataclass
class WarningThresholds:
    """警告閾値設定"""

    cpu_percent: int = 80
    memory_percent: int = 80
    disk_percent: int = 90


@dataclass
class ResourceMonitorConfig:
    """リソースモニタ設定"""

    disk_paths: list[str] = field(default_factory=list)
    warning_thresholds: WarningThresholds = field(default_factory=WarningThresholds)


@dataclass
class AppInstallConfig:
    """アプリインストール設定"""

    install_dir: str = ""
    github_api_url: str = "https://api.github.com"


@dataclass
class LoggingArchiveConfig:
    """ログアーカイブ設定"""

    enabled: bool = True
    directory: str = "archive"
    retention_days: int = 30


@dataclass
class LoggingConsoleConfig:
    """ログコンソール設定"""

    enabled: bool = True


@dataclass
class LoggingConfig:
    """ログ設定"""

    level: str = "INFO"
    directory: str = "logs"
    console: LoggingConsoleConfig = field(default_factory=LoggingConsoleConfig)
    max_size_mb: int = 10
    backup_count: int = 3
    retention_days: int = 7
    archive: LoggingArchiveConfig = field(default_factory=LoggingArchiveConfig)
    max_folder_size_mb: int = 500


@dataclass
class InitialUser:
    """初期ユーザー"""

    username: str
    password: str
    role: str


@dataclass
class User:
    """ユーザー（DB保存用）

    Flask-Login との連携のため、UserMixin 相当のメソッドを実装。
    """

    id: int
    username: str
    password_hash: str
    role: str
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Flask-Login 用プロパティ・メソッド

    @property
    def is_authenticated(self) -> bool:
        """認証済みかどうか"""
        return True

    @property
    def is_active(self) -> bool:
        """アクティブかどうか"""
        return self.enabled

    @property
    def is_anonymous(self) -> bool:
        """匿名ユーザーかどうか"""
        return False

    def get_id(self) -> str:
        """ユーザーIDを文字列で返す（Flask-Login用）"""
        return str(self.id)

    @property
    def is_admin(self) -> bool:
        """管理者権限を持つかどうか"""
        return self.role == "admin"


@dataclass
class Application:
    """アプリケーション"""

    id: str
    name: str
    github_owner: str
    github_repo: str
    service_name: str
    port: int
    description: str | None = None
    health_check_path: str | None = None
    auto_restart: bool = False
    installed: bool = False
    installed_version: str | None = None
    installed_at: datetime | None = None
    sort_order: int = 0
    updated_at: datetime | None = None
    # プロキシ設定
    proxy_enabled: bool = True
    proxy_rewrite_urls: bool = True


@dataclass
class SystemConfig:
    """システム設定全体"""

    server: ServerConfig = field(default_factory=ServerConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    resource_monitor: ResourceMonitorConfig = field(
        default_factory=ResourceMonitorConfig
    )
    app_install: AppInstallConfig = field(default_factory=AppInstallConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    initial_users: list[InitialUser] = field(default_factory=list)
