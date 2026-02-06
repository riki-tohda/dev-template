"""プロキシルートのテスト"""


class TestProxyRoute:
    """プロキシルートのテスト"""

    def test_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/proxy/test-app/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_app_not_found(self, admin_client):
        """存在しないアプリは404"""
        response = admin_client.get("/proxy/nonexistent-app/")
        assert response.status_code == 404

    def test_app_not_installed(self, admin_client, app):
        """未インストールのアプリは404"""
        # test-appはデフォルトで未インストール
        response = admin_client.get("/proxy/test-app/")
        assert response.status_code == 404

    def test_proxy_disabled(self, admin_client, app):
        """プロキシが無効なアプリは403"""
        from app import get_db

        with app.app_context():
            db = get_db()
            test_app = db.get_application("test-app")
            test_app.installed = True
            test_app.proxy_enabled = False
            db.update_application(test_app)

        response = admin_client.get("/proxy/test-app/")
        assert response.status_code == 403

        # 元に戻す
        with app.app_context():
            db = get_db()
            test_app = db.get_application("test-app")
            test_app.installed = False
            test_app.proxy_enabled = True
            db.update_application(test_app)

    def test_proxy_connection_error(self, admin_client, app):
        """バックエンドに接続できない場合は502"""
        from app import get_db

        with app.app_context():
            db = get_db()
            test_app = db.get_application("test-app")
            test_app.installed = True
            db.update_application(test_app)

        # バックエンドが起動していないので502になる
        response = admin_client.get("/proxy/test-app/")
        assert response.status_code == 502

        # 元に戻す
        with app.app_context():
            db = get_db()
            test_app = db.get_application("test-app")
            test_app.installed = False
            db.update_application(test_app)


class TestRewriteHtml:
    """HTML書き換えのテスト"""

    def test_rewrite_absolute_paths(self):
        """絶対パスが書き換えられる"""
        from app.routes.proxy import _rewrite_html

        html = '<a href="/page">Link</a>'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<a href="/proxy/app1/page">Link</a>'

    def test_rewrite_relative_paths(self):
        """相対パスが書き換えられる"""
        from app.routes.proxy import _rewrite_html

        html = '<a href="page.html">Link</a>'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<a href="/proxy/app1/page.html">Link</a>'

    def test_preserve_external_urls(self):
        """外部URLは書き換えない"""
        from app.routes.proxy import _rewrite_html

        html = '<a href="https://example.com">Link</a>'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<a href="https://example.com">Link</a>'

    def test_preserve_javascript_urls(self):
        """javascript: URLは書き換えない"""
        from app.routes.proxy import _rewrite_html

        html = '<a href="javascript:void(0)">Link</a>'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<a href="javascript:void(0)">Link</a>'

    def test_preserve_anchor_links(self):
        """アンカーリンクは書き換えない"""
        from app.routes.proxy import _rewrite_html

        html = '<a href="#section">Link</a>'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<a href="#section">Link</a>'

    def test_rewrite_src_attribute(self):
        """src属性も書き換えられる"""
        from app.routes.proxy import _rewrite_html

        html = '<img src="/images/logo.png">'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<img src="/proxy/app1/images/logo.png">'

    def test_rewrite_action_attribute(self):
        """action属性も書き換えられる"""
        from app.routes.proxy import _rewrite_html

        html = '<form action="/submit">'
        result = _rewrite_html(html, "app1", "/proxy/app1")
        assert result == '<form action="/proxy/app1/submit">'


class TestRewriteLocation:
    """Locationヘッダー書き換えのテスト"""

    def test_rewrite_localhost_url(self):
        """localhost URLが書き換えられる"""
        from app.routes.proxy import _rewrite_location

        result = _rewrite_location("http://localhost:5001/dashboard", "app1", 5001)
        assert result == "/proxy/app1/dashboard"

    def test_rewrite_absolute_path(self):
        """絶対パスが書き換えられる"""
        from app.routes.proxy import _rewrite_location

        result = _rewrite_location("/dashboard", "app1", 5001)
        assert result == "/proxy/app1/dashboard"

    def test_preserve_external_url(self):
        """外部URLは書き換えない"""
        from app.routes.proxy import _rewrite_location

        result = _rewrite_location("https://example.com/page", "app1", 5001)
        assert result == "https://example.com/page"
