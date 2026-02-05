"""アプリケーション管理サービス

管理対象アプリケーションのライフサイクル（起動/停止/再起動/状態確認）を管理する。
"""

import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from app.services.log_manager import get_logger

logger = get_logger("resource")


class AppStatus(str, Enum):
    """アプリケーション状態"""

    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"


@dataclass
class AppConfig:
    """アプリケーション設定"""

    id: str
    name: str
    description: str
    github_owner: str
    github_repo: str
    service_name: str
    port: int
    health_check_path: str
    auto_restart: bool

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """辞書からAppConfigを生成する"""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            github_owner=data.get("github_owner", ""),
            github_repo=data.get("github_repo", ""),
            service_name=data["service_name"],
            port=data["port"],
            health_check_path=data.get("health_check_path", "/health"),
            auto_restart=data.get("auto_restart", True),
        )


@dataclass
class AppState:
    """アプリケーション状態"""

    app_id: str
    status: AppStatus
    service_active: bool
    health_check_ok: bool | None
    error_message: str | None = None

    def to_dict(self) -> dict:
        """辞書形式に変換する"""
        return {
            "app_id": self.app_id,
            "status": self.status.value,
            "service_active": self.service_active,
            "health_check_ok": self.health_check_ok,
            "error_message": self.error_message,
        }


OperationType = Literal["start", "stop", "restart"]


@dataclass
class OperationResult:
    """操作結果"""

    success: bool
    operation: OperationType
    app_id: str
    message: str

    def to_dict(self) -> dict:
        """辞書形式に変換する"""
        return {
            "success": self.success,
            "operation": self.operation,
            "app_id": self.app_id,
            "message": self.message,
        }


class AppManager:
    """アプリケーション管理クラス"""

    def __init__(
        self,
        apps: list[AppConfig],
        health_check_timeout: float = 5.0,
        use_systemctl: bool = True,
    ):
        """初期化

        Args:
            apps: 管理対象アプリケーションのリスト
            health_check_timeout: ヘルスチェックのタイムアウト（秒）
            use_systemctl: systemctlを使用するか（Falseの場合はモック動作）
        """
        self.apps = {app.id: app for app in apps}
        self.health_check_timeout = health_check_timeout
        self.use_systemctl = use_systemctl

    def get_app(self, app_id: str) -> AppConfig | None:
        """アプリケーション設定を取得する"""
        return self.apps.get(app_id)

    def get_all_apps(self) -> list[AppConfig]:
        """全アプリケーション設定を取得する"""
        return list(self.apps.values())

    def get_status(self, app_id: str) -> AppState:
        """アプリケーションの状態を取得する

        Args:
            app_id: アプリケーションID

        Returns:
            アプリケーション状態
        """
        app = self.get_app(app_id)
        if app is None:
            return AppState(
                app_id=app_id,
                status=AppStatus.UNKNOWN,
                service_active=False,
                health_check_ok=None,
                error_message=f"アプリケーションが見つかりません: {app_id}",
            )

        # サービス状態を確認
        service_active = self._check_service_active(app.service_name)

        # ヘルスチェック
        health_check_ok = None
        if service_active:
            health_check_ok = self._check_health(app)

        # 総合状態を判定
        status = self._determine_status(service_active, health_check_ok)

        return AppState(
            app_id=app_id,
            status=status,
            service_active=service_active,
            health_check_ok=health_check_ok,
        )

    def get_all_status(self) -> list[AppState]:
        """全アプリケーションの状態を取得する"""
        return [self.get_status(app_id) for app_id in self.apps]

    def start(self, app_id: str) -> OperationResult:
        """アプリケーションを起動する

        Args:
            app_id: アプリケーションID

        Returns:
            操作結果
        """
        return self._execute_operation(app_id, "start")

    def stop(self, app_id: str) -> OperationResult:
        """アプリケーションを停止する

        Args:
            app_id: アプリケーションID

        Returns:
            操作結果
        """
        return self._execute_operation(app_id, "stop")

    def restart(self, app_id: str) -> OperationResult:
        """アプリケーションを再起動する

        Args:
            app_id: アプリケーションID

        Returns:
            操作結果
        """
        return self._execute_operation(app_id, "restart")

    def _execute_operation(
        self, app_id: str, operation: OperationType
    ) -> OperationResult:
        """操作を実行する"""
        app = self.get_app(app_id)
        if app is None:
            return OperationResult(
                success=False,
                operation=operation,
                app_id=app_id,
                message=f"アプリケーションが見つかりません: {app_id}",
            )

        try:
            if self.use_systemctl:
                self._run_systemctl(operation, app.service_name)
            else:
                # モック動作（テスト用）
                logger.info(
                    "モック操作を実行しました operation=%s service=%s",
                    operation,
                    app.service_name,
                )

            logger.info(
                "アプリケーション操作を実行しました operation=%s app=%s service=%s",
                operation,
                app_id,
                app.service_name,
            )

            return OperationResult(
                success=True,
                operation=operation,
                app_id=app_id,
                message=f"{operation}が完了しました",
            )

        except subprocess.CalledProcessError as e:
            error_msg = f"systemctl {operation} に失敗しました: {e}"
            logger.error(
                "アプリケーション操作に失敗しました operation=%s app=%s error=%s",
                operation,
                app_id,
                e,
            )
            return OperationResult(
                success=False,
                operation=operation,
                app_id=app_id,
                message=error_msg,
            )

        except Exception as e:
            error_msg = f"予期しないエラー: {e}"
            logger.error(
                "アプリケーション操作中に予期しないエラーが発生しました operation=%s app=%s error=%s",
                operation,
                app_id,
                e,
            )
            return OperationResult(
                success=False,
                operation=operation,
                app_id=app_id,
                message=error_msg,
            )

    def _check_service_active(self, service_name: str) -> bool:
        """systemdサービスがアクティブかどうかを確認する"""
        if not self.use_systemctl:
            return False

        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_health(self, app: AppConfig) -> bool:
        """ヘルスチェックを実行する"""
        url = f"http://localhost:{app.port}{app.health_check_path}"

        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(
                request, timeout=self.health_check_timeout
            ) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError):
            return False

    def _determine_status(
        self, service_active: bool, health_check_ok: bool | None
    ) -> AppStatus:
        """総合状態を判定する"""
        if not service_active:
            return AppStatus.STOPPED

        if health_check_ok is None:
            return AppStatus.RUNNING

        if health_check_ok:
            return AppStatus.RUNNING
        else:
            return AppStatus.ERROR

    def _run_systemctl(self, operation: OperationType, service_name: str) -> None:
        """systemctlコマンドを実行する"""
        subprocess.run(
            ["systemctl", operation, service_name],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


def create_manager_from_config(
    apps_config: list[dict],
    use_systemctl: bool = True,
) -> AppManager:
    """設定からAppManagerを生成する

    Args:
        apps_config: アプリケーション設定のリスト
        use_systemctl: systemctlを使用するか

    Returns:
        AppManager インスタンス
    """
    apps = [AppConfig.from_dict(app) for app in apps_config]
    return AppManager(apps=apps, use_systemctl=use_systemctl)
