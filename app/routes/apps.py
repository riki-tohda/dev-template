"""アプリケーション管理のルート"""

from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app import get_db
from app.services.app_manager import AppConfig, AppManager, AppStatus
from app.services.github_client import AppInstaller, GitHubClient, GitHubClientError
from app.services.log_manager import get_logger
from app.services.models import AppScript, ScriptExecution
from app.services.script_executor import ScriptExecutor

bp = Blueprint("apps", __name__, url_prefix="/apps")
logger = get_logger("app")
install_logger = get_logger("install")


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
    api_base_url = current_app.config.get("GITHUB_API_URL")
    client = GitHubClient(token, api_base_url=api_base_url)
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
            return jsonify(
                {
                    "has_update": False,
                    "current_version": app.installed_version,
                    "latest_version": app.installed_version,
                }
            )

        return jsonify(
            {
                "has_update": True,
                "current_version": app.installed_version,
                "latest_version": release.tag_name,
                "release_name": release.name,
                "published_at": release.published_at.isoformat(),
            }
        )
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
        return jsonify(
            {"success": False, "message": "アプリケーションが見つかりません"}
        ), 404

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

        install_logger.info(
            "アプリをインストールしました app=%s version=%s user=%s",
            app_id,
            version,
            current_user.username,
        )

        return jsonify(
            {
                "success": True,
                "message": f"インストールが完了しました（{version}）",
                "version": version,
            }
        )
    except GitHubClientError as e:
        install_logger.error("インストールに失敗しました app=%s error=%s", app_id, e)
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
        return jsonify(
            {"success": False, "message": "アプリケーションが見つかりません"}
        ), 404

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

        install_logger.info(
            "アプリをアップデートしました app=%s version=%s user=%s",
            app_id,
            version,
            current_user.username,
        )

        return jsonify(
            {
                "success": True,
                "message": f"アップデートが完了しました（{version}）",
                "version": version,
            }
        )
    except GitHubClientError as e:
        install_logger.error("アップデートに失敗しました app=%s error=%s", app_id, e)
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
        return jsonify(
            {"success": False, "message": "アプリケーションが見つかりません"}
        ), 404

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

        install_logger.info(
            "アプリをアンインストールしました app=%s user=%s",
            app_id,
            current_user.username,
        )

        return jsonify(
            {
                "success": True,
                "message": "アンインストールが完了しました",
            }
        )
    except GitHubClientError as e:
        install_logger.error("アンインストールに失敗しました app=%s error=%s", app_id, e)
        return jsonify({"success": False, "message": str(e)}), 500


# --- スクリプト関連 ---


def _get_script_executor() -> ScriptExecutor:
    """ScriptExecutorインスタンスを取得する。"""
    install_dir = Path(current_app.config.get("APP_INSTALL_DIR", "/opt/pol-apps"))
    project_root = Path(current_app.root_path).parent
    allowed_dirs = [install_dir, project_root]
    return ScriptExecutor(allowed_dirs)


@bp.route("/api/<app_id>/scripts")
@admin_required
def api_get_scripts(app_id: str):
    """アプリのスクリプト一覧を取得する。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: スクリプト一覧
    """
    db = get_db()
    app = db.get_application(app_id)
    if app is None:
        return jsonify({"error": "アプリケーションが見つかりません"}), 404

    scripts = db.get_app_scripts(app_id)
    return jsonify([
        {
            "id": s.id,
            "app_id": s.app_id,
            "name": s.name,
            "description": s.description,
            "script_path": s.script_path,
            "mode": s.mode,
            "timeout": s.timeout,
            "sort_order": s.sort_order,
            "enabled": s.enabled,
        }
        for s in scripts
    ])


@bp.route("/api/<app_id>/scripts", methods=["POST"])
@admin_required
def api_create_script(app_id: str):
    """スクリプトを登録する。

    Args:
        app_id: アプリケーションID

    Returns:
        JSON: 操作結果
    """
    db = get_db()
    app = db.get_application(app_id)
    if app is None:
        return jsonify({"success": False, "message": "アプリケーションが見つかりません"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "リクエストボディが必要です"}), 400

    script_id = data.get("id", "").strip()
    name = data.get("name", "").strip()
    script_path = data.get("script_path", "").strip()

    if not script_id or not name or not script_path:
        return jsonify({"success": False, "message": "id, name, script_path は必須です"}), 400

    mode = data.get("mode", "sync")
    if mode not in ("sync", "async"):
        return jsonify({"success": False, "message": "mode は sync または async です"}), 400

    existing = db.get_app_script(app_id, script_id)
    if existing is not None:
        return jsonify({"success": False, "message": f"スクリプトID '{script_id}' は既に存在します"}), 409

    script = AppScript(
        id=script_id,
        app_id=app_id,
        name=name,
        script_path=script_path,
        mode=mode,
        description=data.get("description"),
        timeout=data.get("timeout", 60),
        sort_order=data.get("sort_order", 0),
        enabled=data.get("enabled", True),
    )

    db.create_app_script(script)

    install_logger.info(
        "スクリプトを登録しました app=%s script=%s user=%s",
        app_id,
        script_id,
        current_user.username,
    )

    return jsonify({"success": True, "message": "スクリプトを登録しました"})


@bp.route("/api/<app_id>/scripts/<script_id>", methods=["PUT"])
@admin_required
def api_update_script(app_id: str, script_id: str):
    """スクリプトを更新する。

    Args:
        app_id: アプリケーションID
        script_id: スクリプトID

    Returns:
        JSON: 操作結果
    """
    db = get_db()
    script = db.get_app_script(app_id, script_id)
    if script is None:
        return jsonify({"success": False, "message": "スクリプトが見つかりません"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "リクエストボディが必要です"}), 400

    if "name" in data:
        script.name = data["name"]
    if "description" in data:
        script.description = data["description"]
    if "script_path" in data:
        script.script_path = data["script_path"]
    if "mode" in data:
        if data["mode"] not in ("sync", "async"):
            return jsonify({"success": False, "message": "mode は sync または async です"}), 400
        script.mode = data["mode"]
    if "timeout" in data:
        script.timeout = data["timeout"]
    if "sort_order" in data:
        script.sort_order = data["sort_order"]
    if "enabled" in data:
        script.enabled = data["enabled"]

    db.update_app_script(script)

    install_logger.info(
        "スクリプトを更新しました app=%s script=%s user=%s",
        app_id,
        script_id,
        current_user.username,
    )

    return jsonify({"success": True, "message": "スクリプトを更新しました"})


@bp.route("/api/<app_id>/scripts/<script_id>", methods=["DELETE"])
@admin_required
def api_delete_script(app_id: str, script_id: str):
    """スクリプトを削除する。

    Args:
        app_id: アプリケーションID
        script_id: スクリプトID

    Returns:
        JSON: 操作結果
    """
    db = get_db()
    script = db.get_app_script(app_id, script_id)
    if script is None:
        return jsonify({"success": False, "message": "スクリプトが見つかりません"}), 404

    db.delete_app_script(app_id, script_id)

    install_logger.info(
        "スクリプトを削除しました app=%s script=%s user=%s",
        app_id,
        script_id,
        current_user.username,
    )

    return jsonify({"success": True, "message": "スクリプトを削除しました"})


@bp.route("/api/<app_id>/scripts/<script_id>/execute", methods=["POST"])
@admin_required
def api_execute_script(app_id: str, script_id: str):
    """スクリプトを実行する。

    Args:
        app_id: アプリケーションID
        script_id: スクリプトID

    Returns:
        JSON: 実行結果
    """
    db = get_db()
    script = db.get_app_script(app_id, script_id)
    if script is None:
        return jsonify({"success": False, "message": "スクリプトが見つかりません"}), 404

    if not script.enabled:
        return jsonify({"success": False, "message": "スクリプトが無効化されています"}), 400

    executor = _get_script_executor()
    valid, error_msg = executor.validate_script(script)
    if not valid:
        return jsonify({"success": False, "message": error_msg}), 400

    execution = ScriptExecution(
        id=None,
        script_id=script_id,
        app_id=app_id,
        executed_by=current_user.username,
        mode=script.mode,
        status="running",
        started_at=datetime.now(),
    )
    execution_id = db.create_script_execution(execution)

    install_logger.info(
        "スクリプトを実行します app=%s script=%s mode=%s user=%s",
        app_id,
        script_id,
        script.mode,
        current_user.username,
    )

    if script.mode == "async":
        executor.execute_async(script, execution_id, db)
        return jsonify({
            "success": True,
            "message": "非同期実行を開始しました",
            "execution_id": execution_id,
        })

    # 同期実行
    result = executor.execute_sync(script)

    execution = db.get_script_execution(execution_id)
    if execution is not None:
        if result.error_message:
            execution.status = "timeout" if "タイムアウト" in result.error_message else "failed"
            execution.stderr = result.error_message
        else:
            execution.status = "completed" if result.success else "failed"
        execution.exit_code = result.exit_code
        execution.stdout = result.stdout
        execution.stderr = execution.stderr or result.stderr
        execution.finished_at = datetime.now()
        db.update_script_execution(execution)

    return jsonify({
        "success": result.success,
        "message": "実行完了" if result.success else (result.error_message or "実行に失敗しました"),
        "execution_id": execution_id,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr or result.error_message,
    })


@bp.route("/api/<app_id>/scripts/<script_id>/executions")
@admin_required
def api_get_executions(app_id: str, script_id: str):
    """スクリプト実行履歴を取得する。

    Args:
        app_id: アプリケーションID
        script_id: スクリプトID

    Returns:
        JSON: 実行履歴
    """
    db = get_db()
    script = db.get_app_script(app_id, script_id)
    if script is None:
        return jsonify({"error": "スクリプトが見つかりません"}), 404

    executions = db.get_script_executions(app_id, script_id)
    return jsonify([
        {
            "id": e.id,
            "script_id": e.script_id,
            "executed_by": e.executed_by,
            "mode": e.mode,
            "status": e.status,
            "exit_code": e.exit_code,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "finished_at": e.finished_at.isoformat() if e.finished_at else None,
        }
        for e in executions
    ])


@bp.route("/api/scripts/executions/<int:execution_id>")
@admin_required
def api_get_execution_detail(execution_id: int):
    """スクリプト実行結果の詳細を取得する（ポーリング用）。

    Args:
        execution_id: 実行ID

    Returns:
        JSON: 実行結果詳細
    """
    db = get_db()
    execution = db.get_script_execution(execution_id)
    if execution is None:
        return jsonify({"error": "実行レコードが見つかりません"}), 404

    return jsonify({
        "id": execution.id,
        "script_id": execution.script_id,
        "app_id": execution.app_id,
        "executed_by": execution.executed_by,
        "mode": execution.mode,
        "status": execution.status,
        "exit_code": execution.exit_code,
        "stdout": execution.stdout,
        "stderr": execution.stderr,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
    })
