"""pytest fixtures"""

from pathlib import Path

import pytest
import yaml

from app import create_app


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """テスト用設定ディレクトリを作成する。"""
    config_yaml = {
        "server": {"host": "0.0.0.0", "port": 8000, "debug": False},
        "session": {"lifetime_hours": 24},
        "auth": {
            "initial_users": [
                {"username": "admin", "password": "admin", "role": "admin"},
                {"username": "user", "password": "user", "role": "user"},
            ]
        },
        "resource_monitor": {
            "disk_paths": ["/"],
            "warning_thresholds": {
                "cpu_percent": 80,
                "memory_percent": 80,
                "disk_percent": 90,
            },
        },
        "app_install": {"install_dir": "/opt/pol-apps"},
        "logging": {
            "level": "INFO",
            "directory": "logs",
            "console": {"enabled": True},
            "max_size_mb": 10,
            "backup_count": 3,
            "retention_days": 7,
            "archive": {
                "enabled": True,
                "directory": "archive",
                "retention_days": 30,
            },
            "max_folder_size_mb": 500,
        },
    }

    apps_yaml = {
        "applications": [
            {
                "id": "test-app",
                "name": "Test App",
                "description": "Test application",
                "github_owner": "TestOwner",
                "github_repo": "test-repo",
                "service_name": "test-service",
                "port": 8001,
                "health_check_path": "/health",
                "auto_restart": True,
                "scripts": [
                    {
                        "id": "test-script",
                        "name": "Test Script",
                        "description": "A test script",
                        "path": str(tmp_path / "scripts" / "test.bat"),
                        "mode": "sync",
                        "timeout": 30,
                    }
                ],
            }
        ]
    }

    # テスト用スクリプトディレクトリとファイルを作成
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    test_script = scripts_dir / "test.bat"
    test_script.write_text("@echo hello\n", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_yaml, f)

    apps_path = tmp_path / "apps.yaml"
    with open(apps_path, "w", encoding="utf-8") as f:
        yaml.dump(apps_yaml, f)

    return tmp_path


@pytest.fixture
def app(config_dir: Path):
    """テスト用Flaskアプリを生成する。"""
    app = create_app(config_dir=config_dir, skip_env_check=True)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """テスト用クライアントを生成する。"""
    return app.test_client()


def _login(client, username: str, password: str):
    """テスト用ログインヘルパー"""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


@pytest.fixture
def admin_client(app):
    """管理者ログイン済みクライアントを生成する。"""
    client = app.test_client()
    _login(client, "admin", "admin")
    return client


@pytest.fixture
def user_client(app):
    """一般ユーザーログイン済みクライアントを生成する。"""
    client = app.test_client()
    _login(client, "user", "user")
    return client
