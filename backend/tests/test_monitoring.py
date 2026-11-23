import os
import time
from app.monitoring.collector import SystemMonitor


def test_collect_snapshot_returns_valid_metrics():
    monitor = SystemMonitor()
    time.sleep(0.5)  # Allow CPU counters to accumulate a real delta
    snapshot = monitor.collect_snapshot(top_n=5)

    assert snapshot.system_info.hostname
    assert snapshot.system_info.uptime_seconds >= 0
    assert 0.0 <= snapshot.cpu.usage_percent <= 100.0
    assert snapshot.cpu.logical_cores >= 1
    assert snapshot.memory.total_gb > 0
    assert 0.0 <= snapshot.memory.usage_percent <= 100.0
    assert snapshot.disk.total_gb > 0
    assert len(snapshot.disk.partitions) >= 1
    assert snapshot.processes.total_running > 0
    assert len(snapshot.processes.top_cpu) <= 5
    assert len(snapshot.processes.top_memory) <= 5


def test_get_process_details_for_current_process():
    monitor = SystemMonitor()
    current_pid = os.getpid()
    detail = monitor.get_process_details(current_pid)

    assert detail is not None
    assert detail.pid == current_pid
    assert detail.memory_mb > 0


def test_get_process_details_handles_invalid_pid():
    monitor = SystemMonitor()
    assert monitor.get_process_details(9999999) is None