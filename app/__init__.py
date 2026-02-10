"""POL統合ポータル・リソース管理システム"""

__version__ = "1.0.0"

import logging
import secrets
from pathlib import Path

from flask import Flask
from flask_login import LoginManager

from app.services.config_loader import ConfigLoader
from app.services.database import Database
from app.services.log_manager import setup_logging
from app.services.models import SystemConfig

login_manager = LoginManager()

# グローバルインスタンス（アプリケーション内で共有）
db: Database | None = None

logger = logging.getLogger(__name__)


def create_app(
    config_dir: Path | None = None,
    skip_env_check: bool = False,
) -> Flask:
    """Flaskアプリケーションを生成する。

    Args:
        config_dir: 設定ファイルディレクトリ。Noneの場合はデフォルトパスを使用。
        skip_env_check: 環境変数チェックをスキップするか（テスト用）

    Returns:
        設定済みのFlaskアプリケーション

    Raises:
        ConfigValidationError: 設定バリデーションエラー
    """
    global db

    app = Flask(__name__)

    # 設定ディレクトリの決定
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / "config"

    # ConfigLoader初期化
    loader = ConfigLoader(config_dir)

    # 環境変数読み込み
    env_vars: dict[str, str | None] = {}
    if not skip_env_check:
        env_vars = loader.load_environment()
    else:
        env_vars = {"POL_GITHUB_TOKEN": "test_token", "POL_SECRET_KEY": None}

    # 設定ファイル読み込み
    config = loader.load_config_yaml()
    applications = loader.load_apps_yaml()

    # バリデーション
    loader.validate_config(config)
    if applications:
        loader.validate_applications(applications)

    # Database初期化
    db_path = config_dir / "settings.db"
    db = Database(db_path)

    # テーブル作成
    db.initialize()

    # DB未初期化（ユーザーなし）なら YAML → DB 投入
    if not db.has_users():
        _initialize_database(db, config, applications, env_vars, loader)

    # DBから設定読み込み → Flask config反映
    _apply_flask_config(app, db, env_vars)

    # Flask-Login初期化
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Databaseインスタンスをappに保存
    app.extensions["database"] = db

    # DB設定でロギングを初期化（Blueprint登録前に行う）
    _setup_logging_from_db(db)

    # Blueprintの登録
    _register_blueprints(app)

    return app


def _initialize_database(
    db: Database,
    config: SystemConfig,
    applications: list,
    env_vars: dict[str, str | None],
    loader: ConfigLoader | None = None,
) -> None:
    """データベースを初期データで初期化する。

    Args:
        db: Databaseインスタンス
        config: システム設定
        applications: アプリケーションリスト
        env_vars: 環境変数
        loader: ConfigLoaderインスタンス（スクリプト読み込み用）
    """
    # 初期ユーザー登録
    for user in config.initial_users:
        db.create_user(user)
        logger.info(f"初期ユーザーを作成しました: {user.username}")

    # システム設定をDBに保存
    _save_system_config(db, config)

    # SECRET_KEY生成（未設定の場合）
    if not env_vars.get("POL_SECRET_KEY"):
        secret_key = secrets.token_hex(32)
        db.set_setting("secret_key", secret_key, "session")
        logger.info("SECRET_KEYを自動生成しました")

    # アプリケーション登録
    for app in applications:
        db.create_application(app)
        logger.info(f"アプリケーションを登録しました: {app.id}")

    # スクリプト登録
    if loader is not None:
        app_scripts = loader.load_app_scripts()
        for script in app_scripts:
            db.create_app_script(script)
            logger.info(f"スクリプトを登録しました: {script.app_id}/{script.id}")


def _save_system_config(db: Database, config: SystemConfig) -> None:
    """システム設定をDBに保存する。

    Args:
        db: Databaseインスタンス
        config: システム設定
    """
    # サーバー設定
    db.set_setting("server.host", config.server.host, "server")
    db.set_setting("server.port", config.server.port, "server")
    db.set_setting("server.debug", config.server.debug, "server")

    # セッション設定
    db.set_setting("session.lifetime_hours", config.session.lifetime_hours, "session")

    # リソースモニタ設定
    db.set_setting(
        "resource_monitor.disk_paths",
        config.resource_monitor.disk_paths,
        "resource_monitor",
    )
    db.set_setting(
        "resource_monitor.warning_thresholds.cpu_percent",
        config.resource_monitor.warning_thresholds.cpu_percent,
        "resource_monitor",
    )
    db.set_setting(
        "resource_monitor.warning_thresholds.memory_percent",
        config.resource_monitor.warning_thresholds.memory_percent,
        "resource_monitor",
    )
    db.set_setting(
        "resource_monitor.warning_thresholds.disk_percent",
        config.resource_monitor.warning_thresholds.disk_percent,
        "resource_monitor",
    )

    # アプリインストール設定
    db.set_setting(
        "app_install.install_dir", config.app_install.install_dir, "app_install"
    )
    db.set_setting(
        "app_install.github_api_url", config.app_install.github_api_url, "app_install"
    )

    # ログ設定
    db.set_setting("logging.level", config.logging.level, "logging")
    db.set_setting("logging.directory", config.logging.directory, "logging")
    db.set_setting("logging.console.enabled", config.logging.console.enabled, "logging")
    db.set_setting("logging.max_size_mb", config.logging.max_size_mb, "logging")
    db.set_setting("logging.backup_count", config.logging.backup_count, "logging")
    db.set_setting("logging.retention_days", config.logging.retention_days, "logging")
    db.set_setting("logging.archive.enabled", config.logging.archive.enabled, "logging")
    db.set_setting(
        "logging.archive.directory", config.logging.archive.directory, "logging"
    )
    db.set_setting(
        "logging.archive.retention_days",
        config.logging.archive.retention_days,
        "logging",
    )
    db.set_setting(
        "logging.max_folder_size_mb", config.logging.max_folder_size_mb, "logging"
    )
    db.set_setting(
        "logging.maintenance_interval_hours",
        config.logging.maintenance_interval_hours,
        "logging",
    )


def _apply_flask_config(
    app: Flask,
    db: Database,
    env_vars: dict[str, str | None],
) -> None:
    """DBから設定を読み込んでFlask configに反映する。

    Args:
        app: Flaskアプリケーション
        db: Databaseインスタンス
        env_vars: 環境変数
    """
    # SECRET_KEY（環境変数優先、なければDB、それもなければデフォルト）
    secret_key = env_vars.get("POL_SECRET_KEY")
    if not secret_key:
        secret_key = db.get_setting("secret_key")
    if not secret_key:
        secret_key = "dev-secret-key-change-in-production"
    app.config["SECRET_KEY"] = secret_key

    # サーバー設定
    app.config["SERVER_HOST"] = db.get_setting("server.host", "0.0.0.0")
    app.config["SERVER_PORT"] = db.get_setting("server.port", 8000)
    app.config["DEBUG"] = db.get_setting("server.debug", False)

    # セッション設定
    app.config["SESSION_LIFETIME_HOURS"] = db.get_setting("session.lifetime_hours", 24)

    # リソースモニタ設定
    app.config["DISK_PATHS"] = db.get_setting("resource_monitor.disk_paths", ["/"])
    app.config["CPU_WARNING_THRESHOLD"] = db.get_setting(
        "resource_monitor.warning_thresholds.cpu_percent", 80
    )
    app.config["MEMORY_WARNING_THRESHOLD"] = db.get_setting(
        "resource_monitor.warning_thresholds.memory_percent", 80
    )
    app.config["DISK_WARNING_THRESHOLD"] = db.get_setting(
        "resource_monitor.warning_thresholds.disk_percent", 90
    )

    # アプリインストール設定
    app.config["APP_INSTALL_DIR"] = db.get_setting(
        "app_install.install_dir", "/opt/pol-apps"
    )
    app.config["GITHUB_API_URL"] = db.get_setting(
        "app_install.github_api_url", "https://api.github.com"
    )

    # GitHub Token
    app.config["GITHUB_TOKEN"] = env_vars.get("POL_GITHUB_TOKEN")


def _setup_logging_from_db(db: Database) -> None:
    """DB設定を使ってロギングを初期化する。

    Args:
        db: Databaseインスタンス
    """
    log_config = {
        "level": db.get_setting("logging.level", "INFO"),
        "directory": db.get_setting("logging.directory", "logs"),
        "console": {"enabled": db.get_setting("logging.console.enabled", True)},
        "max_size_mb": db.get_setting("logging.max_size_mb", 10),
        "backup_count": db.get_setting("logging.backup_count", 3),
        "retention_days": db.get_setting("logging.retention_days", 7),
        "archive": {
            "enabled": db.get_setting("logging.archive.enabled", True),
            "directory": db.get_setting("logging.archive.directory", "archive"),
            "retention_days": db.get_setting("logging.archive.retention_days", 30),
        },
        "max_folder_size_mb": db.get_setting("logging.max_folder_size_mb", 500),
        "maintenance_interval_hours": db.get_setting(
            "logging.maintenance_interval_hours", 24
        ),
    }
    setup_logging(log_config)


def _register_blueprints(app: Flask) -> None:
    """Blueprintを登録する。"""
    from app.routes import apps, auth, dashboard, proxy, resources, settings

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(resources.bp)
    app.register_blueprint(apps.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(proxy.bp)

    # コンテキストプロセッサを登録（サイドバー用）
    @app.context_processor
    def inject_sidebar_data():
        """テンプレートにサイドバー用データを注入する。"""
        from flask_login import current_user

        result = {
            "installed_apps": [],
            "app_version": __version__,
        }

        if not current_user.is_authenticated:
            return result

        database = app.extensions.get("database")
        if database is None:
            return result

        applications = database.get_all_applications()
        result["installed_apps"] = [
            {"id": a.id, "name": a.name, "port": a.port}
            for a in applications
            if a.installed
        ]
        return result


def get_db() -> Database:
    """Databaseインスタンスを取得する。

    Returns:
        Databaseインスタンス

    Raises:
        RuntimeError: アプリケーションが初期化されていない場合
    """
    if db is None:
        raise RuntimeError("アプリケーションが初期化されていません")
    return db
