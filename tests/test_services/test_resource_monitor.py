"""resource_monitor のテスト"""

from datetime import datetime, timedelta

import pytest

from app.services.resource_monitor import (
    CpuInfo,
    DiskInfo,
    MemoryInfo,
    ResourceMonitor,
    ResourceStatus,
    SystemInfo,
    create_monitor_from_config,
)


class TestCpuInfo:
    """CpuInfo のテスト"""

    def test_create(self):
        """CpuInfoが生成できる"""
        cpu = CpuInfo(percent=50.0, count=4, count_logical=8)

        assert cpu.percent == 50.0
        assert cpu.count == 4
        assert cpu.count_logical == 8


class TestMemoryInfo:
    """MemoryInfo のテスト"""

    def test_create(self):
        """MemoryInfoが生成できる"""
        mem = MemoryInfo(
            total_bytes=8 * 1024**3,
            available_bytes=4 * 1024**3,
            used_bytes=4 * 1024**3,
            percent=50.0,
        )

        assert mem.total_gb == 8.0
        assert mem.available_gb == 4.0
        assert mem.used_gb == 4.0
        assert mem.percent == 50.0


class TestDiskInfo:
    """DiskInfo のテスト"""

    def test_create(self):
        """DiskInfoが生成できる"""
        disk = DiskInfo(
            path="/",
            total_bytes=100 * 1024**3,
            used_bytes=60 * 1024**3,
            free_bytes=40 * 1024**3,
            percent=60.0,
        )

        assert disk.path == "/"
        assert disk.total_gb == 100.0
        assert disk.used_gb == 60.0
        assert disk.free_gb == 40.0
        assert disk.percent == 60.0


class TestSystemInfo:
    """SystemInfo のテスト"""

    def test_uptime_str_hours(self):
        """稼働時間が時間単位で表示される"""
        sys_info = SystemInfo(
            boot_time=datetime.now() - timedelta(hours=5, minutes=30),
            uptime=timedelta(hours=5, minutes=30),
        )

        assert "5時間" in sys_info.uptime_str
        assert "30分" in sys_info.uptime_str

    def test_uptime_str_days(self):
        """稼働時間が日単位で表示される"""
        sys_info = SystemInfo(
            boot_time=datetime.now() - timedelta(days=3, hours=2),
            uptime=timedelta(days=3, hours=2),
        )

        assert "3日" in sys_info.uptime_str
        assert "2時間" in sys_info.uptime_str


class TestResourceStatus:
    """ResourceStatus のテスト"""

    @pytest.fixture
    def sample_status(self) -> ResourceStatus:
        """サンプルのResourceStatus"""
        return ResourceStatus(
            cpu=CpuInfo(percent=50.0, count=4, count_logical=8),
            memory=MemoryInfo(
                total_bytes=8 * 1024**3,
                available_bytes=4 * 1024**3,
                used_bytes=4 * 1024**3,
                percent=50.0,
            ),
            disks=[
                DiskInfo(
                    path="/",
                    total_bytes=100 * 1024**3,
                    used_bytes=60 * 1024**3,
                    free_bytes=40 * 1024**3,
                    percent=60.0,
                )
            ],
            system=SystemInfo(
                boot_time=datetime(2025, 1, 20, 10, 0, 0),
                uptime=timedelta(hours=5),
            ),
            timestamp=datetime(2025, 1, 20, 15, 0, 0),
            cpu_warning=False,
            memory_warning=False,
            disk_warnings={"/": False},
        )

    def test_to_dict(self, sample_status: ResourceStatus):
        """to_dictで辞書変換できる"""
        result = sample_status.to_dict()

        assert result["cpu"]["percent"] == 50.0
        assert result["cpu"]["warning"] is False
        assert result["memory"]["total_gb"] == 8.0
        assert result["memory"]["warning"] is False
        assert len(result["disks"]) == 1
        assert result["disks"][0]["path"] == "/"
        assert result["disks"][0]["warning"] is False
        assert "uptime" in result["system"]
        assert "timestamp" in result


class TestResourceMonitor:
    """ResourceMonitor のテスト"""

    def test_init_default(self):
        """デフォルト設定で初期化できる"""
        monitor = ResourceMonitor()

        assert monitor.disk_paths == ["/"]
        assert monitor.cpu_warning_threshold == 80.0
        assert monitor.memory_warning_threshold == 80.0
        assert monitor.disk_warning_threshold == 90.0

    def test_init_custom(self):
        """カスタム設定で初期化できる"""
        monitor = ResourceMonitor(
            disk_paths=["/", "/home"],
            cpu_warning_threshold=70.0,
            memory_warning_threshold=75.0,
            disk_warning_threshold=85.0,
        )

        assert monitor.disk_paths == ["/", "/home"]
        assert monitor.cpu_warning_threshold == 70.0
        assert monitor.memory_warning_threshold == 75.0
        assert monitor.disk_warning_threshold == 85.0

    def test_get_cpu_info(self):
        """CPU情報を取得できる"""
        monitor = ResourceMonitor()
        cpu = monitor.get_cpu_info()

        assert isinstance(cpu, CpuInfo)
        assert 0 <= cpu.percent <= 100
        assert cpu.count >= 1
        assert cpu.count_logical >= 1

    def test_get_memory_info(self):
        """メモリ情報を取得できる"""
        monitor = ResourceMonitor()
        mem = monitor.get_memory_info()

        assert isinstance(mem, MemoryInfo)
        assert mem.total_bytes > 0
        assert 0 <= mem.percent <= 100

    def test_get_disk_info(self):
        """ディスク情報を取得できる"""
        monitor = ResourceMonitor()
        # Windowsでは "C:/" または "/" を使用
        import sys

        path = "C:/" if sys.platform == "win32" else "/"
        disk = monitor.get_disk_info(path)

        assert disk is not None
        assert isinstance(disk, DiskInfo)
        assert disk.total_bytes > 0
        assert 0 <= disk.percent <= 100

    def test_get_disk_info_invalid_path(self):
        """存在しないパスではNoneを返す"""
        monitor = ResourceMonitor()
        disk = monitor.get_disk_info("/nonexistent/path/12345")

        assert disk is None

    def test_get_system_info(self):
        """システム情報を取得できる"""
        monitor = ResourceMonitor()
        sys_info = monitor.get_system_info()

        assert isinstance(sys_info, SystemInfo)
        assert sys_info.boot_time < datetime.now()
        assert sys_info.uptime.total_seconds() > 0

    def test_get_status(self):
        """リソース状態を取得できる"""
        import sys

        disk_path = "C:/" if sys.platform == "win32" else "/"
        monitor = ResourceMonitor(disk_paths=[disk_path])
        status = monitor.get_status()

        assert isinstance(status, ResourceStatus)
        assert status.cpu is not None
        assert status.memory is not None
        assert len(status.disks) >= 1
        assert status.system is not None
        assert status.timestamp is not None

    def test_warning_detection(self):
        """警告状態が検出される"""
        import sys

        disk_path = "C:/" if sys.platform == "win32" else "/"
        # 非常に低い閾値を設定して警告を発生させる
        monitor = ResourceMonitor(
            disk_paths=[disk_path],
            cpu_warning_threshold=0.0,  # 必ず超える
            memory_warning_threshold=0.0,  # 必ず超える
            disk_warning_threshold=0.0,  # 必ず超える
        )
        status = monitor.get_status()

        assert status.cpu_warning is True
        assert status.memory_warning is True
        assert all(status.disk_warnings.values())


class TestCreateMonitorFromConfig:
    """create_monitor_from_config のテスト"""

    def test_create_from_config(self):
        """設定からモニターを生成できる"""
        config = {
            "DISK_PATHS": ["/", "/data"],
            "CPU_WARNING_THRESHOLD": 75,
            "MEMORY_WARNING_THRESHOLD": 70,
            "DISK_WARNING_THRESHOLD": 85,
        }
        monitor = create_monitor_from_config(config)

        assert monitor.disk_paths == ["/", "/data"]
        assert monitor.cpu_warning_threshold == 75
        assert monitor.memory_warning_threshold == 70
        assert monitor.disk_warning_threshold == 85

    def test_create_from_empty_config(self):
        """空の設定からデフォルト値で生成できる"""
        monitor = create_monitor_from_config({})

        assert monitor.disk_paths == ["/"]
        assert monitor.cpu_warning_threshold == 80
        assert monitor.memory_warning_threshold == 80
        assert monitor.disk_warning_threshold == 90
