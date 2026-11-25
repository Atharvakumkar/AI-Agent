import platform
import socket
import time
from datetime import datetime
from app.time_utils import from_timestamp_ist, now_ist
import psutil

from app.monitoring.linux_adapter import LinuxAdapter
from app.monitoring.schemas import (
    CpuMetrics,
    DiskMetrics,
    DiskPartitionMetrics,
    MemoryMetrics,
    ProcessDetail,
    ProcessOverview,
    ProcessSummary,
    SystemInfo,
    SystemSnapshot,
)
from app.monitoring.windows_adapter import WindowsAdapter

BYTES_PER_GB = 1024 ** 3
BYTES_PER_MB = 1024 ** 2


def _bytes_to_gb(value: int) -> float:
    return round(value / BYTES_PER_GB, 2)


def _bytes_to_mb(value: int) -> float:
    return round(value / BYTES_PER_MB, 2)


def _format_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


class SystemMonitor:
    """Cross-platform read-only system metrics collector."""

    def __init__(self) -> None:
        current_os = platform.system().lower()
        if current_os == "windows":
            self.adapter = WindowsAdapter()
        else:
            self.adapter = LinuxAdapter()

        # Prime psutil CPU counters so subsequent non-blocking calls return real values
        psutil.cpu_percent(interval=None, percpu=True)
        self._prime_process_cpu()

    def _prime_process_cpu(self) -> None:
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def get_system_information(self) -> SystemInfo:
        boot_ts = psutil.boot_time()
        boot_dt = from_timestamp_ist(boot_ts)
        uptime_seconds = max(0, int(time.time() - boot_ts))

        return SystemInfo(
            hostname=socket.gethostname(),
            os_name=platform.system(),
            os_release=platform.release(),
            os_version=platform.version(),
            architecture=platform.machine(),
            processor=platform.processor() or "Unknown",
            boot_time=boot_dt,
            uptime_seconds=uptime_seconds,
            uptime_human=_format_uptime(uptime_seconds),
        )

    def get_cpu_metrics(self, interval: float | None = None) -> CpuMetrics:
        per_core = psutil.cpu_percent(interval=interval, percpu=True)
        overall = round(sum(per_core) / len(per_core), 1) if per_core else 0.0

        freq_mhz: float | None = None
        try:
            freq = psutil.cpu_freq()
            if freq and freq.current:
                freq_mhz = round(freq.current, 1)
        except Exception:
            freq_mhz = None

        return CpuMetrics(
            usage_percent=overall,
            per_core_percent=[round(c, 1) for c in per_core],
            logical_cores=psutil.cpu_count(logical=True) or 1,
            physical_cores=psutil.cpu_count(logical=False),
            frequency_mhz=freq_mhz,
        )

    def get_memory_metrics(self) -> MemoryMetrics:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return MemoryMetrics(
            total_gb=_bytes_to_gb(vm.total),
            used_gb=_bytes_to_gb(vm.used),
            available_gb=_bytes_to_gb(vm.available),
            usage_percent=round(vm.percent, 1),
            swap_total_gb=_bytes_to_gb(swap.total),
            swap_used_gb=_bytes_to_gb(swap.used),
            swap_percent=round(swap.percent, 1),
        )

    def get_disk_metrics(self) -> DiskMetrics:
        primary_path = self.adapter.get_primary_disk_path()
        primary_usage = psutil.disk_usage(primary_path)

        partitions: list[DiskPartitionMetrics] = []
        for part in psutil.disk_partitions(all=False):
            if not self.adapter.should_include_partition(part):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue

            partitions.append(
                DiskPartitionMetrics(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total_gb=_bytes_to_gb(usage.total),
                    used_gb=_bytes_to_gb(usage.used),
                    free_gb=_bytes_to_gb(usage.free),
                    usage_percent=round(usage.percent, 1),
                )
            )

        return DiskMetrics(
            primary_mount=primary_path,
            total_gb=_bytes_to_gb(primary_usage.total),
            used_gb=_bytes_to_gb(primary_usage.used),
            free_gb=_bytes_to_gb(primary_usage.free),
            usage_percent=round(primary_usage.percent, 1),
            partitions=partitions,
        )

    def get_top_processes(self, limit: int = 10) -> ProcessOverview:
        logical_cores = psutil.cpu_count(logical=True) or 1
        summaries: list[ProcessSummary] = []

        attrs = ["pid", "name", "status", "memory_percent", "memory_info", "username"]
        for proc in psutil.process_iter(attrs=attrs):
            try:
                info = proc.info
                pid = info["pid"]
                name = info["name"] or "unknown"

                if self.adapter.should_skip_process(pid, name):
                    continue

                # Normalize process CPU% across all logical cores so it stays on a 0-100% scale
                raw_cpu = proc.cpu_percent(interval=None) or 0.0
                norm_cpu = round(min(raw_cpu / logical_cores, 100.0), 1)

                mem_info = info.get("memory_info")
                mem_mb = _bytes_to_mb(mem_info.rss) if mem_info else 0.0
                mem_pct = round(info.get("memory_percent") or 0.0, 2)

                summaries.append(
                    ProcessSummary(
                        pid=pid,
                        name=name,
                        status=info.get("status") or "unknown",
                        cpu_percent=norm_cpu,
                        memory_percent=mem_pct,
                        memory_mb=mem_mb,
                        username=info.get("username"),
                        is_protected=self.adapter.is_protected_process(pid, name),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        top_cpu = sorted(summaries, key=lambda p: p.cpu_percent, reverse=True)[:limit]
        top_memory = sorted(summaries, key=lambda p: p.memory_percent, reverse=True)[:limit]

        return ProcessOverview(
            total_running=len(summaries),
            top_cpu=top_cpu,
            top_memory=top_memory,
        )

    def get_process_details(self, pid: int) -> ProcessDetail | None:
        logical_cores = psutil.cpu_count(logical=True) or 1
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                name = proc.name()
                status = proc.status()
                raw_cpu = proc.cpu_percent(interval=0.1)
                norm_cpu = round(min(raw_cpu / logical_cores, 100.0), 1)
                mem_info = proc.memory_info()
                mem_pct = round(proc.memory_percent(), 2)
                create_dt = from_timestamp_ist(proc.create_time())
                parent_pid = proc.ppid()
                num_threads = proc.num_threads()

                # These fields can raise AccessDenied on elevated system processes
                try:
                    username = proc.username()
                except psutil.AccessDenied:
                    username = None
                try:
                    cmdline = proc.cmdline()
                except psutil.AccessDenied:
                    cmdline = []
                try:
                    exe = proc.exe()
                except psutil.AccessDenied:
                    exe = None

            return ProcessDetail(
                pid=pid,
                name=name,
                status=status,
                cpu_percent=norm_cpu,
                memory_percent=mem_pct,
                memory_mb=_bytes_to_mb(mem_info.rss),
                username=username,
                is_protected=self.adapter.is_protected_process(pid, name),
                cmdline=cmdline,
                exe=exe,
                parent_pid=parent_pid,
                create_time=create_dt,
                num_threads=num_threads,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def collect_snapshot(self, top_n: int = 10) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp=now_ist(),
            system_info=self.get_system_information(),
            cpu=self.get_cpu_metrics(interval=None),
            memory=self.get_memory_metrics(),
            disk=self.get_disk_metrics(),
            processes=self.get_top_processes(limit=top_n),
        )