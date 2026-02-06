"""リソースモニタのルート"""

from flask import Blueprint, current_app, jsonify
from flask_login import login_required

from app.services.resource_monitor import create_monitor_from_config

bp = Blueprint("resources", __name__, url_prefix="/resources")


@bp.route("/api/status")
@login_required
def api_status():
    """リソース状態をJSON形式で返す。

    Returns:
        JSON: CPU、メモリ、ディスク、システム情報
    """
    monitor = create_monitor_from_config(current_app.config)
    status = monitor.get_status()
    return jsonify(status.to_dict())
