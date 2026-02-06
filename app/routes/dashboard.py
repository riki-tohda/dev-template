"""ダッシュボードのルート"""

from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    """ダッシュボードを表示する。

    リソース状況とアプリケーション状態の概要を表示する。
    詳細データはJavaScriptからAPIで取得する。
    """
    return render_template("dashboard.html")
