from datetime import datetime, timedelta, timezone
import pytest

from app.anomalies.detector import AnomalyDetector
from app.anomalies.rules import AnomalyCategory, Severity, ThresholdConfig
from app.monitoring.schemas import (
    CpuMetrics,
    DiskMetrics,
    MemoryMetrics,
    ProcessOverview,
    ProcessSummary,
    SystemInfo,
    SystemSnapshot,
)


def _make_snapshot(
    *,
    timestamp: datetime | None = None,
    cpu_pct: float = 20.0,
    mem_pct: float = 40.0,
    disk_pct: float = 50.0,
    top_cpu: list[ProcessSummary] | None = None,
    top_memory: list[ProcessSummary] | None = None,
) -> SystemSnapshot:
    now = timestamp or datetime.now(timezone.utc)
    return SystemSnapshot(
        timestamp=now,
        system_info=SystemInfo(
            hostname="test-host",
            os_name="Windows",
            os_release="11",
            os_version="10.0.22621",
            architecture="AMD64",
            processor="x86_64",
            boot_time=now - timedelta(hours=5),
            uptime_seconds=18000,
            uptime_human="5h 0m",
        ),
        cpu=CpuMetrics(
            usage_percent=cpu_pct,
            per_core_percent=[cpu_pct],
            logical_cores=4,
            physical_cores=4,
        ),
        memory=MemoryMetrics(
            total_gb=16.0,
            used_gb=round(16.0 * mem_pct / 100, 2),
            available_gb=round(16.0 * (100 - mem_pct) / 100, 2),
            usage_percent=mem_pct,
            swap_total_gb=4.0,
            swap_used_gb=0.0,
            swap_percent=0.0,
        ),
        disk=DiskMetrics(
            primary_mount="C:\\",
            total_gb=500.0,
            used_gb=round(500.0 * disk_pct / 100, 2),
            free_gb=round(500.0 * (100 - disk_pct) / 100, 2),
            usage_percent=disk_pct,
            partitions=[],
        ),
        processes=ProcessOverview(
            total_running=100,
            top_cpu=top_cpu or [],
            top_memory=top_memory or [],
        ),
    )


def test_healthy_snapshot_produces_no_anomalies():
    detector = AnomalyDetector(ThresholdConfig())
    anomalies = detector.evaluate(_make_snapshot(cpu_pct=25.0, mem_pct=50.0, disk_pct=60.0))
    assert anomalies == []


def test_system_warning_and_critical_detection():
    detector = AnomalyDetector(ThresholdConfig(cooldown_seconds=60))
    anomalies = detector.evaluate(_make_snapshot(cpu_pct=82.0, mem_pct=95.0, disk_pct=91.0))

    by_category = {a.category: a for a in anomalies}
    assert by_category[AnomalyCategory.CPU].severity == Severity.WARNING
    assert by_category[AnomalyCategory.MEMORY].severity == Severity.CRITICAL
    assert by_category[AnomalyCategory.DISK].severity == Severity.CRITICAL


def test_cooldown_suppresses_duplicates_and_allows_escalation():
    t0 = datetime.now(timezone.utc)
    detector = AnomalyDetector(ThresholdConfig(cooldown_seconds=120))

    # First WARNING fires
    first = detector.evaluate(_make_snapshot(timestamp=t0, cpu_pct=80.0))
    assert len(first) == 1
    assert first[0].severity == Severity.WARNING

    # Repeat WARNING 10s later is suppressed
    second = detector.evaluate(_make_snapshot(timestamp=t0 + timedelta(seconds=10), cpu_pct=82.0))
    assert second == []

    # Escalation to CRITICAL 20s later fires immediately
    third = detector.evaluate(_make_snapshot(timestamp=t0 + timedelta(seconds=20), cpu_pct=94.0))
    assert len(third) == 1
    assert third[0].severity == Severity.CRITICAL

    # Recovery clears cooldown so a later WARNING fires again
    detector.evaluate(_make_snapshot(timestamp=t0 + timedelta(seconds=30), cpu_pct=30.0))
    fourth = detector.evaluate(_make_snapshot(timestamp=t0 + timedelta(seconds=40), cpu_pct=78.0))
    assert len(fourth) == 1
    assert fourth[0].severity == Severity.WARNING


def test_process_anomaly_captures_pid_and_name():
    runaway = ProcessSummary(
        pid=4321,
        name="python.exe",
        status="running",
        cpu_percent=75.0,
        memory_percent=30.0,
        memory_mb=1200.0,
        is_protected=False,
    )
    detector = AnomalyDetector(ThresholdConfig())
    anomalies = detector.evaluate(_make_snapshot(top_cpu=[runaway], top_memory=[runaway]))

    categories = {a.category for a in anomalies}
    assert AnomalyCategory.PROCESS_CPU in categories
    assert AnomalyCategory.PROCESS_MEMORY in categories
    for alert in anomalies:
        assert alert.process_pid == 4321
        assert alert.process_name == "python.exe"


def test_invalid_threshold_config_raises_error():
    with pytest.raises(ValueError):
        ThresholdConfig(cpu_warning=90.0, cpu_critical=80.0)