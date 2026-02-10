"""アプリケーション管理ルートのテスト"""

import json
import platform
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAppsDetailPage:
    """アプリ詳細画面のテスト"""

    def test_detail_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/apps/test-app", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

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


class TestScriptsApi:
    """スクリプト API のテスト"""

    def test_get_scripts(self, admin_client):
        """スクリプト一覧を取得できる"""
        response = admin_client.get("/apps/api/test-app/scripts")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_get_scripts_requires_admin(self, user_client):
        """一般ユーザーはスクリプト一覧を取得できない"""
        response = user_client.get("/apps/api/test-app/scripts")
        assert response.status_code == 403

    def test_get_scripts_unauthenticated(self, client):
        """未認証ユーザーはスクリプト一覧を取得できない"""
        response = client.get("/apps/api/test-app/scripts")
        assert response.status_code == 401

    def test_get_scripts_app_not_found(self, admin_client):
        """存在しないアプリのスクリプト"""
        response = admin_client.get("/apps/api/nonexistent/scripts")
        assert response.status_code == 404

    def test_create_script(self, admin_client):
        """スクリプトを登録できる"""
        response = admin_client.post(
            "/apps/api/test-app/scripts",
            data=json.dumps({
                "id": "new-script",
                "name": "New Script",
                "script_path": "scripts/new.bat",
                "mode": "sync",
                "timeout": 60,
            }),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_create_script_requires_admin(self, user_client):
        """一般ユーザーはスクリプトを登録できない"""
        response = user_client.post(
            "/apps/api/test-app/scripts",
            data=json.dumps({
                "id": "new-script",
                "name": "New Script",
                "script_path": "scripts/new.bat",
            }),
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_create_script_missing_fields(self, admin_client):
        """必須フィールドが不足"""
        response = admin_client.post(
            "/apps/api/test-app/scripts",
            data=json.dumps({"id": "test"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_script_duplicate_id(self, admin_client):
        """重複ID"""
        # test-script は conftest で登録済み
        response = admin_client.post(
            "/apps/api/test-app/scripts",
            data=json.dumps({
                "id": "test-script",
                "name": "Duplicate",
                "script_path": "scripts/dup.bat",
            }),
            content_type="application/json",
        )
        assert response.status_code == 409

    def test_update_script(self, admin_client):
        """スクリプトを更新できる"""
        response = admin_client.put(
            "/apps/api/test-app/scripts/test-script",
            data=json.dumps({"name": "Updated Name"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_update_script_not_found(self, admin_client):
        """存在しないスクリプトの更新"""
        response = admin_client.put(
            "/apps/api/test-app/scripts/nonexistent",
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_delete_script(self, admin_client):
        """スクリプトを削除できる"""
        # まず新しいスクリプトを登録
        admin_client.post(
            "/apps/api/test-app/scripts",
            data=json.dumps({
                "id": "to-delete",
                "name": "Delete Me",
                "script_path": "scripts/del.bat",
            }),
            content_type="application/json",
        )

        response = admin_client.delete("/apps/api/test-app/scripts/to-delete")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_delete_script_not_found(self, admin_client):
        """存在しないスクリプトの削除"""
        response = admin_client.delete("/apps/api/test-app/scripts/nonexistent")
        assert response.status_code == 404

    def test_delete_script_requires_admin(self, user_client):
        """一般ユーザーはスクリプトを削除できない"""
        response = user_client.delete("/apps/api/test-app/scripts/test-script")
        assert response.status_code == 403


class TestScriptExecutionApi:
    """スクリプト実行 API のテスト"""

    def test_execute_requires_admin(self, user_client):
        """一般ユーザーはスクリプトを実行できない"""
        response = user_client.post("/apps/api/test-app/scripts/test-script/execute")
        assert response.status_code == 403

    def test_execute_unauthenticated(self, client):
        """未認証ユーザーはスクリプトを実行できない"""
        response = client.post("/apps/api/test-app/scripts/test-script/execute")
        assert response.status_code == 401

    def test_execute_script_not_found(self, admin_client):
        """存在しないスクリプトの実行"""
        response = admin_client.post("/apps/api/test-app/scripts/nonexistent/execute")
        assert response.status_code == 404

    def test_execute_sync(self, admin_client, app):
        """同期実行"""
        with patch("app.routes.apps._get_script_executor") as mock_get:
            from app.services.script_executor import ScriptExecutionResult

            mock_executor = MagicMock()
            mock_executor.validate_script.return_value = (True, "")
            mock_executor.execute_sync.return_value = ScriptExecutionResult(
                success=True,
                exit_code=0,
                stdout="hello",
                stderr="",
            )
            mock_get.return_value = mock_executor

            response = admin_client.post("/apps/api/test-app/scripts/test-script/execute")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["execution_id"] is not None

    def test_execute_validation_failure(self, admin_client, app):
        """バリデーション失敗"""
        with patch("app.routes.apps._get_script_executor") as mock_get:
            mock_executor = MagicMock()
            mock_executor.validate_script.return_value = (False, "パスが見つかりません")
            mock_get.return_value = mock_executor

            response = admin_client.post("/apps/api/test-app/scripts/test-script/execute")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_executions(self, admin_client):
        """実行履歴を取得できる"""
        response = admin_client.get("/apps/api/test-app/scripts/test-script/executions")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_get_executions_requires_admin(self, user_client):
        """一般ユーザーは実行履歴を取得できない"""
        response = user_client.get("/apps/api/test-app/scripts/test-script/executions")
        assert response.status_code == 403

    def test_get_execution_detail(self, admin_client, app):
        """実行結果詳細を取得できる"""
        # まず実行レコードを作成
        with patch("app.routes.apps._get_script_executor") as mock_get:
            from app.services.script_executor import ScriptExecutionResult

            mock_executor = MagicMock()
            mock_executor.validate_script.return_value = (True, "")
            mock_executor.execute_sync.return_value = ScriptExecutionResult(
                success=True, exit_code=0, stdout="ok", stderr=""
            )
            mock_get.return_value = mock_executor

            resp = admin_client.post("/apps/api/test-app/scripts/test-script/execute")
            exec_id = json.loads(resp.data)["execution_id"]

        response = admin_client.get(f"/apps/api/scripts/executions/{exec_id}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == exec_id

    def test_get_execution_detail_not_found(self, admin_client):
        """存在しない実行レコード"""
        response = admin_client.get("/apps/api/scripts/executions/99999")
        assert response.status_code == 404
