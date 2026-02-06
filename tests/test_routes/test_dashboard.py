"""ダッシュボードルートのテスト"""


class TestDashboard:
    """ダッシュボード画面のテスト"""

    def test_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_dashboard_display(self, admin_client):
        """ログイン後にダッシュボードが表示される"""
        response = admin_client.get("/")
        assert response.status_code == 200
        assert "ダッシュボード" in response.data.decode("utf-8")

    def test_dashboard_accessible_by_user(self, user_client):
        """一般ユーザーもダッシュボードにアクセスできる"""
        response = user_client.get("/")
        assert response.status_code == 200
        assert "ダッシュボード" in response.data.decode("utf-8")

    def test_dashboard_contains_resource_section(self, admin_client):
        """ダッシュボードにリソース状況セクションがある"""
        response = admin_client.get("/")
        html = response.data.decode("utf-8")
        assert "リソース状況" in html
        assert "CPU" in html
        assert "メモリ" in html

    def test_dashboard_contains_apps_section(self, admin_client):
        """ダッシュボードにアプリケーション状態セクションがある"""
        response = admin_client.get("/")
        html = response.data.decode("utf-8")
        assert "アプリケーション状態" in html

    def test_dashboard_contains_apps_table_columns(self, admin_client):
        """ダッシュボードのアプリテーブルに必要なカラムがある"""
        response = admin_client.get("/")
        html = response.data.decode("utf-8")
        assert "アプリ名" in html
        assert "バージョン" in html
        assert "状態" in html
        assert "操作" in html
