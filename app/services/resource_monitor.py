"""リソース監視サービス

端末のリソース使用状況（CPU、メモリ、ディスク）を監視する。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import psutil

from app.services.log_manager import get_logger

logger = get_logger("resource")


@dataclass
class CpuInfo:
    """CPU情報"""

    percent: float
    count: int
    count_logical: int

    @property
    def is_warning(self) -> bool:
        """警告状態かどうか（外部で閾値設定が必要）"""
        return False  # 閾値チェックは ResourceMonitor で行う


@dataclass
class MemoryInfo:
    """メモリ情報"""

    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent: float

    @property
    def total_gb(self) -> float:
        """合計（GB）"""
        return round(self.total_bytes / (1024**3), 2)

    @property
    def available_gb(self) -> float:
        """利用可能（GB）"""
        return round(self.available_bytes / (1024**3), 2)

    @property
    def used_gb(self) -> float:
        """使用中（GB）"""
        return round(self.used_bytes / (1024**3), 2)


@dataclass
class DiskInfo:
    """ディスク情報"""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float

    @property
    def total_gb(self) -> float:
        """合計（GB）"""
        return round(self.total_bytes / (1024**3), 2)

    @property
    def used_gb(self) -> float:
        """使用中（GB）"""
        return round(self.used_bytes / (1024**3), 2)

    @property
    def free_gb(self) -> float:
        """空き（GB）"""
        return round(self.free_bytes / (1024**3), 2)


@dataclass
class SystemInfo:
    """システム情報"""

    boot_time: datetime
    uptime: timedelta

    @property
    def uptime_str(self) -> str:
        """稼働時間の文字列表現"""
        days = self.uptime.days
        hours, remainder = divmod(self.uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}日")
        if hours > 0:
            parts.append(f"{hours}時間")
        parts.append(f"{minutes}分")

        return " ".join(parts)


@dataclass
class ResourceStatus:
    """リソース状態の総合情報"""

    cpu: CpuInfo
    memory: MemoryInfo
    disks: list[DiskInfo]
    system: SystemInfo
    timestamp: datetime

    # 警告状態
    cpu_warning: bool = False
    memory_warning: bool = False
    disk_warnings: dict[str, bool] | None = None

    def to_dict(self) -> dict:
        """辞書形式に変換する"""
        return {
            "cpu": {
                "percent": self.cpu.percent,
                "count": self.cpu.count,
                "count_logical": self.cpu.count_logical,
                "warning": self.cpu_warning,
            },
            "memory": {
                "total_gb": self.memory.total_gb,
                "used_gb": self.memory.used_gb,
                "available_gb": self.memory.available_gb,
                "percent": self.memory.percent,
                "warning": self.memory_warning,
            },
            "disks": [
                {
                    "path": disk.path,
                    "total_gb": disk.total_gb,
                    "used_gb": disk.used_gb,
                    "free_gb": disk.free_gb,
                    "percent": disk.percent,
                    "warning": (self.disk_warnings or {}).get(disk.path, False),
                }
                for disk in self.disks
            ],
            "system": {
                "boot_time": self.system.boot_time.isoformat(),
                "uptime": self.system.uptime_str,
            },
            "timestamp": self.timestamp.isoformat(),
        }


class ResourceMonitor:
    """リソース監視クラス"""

    def __init__(
        self,
        disk_paths: list[str] | None = None,
        cpu_warning_threshold: float = 80.0,
        memory_warning_threshold: float = 80.0,
        disk_warning_threshold: float = 90.0,
    ):
        """初期化

        Args:
            disk_paths: 監視対象のディスクパス
            cpu_warning_threshold: CPU使用率の警告閾値（%）
            memory_warning_threshold: メモリ使用率の警告閾値（%）
            disk_warning_threshold: ディスク使用率の警告閾値（%）
        """
        self.disk_paths = disk_paths or ["/"]
        self.cpu_warning_threshold = cpu_warning_threshold
        self.memory_warning_threshold = memory_warning_threshold
        self.disk_warning_threshold = disk_warning_threshold

    def get_cpu_info(self) -> CpuInfo:
        """CPU情報を取得する"""
        return CpuInfo(
            percent=psutil.cpu_percent(interval=0.1),
            count=psutil.cpu_count(logical=False) or 1,
            count_logical=psutil.cpu_count(logical=True) or 1,
        )

    def get_memory_info(self) -> MemoryInfo:
        """メモリ情報を取得する"""
        mem = psutil.virtual_memory()
        return MemoryInfo(
            total_bytes=mem.total,
            available_bytes=mem.available,
            used_bytes=mem.used,
            percent=mem.percent,
        )

    def get_disk_info(self, path: str) -> DiskInfo | None:
        """指定パスのディスク情報を取得する

        Args:
            path: ディスクパス

        Returns:
            ディスク情報。取得できない場合は None。
        """
        try:
            usage = psutil.disk_usage(path)
            return DiskInfo(
                path=path,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=usage.percent,
            )
        except (OSError, PermissionError) as e:
            logger.warning("ディスク情報の取得に失敗しました path=%s error=%s", path, e)
            return None

    def get_all_disk_info(self) -> list[DiskInfo]:
        """全監視対象ディスクの情報を取得する"""
        disks = []
        for path in self.disk_paths:
            disk_info = self.get_disk_info(path)
            if disk_info is not None:
                disks.append(disk_info)
        return disks

    def get_system_info(self) -> SystemInfo:
        """システム情報を取得する"""
        boot_timestamp = psutil.boot_time()
        boot_time = datetime.fromtimestamp(boot_timestamp)
        uptime = datetime.now() - boot_time

        return SystemInfo(
            boot_time=boot_time,
            uptime=uptime,
        )

    def get_status(self) -> ResourceStatus:
        """リソース状態を取得する

        Returns:
            現在のリソース状態
        """
        cpu = self.get_cpu_info()
        memory = self.get_memory_info()
        disks = self.get_all_disk_info()
        system = self.get_system_info()

        # 警告状態のチェック
        cpu_warning = cpu.percent >= self.cpu_warning_threshold
        memory_warning = memory.percent >= self.memory_warning_threshold
        disk_warnings = {
            disk.path: disk.percent >= self.disk_warning_threshold for disk in disks
        }

        status = ResourceStatus(
            cpu=cpu,
            memory=memory,
            disks=disks,
            system=system,
            timestamp=datetime.now(),
            cpu_warning=cpu_warning,
            memory_warning=memory_warning,
            disk_warnings=disk_warnings,
        )

        # 警告状態のログ出力
        self._log_warnings(status)

        return status

    def _log_warnings(self, status: ResourceStatus) -> None:
        """警告状態をログに出力する"""
        if status.cpu_warning:
            logger.warning(
                "CPU使用率が閾値を超えました usage=%.1f%% threshold=%.1f%%",
                status.cpu.percent,
                self.cpu_warning_threshold,
            )

        if status.memory_warning:
            logger.warning(
                "メモリ使用率が閾値を超えました usage=%.1f%% threshold=%.1f%%",
                status.memory.percent,
                self.memory_warning_threshold,
            )

        for disk in status.disks:
            if (status.disk_warnings or {}).get(disk.path, False):
                logger.warning(
                    "ディスク使用率が閾値を超えました path=%s usage=%.1f%% threshold=%.1f%%",
                    disk.path,
                    disk.percent,
                    self.disk_warning_threshold,
                )


def create_monitor_from_config(config: dict) -> ResourceMonitor:
    """設定からResourceMonitorを生成する

    Args:
        config: Flask app.config

    Returns:
        ResourceMonitor インスタンス
    """
    return ResourceMonitor(
        disk_paths=config.get("DISK_PATHS", ["/"]),
        cpu_warning_threshold=config.get("CPU_WARNING_THRESHOLD", 80),
        memory_warning_threshold=config.get("MEMORY_WARNING_THRESHOLD", 80),
        disk_warning_threshold=config.get("DISK_WARNING_THRESHOLD", 90),
    )
