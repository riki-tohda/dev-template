"""設定管理のルート"""

from functools import wraps

import bcrypt
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import get_db
from app.services.log_manager import get_logger
from app.services.models import InitialUser

bp = Blueprint("settings", __name__, url_prefix="/settings")
logger = get_logger("app")


def admin_required(f):
    """管理者権限が必要なルートのデコレーター"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            flash("この操作には管理者権限が必要です", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/")
@admin_required
def index():
    """設定トップ画面を表示する。"""
    return render_template("settings/index.html")


# --- サーバー設定 ---


@bp.route("/server", methods=["GET", "POST"])
@admin_required
def server():
    """サーバー設定画面"""
    db = get_db()

    if request.method == "POST":
        try:
            port = int(request.form.get("port", 8000))
            if port < 1024 or port > 65535:
                raise ValueError("ポート番号は1024-65535の範囲で指定してください")

            db.set_setting("server.port", port, "server")
            flash("サーバー設定を保存しました（再起動後に反映されます）", "success")
            logger.info(
                "サーバー設定を変更しました port=%d user=%s",
                port,
                current_user.username,
            )
        except ValueError as e:
            flash(str(e), "error")

        return redirect(url_for("settings.server"))

    settings = {
        "host": db.get_setting("server.host", "0.0.0.0"),
        "port": db.get_setting("server.port", 8000),
    }
    return render_template("settings/server.html", settings=settings)


# --- セッション設定 ---


@bp.route("/session", methods=["GET", "POST"])
@admin_required
def session():
    """セッション設定画面"""
    db = get_db()

    if request.method == "POST":
        try:
            lifetime_hours = int(request.form.get("lifetime_hours", 24))
            if lifetime_hours < 1 or lifetime_hours > 168:
                raise ValueError(
                    "セッション有効時間は1-168時間の範囲で指定してください"
                )

            db.set_setting("session.lifetime_hours", lifetime_hours, "session")
            flash("セッション設定を保存しました", "success")
            logger.info(
                "セッション設定を変更しました lifetime_hours=%d user=%s",
                lifetime_hours,
                current_user.username,
            )
        except ValueError as e:
            flash(str(e), "error")

        return redirect(url_for("settings.session"))

    settings = {
        "lifetime_hours": db.get_setting("session.lifetime_hours", 24),
    }
    return render_template("settings/session.html", settings=settings)


# --- ユーザー管理 ---


@bp.route("/users")
@admin_required
def users():
    """ユーザー一覧画面"""
    db = get_db()
    users = db.get_all_users()
    return render_template("settings/users.html", users=users)


@bp.route("/users/add", methods=["GET", "POST"])
@admin_required
def users_add():
    """ユーザー追加画面"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        # バリデーション
        errors = []
        if len(username) < 3 or len(username) > 32:
            errors.append("ユーザー名は3-32文字で指定してください")
        if len(password) < 4:
            errors.append("パスワードは4文字以上で指定してください")
        if role not in ("admin", "user"):
            errors.append("権限はadminまたはuserで指定してください")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("settings/users_form.html", mode="add")

        db = get_db()

        # 重複チェック
        if db.get_user_by_username(username):
            flash("このユーザー名は既に使用されています", "error")
            return render_template("settings/users_form.html", mode="add")

        # ユーザー作成
        user = InitialUser(username=username, password=password, role=role)
        db.create_user(user)
        flash(f"ユーザー {username} を作成しました", "success")
        logger.info(
            "ユーザーを作成しました new_user=%s by=%s", username, current_user.username
        )

        return redirect(url_for("settings.users"))

    return render_template("settings/users_form.html", mode="add")


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def users_edit(user_id: int):
    """ユーザー編集画面"""
    db = get_db()
    user = db.get_user_by_id(user_id)

    if user is None:
        abort(404)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        role = request.form.get("role", "user")
        enabled = request.form.get("enabled") == "on"
        new_password = request.form.get("new_password", "")

        # バリデーション
        errors = []
        if len(username) < 3 or len(username) > 32:
            errors.append("ユーザー名は3-32文字で指定してください")
        if role not in ("admin", "user"):
            errors.append("権限はadminまたはuserで指定してください")
        if new_password and len(new_password) < 4:
            errors.append("パスワードは4文字以上で指定してください")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("settings/users_form.html", mode="edit", user=user)

        # 重複チェック（自分以外）
        existing = db.get_user_by_username(username)
        if existing and existing.id != user_id:
            flash("このユーザー名は既に使用されています", "error")
            return render_template("settings/users_form.html", mode="edit", user=user)

        # 更新
        user.username = username
        user.role = role
        user.enabled = enabled

        if new_password:
            user.password_hash = bcrypt.hashpw(
                new_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

        db.update_user(user)
        flash(f"ユーザー {username} を更新しました", "success")
        logger.info(
            "ユーザーを更新しました target=%s by=%s", username, current_user.username
        )

        return redirect(url_for("settings.users"))

    return render_template("settings/users_form.html", mode="edit", user=user)


# --- リソース監視設定 ---


@bp.route("/resource", methods=["GET", "POST"])
@admin_required
def resource():
    """リソース監視設定画面"""
    db = get_db()

    if request.method == "POST":
        try:
            cpu_threshold = int(request.form.get("cpu_threshold", 80))
            memory_threshold = int(request.form.get("memory_threshold", 80))
            disk_threshold = int(request.form.get("disk_threshold", 90))

            for name, value in [
                ("CPU警告閾値", cpu_threshold),
                ("メモリ警告閾値", memory_threshold),
                ("ディスク警告閾値", disk_threshold),
            ]:
                if value < 1 or value > 100:
                    raise ValueError(f"{name}は1-100%の範囲で指定してください")

            db.set_setting(
                "resource_monitor.warning_thresholds.cpu_percent",
                cpu_threshold,
                "resource_monitor",
            )
            db.set_setting(
                "resource_monitor.warning_thresholds.memory_percent",
                memory_threshold,
                "resource_monitor",
            )
            db.set_setting(
                "resource_monitor.warning_thresholds.disk_percent",
                disk_threshold,
                "resource_monitor",
            )

            flash("リソース監視設定を保存しました", "success")
            logger.info(
                "リソース監視設定を変更しました cpu=%d%% memory=%d%% disk=%d%% user=%s",
                cpu_threshold,
                memory_threshold,
                disk_threshold,
                current_user.username,
            )
        except ValueError as e:
            flash(str(e), "error")

        return redirect(url_for("settings.resource"))

    settings = {
        "cpu_threshold": db.get_setting(
            "resource_monitor.warning_thresholds.cpu_percent", 80
        ),
        "memory_threshold": db.get_setting(
            "resource_monitor.warning_thresholds.memory_percent", 80
        ),
        "disk_threshold": db.get_setting(
            "resource_monitor.warning_thresholds.disk_percent", 90
        ),
    }
    return render_template("settings/resource.html", settings=settings)


# --- アプリインストール設定 ---


@bp.route("/app-install", methods=["GET", "POST"])
@admin_required
def app_install():
    """アプリインストール設定画面"""
    db = get_db()

    if request.method == "POST":
        install_dir = request.form.get("install_dir", "").strip()
        github_api_url = request.form.get("github_api_url", "").strip()

        if not install_dir:
            flash("インストール先ディレクトリを入力してください", "error")
            return redirect(url_for("settings.app_install"))

        db.set_setting("app_install.install_dir", install_dir, "app_install")
        if github_api_url:
            db.set_setting("app_install.github_api_url", github_api_url, "app_install")
        flash("アプリインストール設定を保存しました", "success")
        logger.info(
            "アプリインストール設定を変更しました install_dir=%s github_api_url=%s user=%s",
            install_dir,
            github_api_url,
            current_user.username,
        )

        return redirect(url_for("settings.app_install"))

    settings = {
        "install_dir": db.get_setting("app_install.install_dir", "/opt/pol-apps"),
        "github_api_url": db.get_setting(
            "app_install.github_api_url", "https://api.github.com"
        ),
    }
    return render_template("settings/app_install.html", settings=settings)


# --- プロファイル（全ユーザー共通） ---


@bp.route("/profile/password", methods=["GET", "POST"])
@login_required
def profile_password():
    """パスワード変更画面"""
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        # 現在のパスワード確認
        if not bcrypt.checkpw(
            current_password.encode("utf-8"),
            current_user.password_hash.encode("utf-8"),
        ):
            flash("現在のパスワードが正しくありません", "error")
            return render_template("settings/password.html")

        # 新しいパスワードのバリデーション
        if len(new_password) < 4:
            flash("新しいパスワードは4文字以上で指定してください", "error")
            return render_template("settings/password.html")

        if new_password != confirm_password:
            flash("新しいパスワードが一致しません", "error")
            return render_template("settings/password.html")

        # パスワード更新
        db = get_db()
        user = db.get_user_by_id(current_user.id)
        user.password_hash = bcrypt.hashpw(
            new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        db.update_user(user)

        flash("パスワードを変更しました", "success")
        logger.info("パスワードを変更しました user=%s", current_user.username)

        return redirect(url_for("dashboard.index"))

    return render_template("settings/password.html")
