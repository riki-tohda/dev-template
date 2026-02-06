"""ConfigLoaderのテスト"""

from pathlib import Path

import pytest
import yaml

from app.services.config_loader import (
    OS_LINUX,
    OS_WINDOWS,
    ConfigLoader,
    ConfigValidationError,
    get_current_os,
    resolve_os_value,
    validate_log_level,
    validate_password,
    validate_port,
    validate_role,
    validate_session_lifetime,
    validate_threshold,
    validate_username,
)
from app.services.models import Application


class TestValidateFunctions:
    """バリデーション関数のテスト"""

    def test_validate_port_valid(self) -> None:
        """有効なポート番号"""
        validate_port(1024)
        validate_port(8000)
        validate_port(65535)

    def test_validate_port_invalid_range(self) -> None:
        """範囲外のポート番号"""
        with pytest.raises(ConfigValidationError):
            validate_port(1023)
        with pytest.raises(ConfigValidationError):
            validate_port(65536)
        with pytest.raises(ConfigValidationError):
            validate_port(0)

    def test_validate_port_invalid_type(self) -> None:
        """不正な型"""
        with pytest.raises(ConfigValidationError):
            validate_port("8000")  # type: ignore

    def test_validate_username_valid(self) -> None:
        """有効なユーザー名"""
        validate_username("abc")
        validate_username("user_123")
        validate_username("Admin")
        validate_username("a" * 32)

    def test_validate_username_too_short(self) -> None:
        """短すぎるユーザー名"""
        with pytest.raises(ConfigValidationError):
            validate_username("ab")

    def test_validate_username_too_long(self) -> None:
        """長すぎるユーザー名"""
        with pytest.raises(ConfigValidationError):
            validate_username("a" * 33)

    def test_validate_username_invalid_chars(self) -> None:
        """不正な文字を含むユーザー名"""
        with pytest.raises(ConfigValidationError):
            validate_username("user-name")
        with pytest.raises(ConfigValidationError):
            validate_username("user name")
        with pytest.raises(ConfigValidationError):
            validate_username("user@name")

    def test_validate_password_valid(self) -> None:
        """有効なパスワード"""
        validate_password("abcd")
        validate_password("a" * 100)

    def test_validate_password_too_short(self) -> None:
        """短すぎるパスワード"""
        with pytest.raises(ConfigValidationError):
            validate_password("abc")

    def test_validate_role_valid(self) -> None:
        """有効な権限"""
        validate_role("admin")
        validate_role("user")

    def test_validate_role_invalid(self) -> None:
        """不正な権限"""
        with pytest.raises(ConfigValidationError):
            validate_role("guest")
        with pytest.raises(ConfigValidationError):
            validate_role("Admin")

    def test_validate_session_lifetime_valid(self) -> None:
        """有効なセッション有効時間"""
        validate_session_lifetime(1)
        validate_session_lifetime(24)
        validate_session_lifetime(168)

    def test_validate_session_lifetime_invalid(self) -> None:
        """無効なセッション有効時間"""
        with pytest.raises(ConfigValidationError):
            validate_session_lifetime(0)
        with pytest.raises(ConfigValidationError):
            validate_session_lifetime(169)

    def test_validate_threshold_valid(self) -> None:
        """有効な閾値"""
        validate_threshold(1, "test")
        validate_threshold(50, "test")
        validate_threshold(100, "test")

    def test_validate_threshold_invalid(self) -> None:
        """無効な閾値"""
        with pytest.raises(ConfigValidationError):
            validate_threshold(0, "test")
        with pytest.raises(ConfigValidationError):
            validate_threshold(101, "test")

    def test_validate_log_level_valid(self) -> None:
        """有効なログレベル"""
        validate_log_level("DEBUG")
        validate_log_level("INFO")
        validate_log_level("WARNING")
        validate_log_level("ERROR")
        validate_log_level("CRITICAL")
        validate_log_level("debug")  # 大文字小文字を区別しない

    def test_validate_log_level_invalid(self) -> None:
        """無効なログレベル"""
        with pytest.raises(ConfigValidationError):
            validate_log_level("TRACE")
        with pytest.raises(ConfigValidationError):
            validate_log_level("FATAL")


class TestOsValueResolution:
    """OS別設定値解決のテスト"""

    def test_get_current_os(self) -> None:
        """現在のOSを取得"""
        os_name = get_current_os()
        assert os_name in (OS_WINDOWS, OS_LINUX)

    def test_resolve_os_value_with_os_dict_windows(self) -> None:
        """Windows用の値を解決"""
        value = {"windows": "C:\\apps", "linux": "/opt/apps"}
        result = resolve_os_value(value, OS_WINDOWS)
        assert result == "C:\\apps"

    def test_resolve_os_value_with_os_dict_linux(self) -> None:
        """Linux用の値を解決"""
        value = {"windows": "C:\\apps", "linux": "/opt/apps"}
        result = resolve_os_value(value, OS_LINUX)
        assert result == "/opt/apps"

    def test_resolve_os_value_with_list(self) -> None:
        """リスト値のOS別解決"""
        value = {"windows": ["C:\\"], "linux": ["/"]}
        result_win = resolve_os_value(value, OS_WINDOWS)
        result_linux = resolve_os_value(value, OS_LINUX)
        assert result_win == ["C:\\"]
        assert result_linux == ["/"]

    def test_resolve_os_value_single_value(self) -> None:
        """単一値はそのまま返す"""
        value = "/opt/apps"
        result = resolve_os_value(value, OS_WINDOWS)
        assert result == "/opt/apps"

    def test_resolve_os_value_non_os_dict(self) -> None:
        """OSキーを含まない辞書はそのまま返す"""
        value = {"key": "value", "other": "data"}
        result = resolve_os_value(value, OS_WINDOWS)
        assert result == {"key": "value", "other": "data"}

    def test_resolve_os_value_fallback_to_other_os(self) -> None:
        """現在のOSのキーがない場合は他のOSの値を使用"""
        value = {"linux": "/opt/apps"}
        result = resolve_os_value(value, OS_WINDOWS)
        assert result == "/opt/apps"

    def test_resolve_os_value_only_windows(self) -> None:
        """Windowsのみ定義されている場合"""
        value = {"windows": "C:\\apps"}
        result_win = resolve_os_value(value, OS_WINDOWS)
        result_linux = resolve_os_value(value, OS_LINUX)
        assert result_win == "C:\\apps"
        assert result_linux == "C:\\apps"  # フォールバック


class TestConfigLoader:
    """ConfigLoaderのテスト"""

    def test_load_config_yaml(self, tmp_path: Path) -> None:
        """config.yaml読み込み"""
        config_yaml = {
            "server": {"host": "127.0.0.1", "port": 9000, "debug": True},
            "session": {"lifetime_hours": 48},
            "auth": {
                "initial_users": [
                    {"username": "admin", "password": "admin123", "role": "admin"}
                ]
            },
            "resource_monitor": {
                "disk_paths": ["/", "/home"],
                "warning_thresholds": {
                    "cpu_percent": 70,
                    "memory_percent": 75,
                    "disk_percent": 85,
                },
            },
            "app_install": {"install_dir": "/var/apps"},
            "logging": {
                "level": "DEBUG",
                "directory": "logs/test",
                "max_size_mb": 5,
                "backup_count": 2,
                "retention_days": 14,
                "console": {"enabled": False},
                "archive": {
                    "enabled": True,
                    "directory": "archive",
                    "retention_days": 60,
                },
                "max_folder_size_mb": 200,
            },
        }

        config_path = tmp_path / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_yaml, f)

        loader = ConfigLoader(tmp_path)
        config = loader.load_config_yaml()

        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000
        assert config.server.debug is True
        assert config.session.lifetime_hours == 48
        assert len(config.initial_users) == 1
        assert config.initial_users[0].username == "admin"
        assert config.resource_monitor.disk_paths == ["/", "/home"]
        assert config.resource_monitor.warning_thresholds.cpu_percent == 70
        assert config.app_install.install_dir == "/var/apps"
        assert config.app_install.github_api_url == "https://api.github.com"
        assert config.logging.level == "DEBUG"
        assert config.logging.directory == "logs/test"
        assert config.logging.console.enabled is False
        assert config.logging.archive.retention_days == 60
        assert config.logging.max_folder_size_mb == 200

    def test_load_config_yaml_with_github_enterprise_url(self, tmp_path: Path) -> None:
        """GitHub Enterprise API URL を含む config.yaml 読み込み"""
        config_yaml = {
            "server": {"host": "0.0.0.0", "port": 8000},
            "auth": {
                "initial_users": [
                    {"username": "admin", "password": "admin", "role": "admin"}
                ]
            },
            "app_install": {
                "github_api_url": "https://github.example.co.jp/api/v3",
                "install_dir": "/opt/apps",
            },
        }

        config_path = tmp_path / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_yaml, f)

        loader = ConfigLoader(tmp_path)
        config = loader.load_config_yaml()

        assert (
            config.app_install.github_api_url == "https://github.example.co.jp/api/v3"
        )
        assert config.app_install.install_dir == "/opt/apps"

    def test_load_config_yaml_with_os_specific_values(self, tmp_path: Path) -> None:
        """OS別設定値を含むconfig.yaml読み込み"""
        config_yaml = {
            "server": {"host": "0.0.0.0", "port": 8000},
            "auth": {
                "initial_users": [
                    {"username": "admin", "password": "admin", "role": "admin"}
                ]
            },
            "resource_monitor": {
                "disk_paths": {"windows": ["C:\\", "D:\\"], "linux": ["/", "/home"]},
            },
            "app_install": {
                "install_dir": {"windows": "C:\\my-apps", "linux": "/opt/my-apps"}
            },
        }

        config_path = tmp_path / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_yaml, f)

        loader = ConfigLoader(tmp_path)
        config = loader.load_config_yaml()

        current_os = get_current_os()
        if current_os == OS_WINDOWS:
            assert config.resource_monitor.disk_paths == ["C:\\", "D:\\"]
            assert config.app_install.install_dir == "C:\\my-apps"
        else:
            assert config.resource_monitor.disk_paths == ["/", "/home"]
            assert config.app_install.install_dir == "/opt/my-apps"

    def test_load_config_yaml_missing_file(self, tmp_path: Path) -> None:
        """config.yamlが存在しない場合"""
        loader = ConfigLoader(tmp_path)
        config = loader.load_config_yaml()

        # デフォルト値
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.session.lifetime_hours == 24

        # OS別デフォルト値が適用される
        current_os = get_current_os()
        if current_os == OS_WINDOWS:
            assert config.app_install.install_dir == "C:\\pol-apps"
            assert config.resource_monitor.disk_paths == ["C:\\"]
        else:
            assert config.app_install.install_dir == "/opt/pol-apps"
            assert config.resource_monitor.disk_paths == ["/"]

    def test_load_apps_yaml(self, tmp_path: Path) -> None:
        """apps.yaml読み込み"""
        apps_yaml = {
            "applications": [
                {
                    "id": "test-app",
                    "name": "Test App",
                    "description": "Test description",
                    "github_owner": "owner",
                    "github_repo": "repo",
                    "service_name": "test-service",
                    "port": 8001,
                    "health_check_path": "/health",
                    "auto_restart": True,
                }
            ]
        }

        apps_path = tmp_path / "apps.yaml"
        with open(apps_path, "w", encoding="utf-8") as f:
            yaml.dump(apps_yaml, f)

        loader = ConfigLoader(tmp_path)
        applications = loader.load_apps_yaml()

        assert len(applications) == 1
        assert applications[0].id == "test-app"
        assert applications[0].name == "Test App"
        assert applications[0].github_owner == "owner"
        assert applications[0].github_repo == "repo"
        assert applications[0].port == 8001
        assert applications[0].auto_restart is True

    def test_load_apps_yaml_missing_file(self, tmp_path: Path) -> None:
        """apps.yamlが存在しない場合"""
        loader = ConfigLoader(tmp_path)
        applications = loader.load_apps_yaml()

        assert applications == []

    def test_validate_config_valid(self, tmp_path: Path) -> None:
        """有効な設定のバリデーション"""
        loader = ConfigLoader(tmp_path)
        config = loader.get_default_config()
        loader.validate_config(config)

    def test_validate_config_no_initial_users(self, tmp_path: Path) -> None:
        """初期ユーザーなしの設定"""
        loader = ConfigLoader(tmp_path)
        config = loader.get_default_config()
        config.initial_users = []

        with pytest.raises(
            ConfigValidationError, match="初期ユーザーが定義されていません"
        ):
            loader.validate_config(config)

    def test_validate_config_no_admin(self, tmp_path: Path) -> None:
        """admin権限ユーザーなしの設定"""
        from app.services.models import InitialUser

        loader = ConfigLoader(tmp_path)
        config = loader.get_default_config()
        config.initial_users = [
            InitialUser(username="user", password="user", role="user")
        ]

        with pytest.raises(ConfigValidationError, match="admin権限"):
            loader.validate_config(config)

    def test_validate_applications_valid(self, tmp_path: Path) -> None:
        """有効なアプリケーション定義のバリデーション"""
        loader = ConfigLoader(tmp_path)
        applications = [
            Application(
                id="app1",
                name="App 1",
                github_owner="owner",
                github_repo="repo1",
                service_name="service1",
                port=8001,
            ),
            Application(
                id="app2",
                name="App 2",
                github_owner="owner",
                github_repo="repo2",
                service_name="service2",
                port=8002,
            ),
        ]
        loader.validate_applications(applications)

    def test_validate_applications_duplicate_id(self, tmp_path: Path) -> None:
        """ID重複のあるアプリケーション定義"""
        loader = ConfigLoader(tmp_path)
        applications = [
            Application(
                id="app1",
                name="App 1",
                github_owner="owner",
                github_repo="repo1",
                service_name="service1",
                port=8001,
            ),
            Application(
                id="app1",
                name="App 1 Duplicate",
                github_owner="owner",
                github_repo="repo2",
                service_name="service2",
                port=8002,
            ),
        ]

        with pytest.raises(ConfigValidationError, match="IDが重複"):
            loader.validate_applications(applications)

    def test_validate_applications_duplicate_port(self, tmp_path: Path) -> None:
        """ポート番号重複のあるアプリケーション定義"""
        loader = ConfigLoader(tmp_path)
        applications = [
            Application(
                id="app1",
                name="App 1",
                github_owner="owner",
                github_repo="repo1",
                service_name="service1",
                port=8001,
            ),
            Application(
                id="app2",
                name="App 2",
                github_owner="owner",
                github_repo="repo2",
                service_name="service2",
                port=8001,
            ),
        ]

        with pytest.raises(ConfigValidationError, match="ポート番号が重複"):
            loader.validate_applications(applications)

    def test_load_environment_missing_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """環境変数POL_GITHUB_TOKEN未設定時は警告を出しNoneを返す"""
        monkeypatch.delenv("POL_GITHUB_TOKEN", raising=False)

        loader = ConfigLoader(tmp_path)
        env_vars = loader.load_environment()

        assert env_vars["POL_GITHUB_TOKEN"] is None

    def test_load_environment_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """環境変数の読み込み"""
        monkeypatch.setenv("POL_GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("POL_SECRET_KEY", "test_secret")

        loader = ConfigLoader(tmp_path)
        env_vars = loader.load_environment()

        assert env_vars["POL_GITHUB_TOKEN"] == "test_token"
        assert env_vars["POL_SECRET_KEY"] == "test_secret"

    def test_get_default_config(self, tmp_path: Path) -> None:
        """デフォルト設定の取得"""
        loader = ConfigLoader(tmp_path)
        config = loader.get_default_config()

        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert len(config.initial_users) == 1
        assert config.initial_users[0].username == "admin"
        assert config.initial_users[0].role == "admin"

        # OS別デフォルト値
        current_os = get_current_os()
        if current_os == OS_WINDOWS:
            assert config.app_install.install_dir == "C:\\pol-apps"
            assert config.resource_monitor.disk_paths == ["C:\\"]
        else:
            assert config.app_install.install_dir == "/opt/pol-apps"
            assert config.resource_monitor.disk_paths == ["/"]
