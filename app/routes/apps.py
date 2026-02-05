"""アプリケーション管理のルート"""

from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import get_db
from app.services.app_manager import AppConfig, AppManager, AppStatus
from app.services.github_client import AppInstaller, GitHubClient, GitHubClientError
from app.services.log_manager import get_logger

bp = Blueprint("apps", __name__, url_prefix="/apps")
logger = get_logger("app")


def admin_required(f):
    """管理者権限が必要なルートのデコレーター"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "認証が必要です"}), 401
        if not current_user.is_admin:
            return jsonify({"success": False, "message": "管理者権限が必要です"}), 403
        return f(*args, **kwargs)

    return decorated_function


def _get_installer() -> AppInstaller:
    """AppInstallerインスタンスを取得する。"""
    token = current_app.config.get("GITHUB_TOKEN")
    if not token:
        raise GitHubClientError("GitHub Tokenが設定されていません")

    install_dir = Path(current_app.config.get("APP_INSTALL_DIR", "/opt/pol-apps"))
    client = GitHubClient(token)
    return AppInstaller(client, install_dir)


def _get_app_manager() -> AppManager:
    """AppManagerインスタンスを取得する。"""
    db = get_db()
    applications = db.get_all_applications()

    # Application を AppConfig に変換
    app_configs = [
        AppConfig(
            id=app.id,
            name=app.name,
            description=app.description or "",
            github_owner=app.github_owner,
            github_repo=app.github_repo,
            service_name=app.service_name,
            port=app.port,
            health_check_path=app.health_check_path or "/health",
            auto_restart=app.auto_restart,
        )
        for app in applications
    ]

    # Linux以外ではsystemctlを使用しない
    import platform

    use_systemctl = platform.system() == "Linux"

    return AppManager(apps=app_configs, use_systemctl=use_systemctl)


@bp.route("/")
@login_required
def index():
    """アプリ一覧を表示する。"""
    return render_template("apps/index.html")


@bp.route("/<app_id>")
@login_required
def detail(app_id: str):
    """アプリ詳細を表示する。

    Args:
        app_id: アプリケーションID
    """
    db = get_db()
    app = db.get_application(app_id)

    if app is None:
        abort(404)

    return render_template("apps/detail.html", app=app)


@bp.route("/api/status")
@login_required
def api_status():
    """全アプリケーションの状態をJSON形式で返す。

    Returns:
        JSON: アプリケーション一覧と状態
    """
    db = get_db()
    applications = db.get_all_applications()
    manager = _get_app_manager()

    result = []
    for app in applications:
        state = manager.get_status(app.id)
        result.append(
            {
                "id": app.id,
                "name": app.name,
                "description": app.description or "",
                "port": app.port,
                "status": state.status.value,
                "service_active": state.service_active,
                "health_check_ok": state.health_check_ok,
                "installed": app.installed,
                "installed_version": app.installed_version,
            }
        )

    return jsonify(result)


@bp.route("/api/<app_id>/status")
@login_required
def api_app_status(app_id: str):
    """特定アプリケーションの状態をJSON形式で返す。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: アプリケーションの状態
    """
    manager = _get_app_manager()
    state = manager.get_status(app_id)

    if state.status == AppStatus.UNKNOWN and "見つかりません" in (
        state.error_message or ""
    ):
        return jsonify({"error": "アプリケーションが見つかりません"}), 404

    return jsonify(state.to_dict())


@bp.route("/api/<app_id>/start", methods=["POST"])
@login_required
def api_start(app_id: str):
    """アプリケーションを起動する。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    manager = _get_app_manager()
    result = manager.start(app_id)
    return jsonify(result.to_dict())


@bp.route("/api/<app_id>/stop", methods=["POST"])
@login_required
def api_stop(app_id: str):
    """アプリケーションを停止する。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    manager = _get_app_manager()
    result = manager.stop(app_id)
    return jsonify(result.to_dict())


@bp.route("/api/<app_id>/restart", methods=["POST"])
@login_required
def api_restart(app_id: str):
    """アプリケーションを再起動する。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    manager = _get_app_manager()
    result = manager.restart(app_id)
    return jsonify(result.to_dict())


# --- インストール関連 ---


@bp.route("/api/<app_id>/check-update")
@login_required
def api_check_update(app_id: str):
    """アップデートを確認する。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 最新バージョン情報
    """
    db = get_db()
    app = db.get_application(app_id)

    if app is None:
        return jsonify({"error": "アプリケーションが見つかりません"}), 404

    try:
        installer = _get_installer()
        release = installer.check_update(
            app.github_owner,
            app.github_repo,
            app.installed_version,
        )

        if release is None:
            return jsonify({
                "has_update": False,
                "current_version": app.installed_version,
                "latest_version": app.installed_version,
            })

        return jsonify({
            "has_update": True,
            "current_version": app.installed_version,
            "latest_version": release.tag_name,
            "release_name": release.name,
            "published_at": release.published_at.isoformat(),
        })
    except GitHubClientError as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/<app_id>/install", methods=["POST"])
@admin_required
def api_install(app_id: str):
    """アプリケーションをインストールする。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    db = get_db()
    app = db.get_application(app_id)

    if app is None:
        return jsonify({"success": False, "message": "アプリケーションが見つかりません"}), 404

    if app.installed:
        return jsonify({"success": False, "message": "既にインストールされています"})

    try:
        installer = _get_installer()
        version = installer.install(app.github_owner, app.github_repo, app_id)

        # DBを更新
        app.installed = True
        app.installed_version = version
        app.installed_at = datetime.now()
        db.update_application(app)

        logger.info(
            "アプリをインストールしました app=%s version=%s user=%s",
            app_id,
            version,
            current_user.username,
        )

        return jsonify({
            "success": True,
            "message": f"インストールが完了しました（{version}）",
            "version": version,
        })
    except GitHubClientError as e:
        logger.error("インストールに失敗しました app=%s error=%s", app_id, e)
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route("/api/<app_id>/update", methods=["POST"])
@admin_required
def api_update(app_id: str):
    """アプリケーションをアップデートする。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    db = get_db()
    app = db.get_application(app_id)

    if app is None:
        return jsonify({"success": False, "message": "アプリケーションが見つかりません"}), 404

    if not app.installed:
        return jsonify({"success": False, "message": "インストールされていません"})

    try:
        # まずサービスを停止
        manager = _get_app_manager()
        if manager.get_status(app_id).service_active:
            manager.stop(app_id)

        # アップデート実行
        installer = _get_installer()
        version = installer.install(app.github_owner, app.github_repo, app_id)

        # DBを更新
        app.installed_version = version
        app.installed_at = datetime.now()
        db.update_application(app)

        # サービスを再起動
        manager.start(app_id)

        logger.info(
            "アプリをアップデートしました app=%s version=%s user=%s",
            app_id,
            version,
            current_user.username,
        )

        return jsonify({
            "success": True,
            "message": f"アップデートが完了しました（{version}）",
            "version": version,
        })
    except GitHubClientError as e:
        logger.error("アップデートに失敗しました app=%s error=%s", app_id, e)
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route("/api/<app_id>/uninstall", methods=["POST"])
@admin_required
def api_uninstall(app_id: str):
    """アプリケーションをアンインストールする。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    db = get_db()
    app = db.get_application(app_id)

    if app is None:
        return jsonify({"success": False, "message": "アプリケーションが見つかりません"}), 404

    if not app.installed:
        return jsonify({"success": False, "message": "インストールされていません"})

    try:
        # まずサービスを停止
        manager = _get_app_manager()
        if manager.get_status(app_id).service_active:
            manager.stop(app_id)

        # アンインストール実行
        installer = _get_installer()
        installer.uninstall(app_id)

        # DBを更新
        app.installed = False
        app.installed_version = None
        app.installed_at = None
        db.update_application(app)

        logger.info(
            "アプリをアンインストールしました app=%s user=%s",
            app_id,
            current_user.username,
        )

        return jsonify({
            "success": True,
            "message": "アンインストールが完了しました",
        })
    except GitHubClientError as e:
        logger.error("アンインストールに失敗しました app=%s error=%s", app_id, e)
        return jsonify({"success": False, "message": str(e)}), 500
