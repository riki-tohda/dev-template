"""認証関連のルート"""

import bcrypt
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import get_db, login_manager
from app.services.log_manager import get_logger
from app.services.models import User

bp = Blueprint("auth", __name__)
logger = get_logger("auth")


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Flask-Login用のユーザーローダー。

    Args:
        user_id: ユーザーID（文字列）

    Returns:
        Userオブジェクト。見つからない場合はNone。
    """
    try:
        db = get_db()
        return db.get_user_by_id(int(user_id))
    except (ValueError, RuntimeError):
        return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    """ログイン画面を表示・処理する。"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("ユーザー名とパスワードを入力してください", "error")
            return render_template("login.html")

        db = get_db()
        user = db.get_user_by_username(username)

        if user is None:
            logger.warning("ログイン失敗: ユーザーが見つかりません user=%s", username)
            flash("ユーザー名またはパスワードが正しくありません", "error")
            return render_template("login.html")

        if not user.enabled:
            logger.warning("ログイン失敗: ユーザーが無効です user=%s", username)
            flash("このアカウントは無効になっています", "error")
            return render_template("login.html")

        # パスワード検証
        if not _verify_password(password, user.password_hash):
            logger.warning(
                "ログイン失敗: パスワードが正しくありません user=%s ip=%s",
                username,
                request.remote_addr,
            )
            flash("ユーザー名またはパスワードが正しくありません", "error")
            return render_template("login.html")

        # ログイン成功
        login_user(user)
        logger.info(
            "ユーザーがログインしました user=%s ip=%s",
            username,
            request.remote_addr,
        )
        flash("ログインしました", "success")

        # next パラメータがあればそこにリダイレクト
        next_page = request.args.get("next")
        if next_page and _is_safe_url(next_page):
            return redirect(next_page)

        return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    """ログアウト処理を行う。"""
    from flask_login import current_user

    username = current_user.username if current_user.is_authenticated else "unknown"
    logout_user()
    logger.info("ユーザーがログアウトしました user=%s", username)
    flash("ログアウトしました", "info")
    return redirect(url_for("auth.login"))


def _verify_password(password: str, password_hash: str) -> bool:
    """パスワードを検証する。

    Args:
        password: 入力されたパスワード
        password_hash: データベースに保存されているハッシュ

    Returns:
        パスワードが一致すればTrue
    """
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _is_safe_url(target: str) -> bool:
    """リダイレクト先が安全かどうかを確認する。

    Args:
        target: リダイレクト先URL

    Returns:
        安全であればTrue
    """
    from urllib.parse import urljoin, urlparse

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc
