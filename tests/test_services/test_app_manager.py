"""app_manager のテスト"""

import pytest

from app.services.app_manager import (
    AppConfig,
    AppManager,
    AppState,
    AppStatus,
    OperationResult,
    create_manager_from_config,
)


class TestAppConfig:
    """AppConfig のテスト"""

    def test_from_dict(self):
        """辞書からAppConfigを生成できる"""
        data = {
            "id": "test-app",
            "name": "Test App",
            "description": "Test description",
            "github_owner": "TestOwner",
            "github_repo": "test-repo",
            "service_name": "test-service",
            "port": 8001,
            "health_check_path": "/health",
            "auto_restart": True,
        }
        config = AppConfig.from_dict(data)

        assert config.id == "test-app"
        assert config.name == "Test App"
        assert config.description == "Test description"
        assert config.github_owner == "TestOwner"
        assert config.github_repo == "test-repo"
        assert config.service_name == "test-service"
        assert config.port == 8001
        assert config.health_check_path == "/health"
        assert config.auto_restart is True

    def test_from_dict_with_defaults(self):
        """デフォルト値が適用される"""
        data = {
            "id": "test-app",
            "name": "Test App",
            "service_name": "test-service",
            "port": 8001,
        }
        config = AppConfig.from_dict(data)

        assert config.description == ""
        assert config.health_check_path == "/health"
        assert config.auto_restart is True


class TestAppState:
    """AppState のテスト"""

    def test_to_dict(self):
        """辞書変換できる"""
        state = AppState(
            app_id="test-app",
            status=AppStatus.RUNNING,
            service_active=True,
            health_check_ok=True,
        )
        result = state.to_dict()

        assert result["app_id"] == "test-app"
        assert result["status"] == "running"
        assert result["service_active"] is True
        assert result["health_check_ok"] is True

    def test_to_dict_with_error(self):
        """エラーメッセージ付きで辞書変換できる"""
        state = AppState(
            app_id="test-app",
            status=AppStatus.ERROR,
            service_active=True,
            health_check_ok=False,
            error_message="Connection failed",
        )
        result = state.to_dict()

        assert result["status"] == "error"
        assert result["error_message"] == "Connection failed"


class TestOperationResult:
    """OperationResult のテスト"""

    def test_to_dict(self):
        """辞書変換できる"""
        result = OperationResult(
            success=True,
            operation="start",
            app_id="test-app",
            message="Started successfully",
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["operation"] == "start"
        assert data["app_id"] == "test-app"
        assert data["message"] == "Started successfully"


class TestAppManager:
    """AppManager のテスト"""

    @pytest.fixture
    def sample_apps(self) -> list[AppConfig]:
        """サンプルアプリ設定"""
        return [
            AppConfig(
                id="app1",
                name="App 1",
                description="First app",
                github_owner="Owner",
                github_repo="repo1",
                service_name="service1",
                port=8001,
                health_check_path="/health",
                auto_restart=True,
            ),
            AppConfig(
                id="app2",
                name="App 2",
                description="Second app",
                github_owner="Owner",
                github_repo="repo2",
                service_name="service2",
                port=8002,
                health_check_path="/health",
                auto_restart=False,
            ),
        ]

    @pytest.fixture
    def manager(self, sample_apps: list[AppConfig]) -> AppManager:
        """テスト用マネージャー（systemctl無効）"""
        return AppManager(apps=sample_apps, use_systemctl=False)

    def test_init(self, manager: AppManager):
        """初期化できる"""
        assert len(manager.apps) == 2
        assert "app1" in manager.apps
        assert "app2" in manager.apps

    def test_get_app(self, manager: AppManager):
        """アプリ設定を取得できる"""
        app = manager.get_app("app1")
        assert app is not None
        assert app.id == "app1"
        assert app.name == "App 1"

    def test_get_app_not_found(self, manager: AppManager):
        """存在しないアプリはNoneを返す"""
        app = manager.get_app("nonexistent")
        assert app is None

    def test_get_all_apps(self, manager: AppManager):
        """全アプリ設定を取得できる"""
        apps = manager.get_all_apps()
        assert len(apps) == 2

    def test_get_status_unknown_app(self, manager: AppManager):
        """存在しないアプリの状態はUNKNOWN"""
        state = manager.get_status("nonexistent")
        assert state.status == AppStatus.UNKNOWN
        assert state.error_message is not None

    def test_get_status_stopped(self, manager: AppManager):
        """systemctl無効時は停止状態"""
        state = manager.get_status("app1")
        assert state.status == AppStatus.STOPPED
        assert state.service_active is False

    def test_get_all_status(self, manager: AppManager):
        """全アプリの状態を取得できる"""
        states = manager.get_all_status()
        assert len(states) == 2

    def test_start_mock(self, manager: AppManager):
        """起動操作（モック）が成功する"""
        result = manager.start("app1")
        assert result.success is True
        assert result.operation == "start"
        assert result.app_id == "app1"

    def test_stop_mock(self, manager: AppManager):
        """停止操作（モック）が成功する"""
        result = manager.stop("app1")
        assert result.success is True
        assert result.operation == "stop"

    def test_restart_mock(self, manager: AppManager):
        """再起動操作（モック）が成功する"""
        result = manager.restart("app1")
        assert result.success is True
        assert result.operation == "restart"

    def test_operation_unknown_app(self, manager: AppManager):
        """存在しないアプリへの操作は失敗する"""
        result = manager.start("nonexistent")
        assert result.success is False
        assert "見つかりません" in result.message

    def test_determine_status_stopped(self, manager: AppManager):
        """停止状態の判定"""
        status = manager._determine_status(
            service_active=False, health_check_ok=None
        )
        assert status == AppStatus.STOPPED

    def test_determine_status_running(self, manager: AppManager):
        """実行中状態の判定"""
        status = manager._determine_status(service_active=True, health_check_ok=True)
        assert status == AppStatus.RUNNING

    def test_determine_status_error(self, manager: AppManager):
        """エラー状態の判定"""
        status = manager._determine_status(service_active=True, health_check_ok=False)
        assert status == AppStatus.ERROR


class TestCreateManagerFromConfig:
    """create_manager_from_config のテスト"""

    def test_create_from_config(self):
        """設定からマネージャーを生成できる"""
        apps_config = [
            {
                "id": "test-app",
                "name": "Test App",
                "service_name": "test-service",
                "port": 8001,
            }
        ]
        manager = create_manager_from_config(apps_config, use_systemctl=False)

        assert len(manager.apps) == 1
        assert "test-app" in manager.apps
        assert manager.use_systemctl is False

    def test_create_multiple_apps(self):
        """複数アプリの設定からマネージャーを生成できる"""
        apps_config = [
            {
                "id": "app1",
                "name": "App 1",
                "service_name": "service1",
                "port": 8001,
            },
            {
                "id": "app2",
                "name": "App 2",
                "service_name": "service2",
                "port": 8002,
            },
        ]
        manager = create_manager_from_config(apps_config, use_systemctl=False)

        assert len(manager.apps) == 2
