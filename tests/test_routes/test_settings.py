"""設定管理ルートのテスト"""

from datetime import datetime


class TestSettingsAccess:
    """設定画面のアクセス制御テスト"""

    def test_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/settings/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_admin(self, user_client):
        """一般ユーザーはリダイレクトされる"""
        response = user_client.get("/settings/", follow_redirects=False)
        assert response.status_code == 302

    def test_admin_can_access(self, admin_client):
        """管理者はアクセスできる"""
        response = admin_client.get("/settings/")
        assert response.status_code == 200


class TestServerSettings:
    """サーバー設定のテスト"""

    def test_page_display(self, admin_client):
        """サーバー設定画面が表示される"""
        response = admin_client.get("/settings/server")
        assert response.status_code == 200

    def test_save_valid_port(self, admin_client):
        """有効なポートを保存できる"""
        response = admin_client.post(
            "/settings/server",
            data={"port": "9000"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "保存しました" in response.data.decode("utf-8")

    def test_save_invalid_port(self, admin_client):
        """無効なポート（範囲外）でエラー"""
        response = admin_client.post(
            "/settings/server",
            data={"port": "80"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1024-65535" in response.data.decode("utf-8")

    def test_user_cannot_access(self, user_client):
        """一般ユーザーはアクセスできない"""
        response = user_client.get("/settings/server", follow_redirects=False)
        assert response.status_code == 302


class TestSessionSettings:
    """セッション設定のテスト"""

    def test_page_display(self, admin_client):
        """セッション設定画面が表示される"""
        response = admin_client.get("/settings/session")
        assert response.status_code == 200

    def test_save_valid_lifetime(self, admin_client):
        """有効なセッション時間を保存できる"""
        response = admin_client.post(
            "/settings/session",
            data={"lifetime_hours": "48"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "保存しました" in response.data.decode("utf-8")

    def test_save_invalid_lifetime(self, admin_client):
        """無効なセッション時間（範囲外）でエラー"""
        response = admin_client.post(
            "/settings/session",
            data={"lifetime_hours": "200"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1-168" in response.data.decode("utf-8")


class TestUserManagement:
    """ユーザー管理のテスト"""

    def test_users_list(self, admin_client):
        """ユーザー一覧が表示される"""
        response = admin_client.get("/settings/users")
        assert response.status_code == 200
        assert "admin" in response.data.decode("utf-8")

    def test_users_add_page(self, admin_client):
        """ユーザー追加画面が表示される"""
        response = admin_client.get("/settings/users/add")
        assert response.status_code == 200

    def test_users_add_success(self, admin_client):
        """ユーザーを追加できる"""
        response = admin_client.post(
            "/settings/users/add",
            data={"username": "newuser", "password": "newpass", "role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "作成しました" in response.data.decode("utf-8")

    def test_users_add_short_username(self, admin_client):
        """ユーザー名が短すぎるとエラー"""
        response = admin_client.post(
            "/settings/users/add",
            data={"username": "ab", "password": "password", "role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "3-32" in response.data.decode("utf-8")

    def test_users_add_short_password(self, admin_client):
        """パスワードが短すぎるとエラー"""
        response = admin_client.post(
            "/settings/users/add",
            data={"username": "newuser2", "password": "ab", "role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "4文字" in response.data.decode("utf-8")

    def test_users_add_duplicate(self, admin_client):
        """重複ユーザー名はエラー"""
        response = admin_client.post(
            "/settings/users/add",
            data={"username": "admin", "password": "password", "role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "既に使用" in response.data.decode("utf-8")

    def test_users_edit_page(self, admin_client):
        """ユーザー編集画面が表示される"""
        response = admin_client.get("/settings/users/1/edit")
        assert response.status_code == 200

    def test_users_edit_not_found(self, admin_client):
        """存在しないユーザーの編集は 404"""
        response = admin_client.get("/settings/users/999/edit")
        assert response.status_code == 404

    def test_user_cannot_manage_users(self, user_client):
        """一般ユーザーはユーザー管理にアクセスできない"""
        response = user_client.get("/settings/users", follow_redirects=False)
        assert response.status_code == 302


class TestResourceSettings:
    """リソース監視設定のテスト"""

    def test_page_display(self, admin_client):
        """リソース設定画面が表示される"""
        response = admin_client.get("/settings/resource")
        assert response.status_code == 200

    def test_save_valid_thresholds(self, admin_client):
        """有効な閾値を保存できる"""
        response = admin_client.post(
            "/settings/resource",
            data={
                "cpu_threshold": "70",
                "memory_threshold": "75",
                "disk_threshold": "85",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "保存しました" in response.data.decode("utf-8")

    def test_save_invalid_threshold(self, admin_client):
        """無効な閾値でエラー"""
        response = admin_client.post(
            "/settings/resource",
            data={
                "cpu_threshold": "150",
                "memory_threshold": "80",
                "disk_threshold": "90",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1-100%" in response.data.decode("utf-8")


class TestAppInstallSettings:
    """アプリインストール設定のテスト"""

    def test_page_display(self, admin_client):
        """アプリインストール設定画面が表示される"""
        response = admin_client.get("/settings/app-install")
        assert response.status_code == 200

    def test_save_install_dir(self, admin_client):
        """インストールディレクトリを保存できる"""
        response = admin_client.post(
            "/settings/app-install",
            data={"install_dir": "/opt/custom-apps"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "保存しました" in response.data.decode("utf-8")

    def test_save_empty_install_dir(self, admin_client):
        """空のインストールディレクトリでエラー"""
        response = admin_client.post(
            "/settings/app-install",
            data={"install_dir": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "入力してください" in response.data.decode("utf-8")


class TestLoggingSettings:
    """ログ設定のテスト"""

    def test_page_display(self, admin_client):
        """ログ設定画面が表示される"""
        response = admin_client.get("/settings/logging")
        assert response.status_code == 200
        assert "ログ設定" in response.data.decode("utf-8")

    def test_save_valid_settings(self, admin_client):
        """有効なログ設定を保存できる"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "14",
                "archive_retention_days": "60",
                "max_size_mb": "20",
                "max_folder_size_mb": "200",
                "backup_count": "5",
                "maintenance_interval_hours": "12",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "保存しました" in response.data.decode("utf-8")

    def test_invalid_retention_days(self, admin_client):
        """無効なログ保持期間でエラー"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "0",
                "archive_retention_days": "30",
                "max_size_mb": "10",
                "max_folder_size_mb": "500",
                "backup_count": "3",
                "maintenance_interval_hours": "24",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1-365" in response.data.decode("utf-8")

    def test_invalid_archive_retention(self, admin_client):
        """無効なアーカイブ保持期間でエラー"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "7",
                "archive_retention_days": "400",
                "max_size_mb": "10",
                "max_folder_size_mb": "500",
                "backup_count": "3",
                "maintenance_interval_hours": "24",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1-365" in response.data.decode("utf-8")

    def test_invalid_max_file_size(self, admin_client):
        """無効な1ファイル最大サイズでエラー"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "7",
                "archive_retention_days": "30",
                "max_size_mb": "0",
                "max_folder_size_mb": "500",
                "backup_count": "3",
                "maintenance_interval_hours": "24",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1-100" in response.data.decode("utf-8")

    def test_invalid_max_folder_size(self, admin_client):
        """無効な最大フォルダサイズでエラー"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "7",
                "archive_retention_days": "30",
                "max_size_mb": "10",
                "max_folder_size_mb": "5",
                "backup_count": "3",
                "maintenance_interval_hours": "24",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "10-10000" in response.data.decode("utf-8")

    def test_invalid_backup_count(self, admin_client):
        """無効なバックアップ数でエラー"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "7",
                "archive_retention_days": "30",
                "max_size_mb": "10",
                "max_folder_size_mb": "500",
                "backup_count": "0",
                "maintenance_interval_hours": "24",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "1-10" in response.data.decode("utf-8")

    def test_invalid_maintenance_interval(self, admin_client):
        """無効なメンテナンス間隔でエラー"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "7",
                "archive_retention_days": "30",
                "max_size_mb": "10",
                "max_folder_size_mb": "500",
                "backup_count": "3",
                "maintenance_interval_hours": "200",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "0-168" in response.data.decode("utf-8")

    def test_save_zero_interval_disables(self, admin_client):
        """メンテナンス間隔0で保存できる（無効化）"""
        response = admin_client.post(
            "/settings/logging",
            data={
                "retention_days": "7",
                "archive_retention_days": "30",
                "max_size_mb": "10",
                "max_folder_size_mb": "500",
                "backup_count": "3",
                "maintenance_interval_hours": "0",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "保存しました" in response.data.decode("utf-8")

    def test_user_cannot_access(self, user_client):
        """一般ユーザーはアクセスできない"""
        response = user_client.get("/settings/logging", follow_redirects=False)
        assert response.status_code == 302


class TestLoggingApi:
    """ログAPIのテスト"""

    def test_stats_api(self, admin_client):
        """統計APIが正常に応答する"""
        response = admin_client.get("/settings/logging/api/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "total_size_mb" in data
        assert "scheduler_active" in data

    def test_maintenance_api(self, admin_client):
        """メンテナンスAPIが正常に応答する"""
        response = admin_client.post("/settings/logging/api/maintenance")
        assert response.status_code == 200
        data = response.get_json()
        assert "archived" in data
        assert "deleted_logs" in data

    def test_stats_api_requires_admin(self, user_client):
        """統計APIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logging/api/stats", follow_redirects=False
        )
        assert response.status_code == 302

    def test_maintenance_api_requires_admin(self, user_client):
        """メンテナンスAPIは管理者権限が必要"""
        response = user_client.post(
            "/settings/logging/api/maintenance", follow_redirects=False
        )
        assert response.status_code == 302


class TestPasswordChange:
    """パスワード変更のテスト"""

    def test_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/settings/profile/password", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_page_display(self, user_client):
        """一般ユーザーもパスワード変更画面にアクセスできる"""
        response = user_client.get("/settings/profile/password")
        assert response.status_code == 200

    def test_change_password_success(self, admin_client):
        """パスワードを変更できる"""
        response = admin_client.post(
            "/settings/profile/password",
            data={
                "current_password": "admin",
                "new_password": "newpass123",
                "confirm_password": "newpass123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "変更しました" in response.data.decode("utf-8")

    def test_change_password_wrong_current(self, admin_client):
        """現在のパスワードが間違っている場合"""
        response = admin_client.post(
            "/settings/profile/password",
            data={
                "current_password": "wrongpassword",
                "new_password": "newpass123",
                "confirm_password": "newpass123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "正しくありません" in response.data.decode("utf-8")

    def test_change_password_too_short(self, admin_client):
        """新しいパスワードが短すぎる場合"""
        response = admin_client.post(
            "/settings/profile/password",
            data={
                "current_password": "admin",
                "new_password": "ab",
                "confirm_password": "ab",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "4文字" in response.data.decode("utf-8")

    def test_change_password_mismatch(self, admin_client):
        """確認パスワードが一致しない場合"""
        response = admin_client.post(
            "/settings/profile/password",
            data={
                "current_password": "admin",
                "new_password": "newpass123",
                "confirm_password": "different",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "一致しません" in response.data.decode("utf-8")


class TestLogViewer:
    """ログビューアのテスト"""

    def test_page_display(self, admin_client):
        """ログビューア画面が表示される"""
        response = admin_client.get("/settings/logs")
        assert response.status_code == 200
        assert "ログビューア" in response.data.decode("utf-8")

    def test_requires_admin(self, user_client):
        """一般ユーザーはリダイレクトされる"""
        response = user_client.get("/settings/logs", follow_redirects=False)
        assert response.status_code == 302

    def test_requires_login(self, client):
        """未ログインでリダイレクトされる"""
        response = client.get("/settings/logs", follow_redirects=False)
        assert response.status_code == 302

    def test_files_api(self, admin_client):
        """ファイル一覧APIが応答する"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = admin_client.get(f"/settings/logs/api/files?date={today}")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_files_api_invalid_date(self, admin_client):
        """不正な日付でエラーが返る"""
        response = admin_client.get("/settings/logs/api/files?date=invalid")
        assert response.status_code == 400

    def test_content_api(self, admin_client, app):
        """コンテンツAPIが応答する"""
        # ログエントリを生成
        from app.services.log_manager import get_logger

        with app.app_context():
            test_logger = get_logger("app")
            test_logger.info("viewer test entry")

        today = datetime.now().strftime("%Y-%m-%d")
        response = admin_client.get(
            f"/settings/logs/api/content?date={today}&type=app&lines=100"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "lines" in data
        assert "total" in data

    def test_content_api_missing_params(self, admin_client):
        """パラメータ不足でエラーが返る"""
        response = admin_client.get("/settings/logs/api/content?date=2025-01-01")
        assert response.status_code == 400

    def test_content_api_invalid_type(self, admin_client):
        """不正なログ種別でエラーが返る"""
        response = admin_client.get(
            "/settings/logs/api/content?date=2025-01-01&type=../../etc"
        )
        assert response.status_code == 400

    def test_files_api_requires_admin(self, user_client):
        """ファイルAPIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/files?date=2025-01-01",
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_content_api_requires_admin(self, user_client):
        """コンテンツAPIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/content?date=2025-01-01&type=app",
            follow_redirects=False,
        )
        assert response.status_code == 302


class TestLogViewerEnhancedAPI:
    """拡張ログビューアAPIのテスト"""

    def test_files_metadata_api(self, admin_client):
        """メタデータ付きファイル一覧APIが応答する"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = admin_client.get(f"/settings/logs/api/files-metadata?date={today}")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_files_metadata_api_invalid_date(self, admin_client):
        """不正な日付でエラーが返る"""
        response = admin_client.get("/settings/logs/api/files-metadata?date=invalid")
        assert response.status_code == 400

    def test_files_metadata_api_requires_admin(self, user_client):
        """メタデータAPIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/files-metadata?date=2025-01-01",
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_statistics_api(self, admin_client):
        """統計APIが応答する"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = admin_client.get(
            f"/settings/logs/api/statistics?start={today}&end={today}"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "total_files" in data
        assert "total_size_bytes" in data
        assert "info_count" in data
        assert "warning_count" in data
        assert "error_count" in data

    def test_statistics_api_invalid_date(self, admin_client):
        """統計APIに不正な日付でエラー"""
        response = admin_client.get(
            "/settings/logs/api/statistics?start=invalid&end=2025-01-01"
        )
        assert response.status_code == 400

    def test_statistics_api_requires_admin(self, user_client):
        """統計APIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/statistics?start=2025-01-01&end=2025-01-01",
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_archives_api(self, admin_client):
        """アーカイブAPIが応答する"""
        response = admin_client.get("/settings/logs/api/archives")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_archives_api_requires_admin(self, user_client):
        """アーカイブAPIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/archives", follow_redirects=False
        )
        assert response.status_code == 302

    def test_content_structured_api(self, admin_client, app):
        """構造化コンテンツAPIが応答する"""
        from app.services.log_manager import get_logger

        with app.app_context():
            test_logger = get_logger("app")
            test_logger.info("structured test entry")

        today = datetime.now().strftime("%Y-%m-%d")
        response = admin_client.get(
            f"/settings/logs/api/content-structured?date={today}&type=app&lines=100"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "entries" in data
        assert "total" in data

    def test_content_structured_api_missing_params(self, admin_client):
        """パラメータ不足でエラー"""
        response = admin_client.get(
            "/settings/logs/api/content-structured?date=2025-01-01"
        )
        assert response.status_code == 400

    def test_content_structured_api_requires_admin(self, user_client):
        """構造化APIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/content-structured?date=2025-01-01&type=app",
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_download_api(self, admin_client, app):
        """ダウンロードAPIが応答する"""
        from app.services.log_manager import get_logger

        with app.app_context():
            test_logger = get_logger("app")
            test_logger.info("download test entry")

        today = datetime.now().strftime("%Y-%m-%d")
        response = admin_client.get(f"/settings/logs/api/download/{today}/app")
        assert response.status_code == 200
        assert response.content_type in (
            "text/x-log",
            "application/octet-stream",
            "text/plain; charset=utf-8",
        )

    def test_download_api_invalid_date(self, admin_client):
        """不正な日付でダウンロードエラー"""
        response = admin_client.get("/settings/logs/api/download/invalid/app")
        assert response.status_code == 400

    def test_download_api_not_found(self, admin_client):
        """存在しないファイルで404"""
        response = admin_client.get("/settings/logs/api/download/1999-01-01/app")
        assert response.status_code == 404

    def test_download_api_requires_admin(self, user_client):
        """ダウンロードAPIは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/download/2025-01-01/app",
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_download_archive_api_invalid_filename(self, admin_client):
        """不正なアーカイブファイル名でエラー"""
        response = admin_client.get(
            "/settings/logs/api/download-archive/../../etc/passwd"
        )
        assert response.status_code in (400, 404)

    def test_download_archive_api_not_found(self, admin_client):
        """存在しないアーカイブで404"""
        response = admin_client.get(
            "/settings/logs/api/download-archive/1999-01-01.tar.gz"
        )
        assert response.status_code == 404

    def test_download_archive_api_requires_admin(self, user_client):
        """アーカイブDLは管理者権限が必要"""
        response = user_client.get(
            "/settings/logs/api/download-archive/2025-01-01.tar.gz",
            follow_redirects=False,
        )
        assert response.status_code == 302


class TestAccessLogging:
    """アクセスログのテスト"""

    def test_access_log_recorded(self, admin_client, app):
        """リクエスト後にアクセスログが記録される"""
        # ダッシュボードにアクセス
        admin_client.get("/")

        today = datetime.now().strftime("%Y-%m-%d")

        from app.services.log_manager import read_log_tail

        lines = read_log_tail(today, "access")
        assert len(lines) > 0
        # アクセスログにダッシュボードへのアクセスが含まれる
        found = any("path=/" in line and "method=GET" in line for line in lines)
        assert found

    def test_static_excluded(self, admin_client, app):
        """/static/ はアクセスログに記録されない"""
        admin_client.get("/static/nonexistent.css")

        today = datetime.now().strftime("%Y-%m-%d")

        from app.services.log_manager import read_log_tail

        lines = read_log_tail(today, "access")
        static_lines = [line for line in lines if "path=/static/" in line]
        assert len(static_lines) == 0
