"""リバースプロキシのルート"""

import re
import urllib.error
import urllib.request

from flask import Blueprint, Response, abort, current_app, request
from flask_login import current_user, login_required

from app import get_db

bp = Blueprint("proxy", __name__, url_prefix="/proxy")

# プロキシしないヘッダー
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _rewrite_html(content: str, app_id: str, base_path: str) -> str:
    """HTML内の相対リンクをプロキシパスに書き換える。

    Args:
        content: HTMLコンテンツ
        app_id: アプリケーションID
        base_path: プロキシのベースパス（例: /proxy/app1）

    Returns:
        書き換え後のHTMLコンテンツ
    """
    # href="/path" → href="/proxy/app1/path"
    content = re.sub(
        r'(href|src|action)=["\']\/([^"\']*)["\']',
        rf'\1="{base_path}/\2"',
        content,
    )

    # href="path" (相対パス、http/https/javascript/mailto/# を除く)
    content = re.sub(
        r'(href|src|action)=["\'](?!https?:|javascript:|mailto:|#|/proxy/)([^"\':/][^"\']*)["\']',
        rf'\1="{base_path}/\2"',
        content,
    )

    return content


@bp.route("/<app_id>/")
@bp.route("/<app_id>/<path:path>")
@login_required
def proxy(app_id: str, path: str = ""):
    """アプリケーションへのリクエストをプロキシする。

    Args:
        app_id: アプリケーションID
        path: リクエストパス

    Returns:
        プロキシされたレスポンス
    """
    db = get_db()
    app = db.get_application(app_id)

    if app is None:
        abort(404)

    if not app.installed:
        abort(404, description="アプリケーションがインストールされていません")

    # プロキシが有効か確認
    if not app.proxy_enabled:
        abort(403, description="このアプリケーションはプロキシ経由でのアクセスが無効です")

    # ターゲットURLを構築
    target_url = f"http://localhost:{app.port}/{path}"
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"

    # リクエストヘッダーを準備
    headers = {}
    for key, value in request.headers:
        key_lower = key.lower()
        if key_lower not in HOP_BY_HOP_HEADERS and key_lower != "host":
            headers[key] = value

    # X-Forwarded ヘッダーを追加
    headers["X-Forwarded-For"] = request.remote_addr
    headers["X-Forwarded-Proto"] = request.scheme
    headers["X-Forwarded-Host"] = request.host
    headers["X-POL-User"] = current_user.username

    try:
        # リクエストを転送
        req = urllib.request.Request(
            target_url,
            data=request.get_data() if request.method in ("POST", "PUT", "PATCH") else None,
            headers=headers,
            method=request.method,
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            # レスポンスヘッダーを準備
            response_headers = {}
            for key, value in response.getheaders():
                key_lower = key.lower()
                if key_lower not in HOP_BY_HOP_HEADERS:
                    # Locationヘッダーの書き換え
                    if key_lower == "location":
                        value = _rewrite_location(value, app_id, app.port)
                    response_headers[key] = value

            # コンテンツを取得
            content = response.read()
            content_type = response.getheader("Content-Type", "")

            # HTMLの場合は相対リンクを書き換え
            if app.proxy_rewrite_urls and "text/html" in content_type:
                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].split(";")[0].strip()

                try:
                    html = content.decode(charset)
                    base_path = f"/proxy/{app_id}"
                    html = _rewrite_html(html, app_id, base_path)
                    content = html.encode(charset)
                except (UnicodeDecodeError, LookupError):
                    pass  # デコードできない場合はそのまま

            return Response(
                content,
                status=response.status,
                headers=response_headers,
            )

    except urllib.error.HTTPError as e:
        return Response(
            e.read(),
            status=e.code,
            headers=dict(e.headers),
        )
    except urllib.error.URLError as e:
        current_app.logger.error(f"プロキシエラー: {e}")
        abort(502, description="アプリケーションに接続できません")
    except TimeoutError:
        abort(504, description="アプリケーションからの応答がタイムアウトしました")


def _rewrite_location(location: str, app_id: str, port: int) -> str:
    """Locationヘッダーを書き換える。

    Args:
        location: 元のLocationヘッダー値
        app_id: アプリケーションID
        port: アプリケーションのポート番号

    Returns:
        書き換え後のLocationヘッダー値
    """
    # 絶対URLでlocalhostの場合
    if location.startswith(f"http://localhost:{port}"):
        return location.replace(f"http://localhost:{port}", f"/proxy/{app_id}")

    # 相対パスの場合
    if location.startswith("/"):
        return f"/proxy/{app_id}{location}"

    return location
