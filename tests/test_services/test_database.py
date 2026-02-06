"""Databaseのテスト"""

from datetime import datetime
from pathlib import Path

import bcrypt
import pytest

from app.services.database import Database
from app.services.models import Application, InitialUser


class TestDatabaseInitialization:
    """データベース初期化のテスト"""

    def test_initialize_creates_tables(self, tmp_path: Path) -> None:
        """テーブルが作成される"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()

        assert db.is_initialized()

    def test_is_initialized_false_when_no_db(self, tmp_path: Path) -> None:
        """DBファイルがない場合はFalse"""
        db_path = tmp_path / "nonexistent.db"
        db = Database(db_path)

        assert not db.is_initialized()

    def test_has_users_false_when_empty(self, tmp_path: Path) -> None:
        """ユーザーがいない場合はFalse"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()

        assert not db.has_users()


class TestUserOperations:
    """ユーザー操作のテスト"""

    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        """テスト用データベース"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()
        return db

    def test_create_user(self, db: Database) -> None:
        """ユーザー作成"""
        user = InitialUser(username="testuser", password="testpass", role="user")
        user_id = db.create_user(user)

        assert user_id > 0
        assert db.has_users()

    def test_get_user_by_username(self, db: Database) -> None:
        """ユーザー名でユーザー取得"""
        user = InitialUser(username="testuser", password="testpass", role="admin")
        db.create_user(user)

        result = db.get_user_by_username("testuser")

        assert result is not None
        assert result.username == "testuser"
        assert result.role == "admin"
        assert bcrypt.checkpw(b"testpass", result.password_hash.encode("utf-8"))

    def test_get_user_by_username_not_found(self, db: Database) -> None:
        """存在しないユーザー名"""
        result = db.get_user_by_username("nonexistent")

        assert result is None

    def test_get_user_by_id(self, db: Database) -> None:
        """IDでユーザー取得"""
        user = InitialUser(username="testuser", password="testpass", role="user")
        user_id = db.create_user(user)

        result = db.get_user_by_id(user_id)

        assert result is not None
        assert result.id == user_id
        assert result.username == "testuser"

    def test_get_user_by_id_not_found(self, db: Database) -> None:
        """存在しないID"""
        result = db.get_user_by_id(9999)

        assert result is None

    def test_update_user(self, db: Database) -> None:
        """ユーザー更新"""
        user = InitialUser(username="testuser", password="testpass", role="user")
        user_id = db.create_user(user)

        result = db.get_user_by_id(user_id)
        assert result is not None

        result.role = "admin"
        result.enabled = False
        db.update_user(result)

        updated = db.get_user_by_id(user_id)
        assert updated is not None
        assert updated.role == "admin"
        assert updated.enabled is False

    def test_get_all_users(self, db: Database) -> None:
        """全ユーザー取得"""
        db.create_user(InitialUser(username="user1", password="pass1", role="admin"))
        db.create_user(InitialUser(username="user2", password="pass2", role="user"))

        users = db.get_all_users()

        assert len(users) == 2
        assert users[0].username == "user1"
        assert users[1].username == "user2"


class TestSettingsOperations:
    """設定操作のテスト"""

    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        """テスト用データベース"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()
        return db

    def test_set_and_get_setting_string(self, db: Database) -> None:
        """文字列設定の保存と取得"""
        db.set_setting("test.key", "test_value", "test")
        result = db.get_setting("test.key")

        assert result == "test_value"

    def test_set_and_get_setting_number(self, db: Database) -> None:
        """数値設定の保存と取得"""
        db.set_setting("test.port", 8000, "test")
        result = db.get_setting("test.port")

        assert result == 8000

    def test_set_and_get_setting_boolean(self, db: Database) -> None:
        """真偽値設定の保存と取得"""
        db.set_setting("test.enabled", True, "test")
        result = db.get_setting("test.enabled")

        assert result is True

    def test_set_and_get_setting_list(self, db: Database) -> None:
        """リスト設定の保存と取得"""
        db.set_setting("test.paths", ["/", "/home"], "test")
        result = db.get_setting("test.paths")

        assert result == ["/", "/home"]

    def test_set_and_get_setting_dict(self, db: Database) -> None:
        """辞書設定の保存と取得"""
        db.set_setting("test.config", {"key": "value"}, "test")
        result = db.get_setting("test.config")

        assert result == {"key": "value"}

    def test_get_setting_default(self, db: Database) -> None:
        """存在しない設定のデフォルト値"""
        result = db.get_setting("nonexistent", "default")

        assert result == "default"

    def test_update_setting(self, db: Database) -> None:
        """設定の更新（UPSERT）"""
        db.set_setting("test.key", "value1", "test")
        db.set_setting("test.key", "value2", "test")

        result = db.get_setting("test.key")

        assert result == "value2"

    def test_get_all_settings(self, db: Database) -> None:
        """全設定の取得"""
        db.set_setting("key1", "value1", "cat1")
        db.set_setting("key2", "value2", "cat2")

        settings = db.get_all_settings()

        assert settings["key1"] == "value1"
        assert settings["key2"] == "value2"

    def test_get_settings_by_category(self, db: Database) -> None:
        """カテゴリ別設定の取得"""
        db.set_setting("server.host", "localhost", "server")
        db.set_setting("server.port", 8000, "server")
        db.set_setting("other.key", "value", "other")

        settings = db.get_settings_by_category("server")

        assert len(settings) == 2
        assert settings["server.host"] == "localhost"
        assert settings["server.port"] == 8000


class TestApplicationOperations:
    """アプリケーション操作のテスト"""

    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        """テスト用データベース"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()
        return db

    def test_create_application(self, db: Database) -> None:
        """アプリケーション作成"""
        app = Application(
            id="test-app",
            name="Test App",
            description="Test description",
            github_owner="owner",
            github_repo="repo",
            service_name="test-service",
            port=8001,
            health_check_path="/health",
            auto_restart=True,
            installed=False,
            sort_order=0,
        )
        db.create_application(app)

        result = db.get_application("test-app")

        assert result is not None
        assert result.id == "test-app"
        assert result.name == "Test App"
        assert result.github_owner == "owner"
        assert result.github_repo == "repo"
        assert result.port == 8001
        assert result.auto_restart is True
        assert result.installed is False

    def test_get_application_not_found(self, db: Database) -> None:
        """存在しないアプリケーション"""
        result = db.get_application("nonexistent")

        assert result is None

    def test_get_all_applications(self, db: Database) -> None:
        """全アプリケーション取得"""
        db.create_application(
            Application(
                id="app1",
                name="App 1",
                github_owner="owner",
                github_repo="repo1",
                service_name="service1",
                port=8001,
                sort_order=1,
            )
        )
        db.create_application(
            Application(
                id="app2",
                name="App 2",
                github_owner="owner",
                github_repo="repo2",
                service_name="service2",
                port=8002,
                sort_order=0,
            )
        )

        applications = db.get_all_applications()

        assert len(applications) == 2
        # sort_orderでソートされる
        assert applications[0].id == "app2"
        assert applications[1].id == "app1"

    def test_update_application(self, db: Database) -> None:
        """アプリケーション更新"""
        app = Application(
            id="test-app",
            name="Test App",
            github_owner="owner",
            github_repo="repo",
            service_name="test-service",
            port=8001,
            installed=False,
        )
        db.create_application(app)

        result = db.get_application("test-app")
        assert result is not None

        result.installed = True
        result.installed_version = "v1.0.0"
        result.installed_at = datetime(2025, 1, 1, 12, 0, 0)
        db.update_application(result)

        updated = db.get_application("test-app")
        assert updated is not None
        assert updated.installed is True
        assert updated.installed_version == "v1.0.0"
        assert updated.installed_at is not None


class TestConnectionContextManager:
    """コネクションコンテキストマネージャーのテスト"""

    def test_connection_commits_on_success(self, tmp_path: Path) -> None:
        """正常時はコミットされる"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()

        with db.connection() as conn:
            conn.execute(
                "INSERT INTO settings (key, value, category) VALUES (?, ?, ?)",
                ("test", '"value"', "test"),
            )

        # 新しいコネクションで確認
        result = db.get_setting("test")
        assert result == "value"

    def test_connection_rollbacks_on_error(self, tmp_path: Path) -> None:
        """エラー時はロールバックされる"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.initialize()

        db.set_setting("test", "original", "test")

        try:
            with db.connection() as conn:
                conn.execute(
                    "UPDATE settings SET value = ? WHERE key = ?",
                    ('"modified"', "test"),
                )
                raise ValueError("Test error")
        except ValueError:
            pass

        # ロールバックされているはず
        result = db.get_setting("test")
        assert result == "original"
