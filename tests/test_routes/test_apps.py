"""アプリケーション管理ルートのテスト"""

import json
from unittest.mock import MagicMock, patch


class TestAppsPage:
    """アプリ一覧画面のテスト"""

    def test_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/apps/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_index_display(self, admin_client):
        """アプリ一覧が表示される"""
        response = admin_client.get("/apps/")
        assert response.status_code == 200

    def test_detail_display(self, admin_client):
        """アプリ詳細が表示される"""
        response = admin_client.get("/apps/test-app")
        assert response.status_code == 200

    def test_detail_not_found(self, admin_client):
        """存在しないアプリの詳細は 404"""
        response = admin_client.get("/apps/nonexistent-app")
        assert response.status_code == 404


class TestAppsStatusApi:
    """アプリ状態 API のテスト"""

    def test_api_status_requires_login(self, client):
        """未ログイン状態で API にアクセスできない"""
        response = client.get("/apps/api/status", follow_redirects=False)
        assert response.status_code == 302

    def test_api_all_status(self, admin_client):
        """全アプリの状態を取得できる"""
        response = admin_client.get("/apps/api/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) >= 1

        app_data = data[0]
        assert "id" in app_data
        assert "name" in app_data
        assert "status" in app_data

    def test_api_app_status(self, admin_client):
        """特定アプリの状態を取得できる"""
        response = admin_client.get("/apps/api/test-app/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "status" in data

    def test_api_app_status_not_found(self, admin_client):
        """存在しないアプリの状態は 404"""
        response = admin_client.get("/apps/api/nonexistent-app/status")
        assert response.status_code == 404


class TestAppsControlApi:
    """アプリ操作 API のテスト"""

    def test_start(self, admin_client):
        """アプリを起動できる"""
        response = admin_client.post("/apps/api/test-app/start")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "success" in data

    def test_stop(self, admin_client):
        """アプリを停止できる"""
        response = admin_client.post("/apps/api/test-app/stop")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "success" in data

    def test_restart(self, admin_client):
        """アプリを再起動できる"""
        response = admin_client.post("/apps/api/test-app/restart")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "success" in data


class TestAppsInstallApi:
    """アプリインストール API のテスト"""

    def test_install_requires_admin(self, user_client):
        """一般ユーザーはインストールできない"""
        response = user_client.post("/apps/api/test-app/install")
        assert response.status_code == 403

    def test_update_requires_admin(self, user_client):
        """一般ユーザーはアップデートできない"""
        response = user_client.post("/apps/api/test-app/update")
        assert response.status_code == 403

    def test_uninstall_requires_admin(self, user_client):
        """一般ユーザーはアンインストールできない"""
        response = user_client.post("/apps/api/test-app/uninstall")
        assert response.status_code == 403

    def test_install_unauthenticated(self, client):
        """未認証ユーザーはインストールできない"""
        response = client.post("/apps/api/test-app/install")
        assert response.status_code == 401

    def test_check_update(self, admin_client):
        """アップデート確認 API"""
        with patch("app.routes.apps._get_installer") as mock_get:
            mock_installer = MagicMock()
            mock_installer.check_update.return_value = None
            mock_get.return_value = mock_installer

            response = admin_client.get("/apps/api/test-app/check-update")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["has_update"] is False

    def test_check_update_app_not_found(self, admin_client):
        """存在しないアプリのアップデート確認"""
        response = admin_client.get("/apps/api/nonexistent-app/check-update")
        assert response.status_code == 404
