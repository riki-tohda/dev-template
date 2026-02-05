"""認証ルートのテスト"""

import pytest


class TestLogin:
    """ログインのテスト"""

    def test_login_page_get(self, client):
        """ログインページが表示される"""
        response = client.get("/login")
        assert response.status_code == 200
        assert "ログイン" in response.data.decode("utf-8")

    def test_login_success(self, client):
        """正しい認証情報でログインできる"""
        response = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "ダッシュボード" in response.data.decode("utf-8")

    def test_login_wrong_password(self, client):
        """パスワードが間違っているとログインできない"""
        response = client.post(
            "/login",
            data={"username": "admin", "password": "wrongpassword"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "正しくありません" in response.data.decode("utf-8")

    def test_login_unknown_user(self, client):
        """存在しないユーザーでログインできない"""
        response = client.post(
            "/login",
            data={"username": "unknown", "password": "password"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "正しくありません" in response.data.decode("utf-8")

    def test_login_empty_fields(self, client):
        """空のフィールドでログインできない"""
        response = client.post(
            "/login",
            data={"username": "", "password": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "入力してください" in response.data.decode("utf-8")


class TestLogout:
    """ログアウトのテスト"""

    def test_logout_requires_login(self, client):
        """未ログイン状態でログアウトするとログインページにリダイレクト"""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_logout_success(self, client):
        """ログイン後にログアウトできる"""
        # ログイン
        client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
        )

        # ログアウト
        response = client.get("/logout", follow_redirects=True)
        assert response.status_code == 200
        assert "ログアウトしました" in response.data.decode("utf-8")


class TestLoginRequired:
    """認証必須ページのテスト"""

    def test_dashboard_requires_login(self, client):
        """ダッシュボードは認証が必要"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_resources_requires_login(self, client):
        """リソースページは認証が必要"""
        response = client.get("/resources/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_apps_requires_login(self, client):
        """アプリ管理ページは認証が必要"""
        response = client.get("/apps/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location
