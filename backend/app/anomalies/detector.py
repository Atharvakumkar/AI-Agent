from datetime import datetime, timedelta

from app.anomalies.rules import (
    AnomalyCategory,
    DetectedAnomaly,
    Severity,
    ThresholdConfig,
)
from app.monitoring.schemas import SystemSnapshot


class AnomalyDetector:
    """Evaluates SystemSnapshots against configurable thresholds with cooldowns."""

    def __init__(self, thresholds: ThresholdConfig | None = None) -> None:
        self.thresholds = thresholds or ThresholdConfig.from_settings()
        # Maps anomaly_key -> (last_triggered_timestamp, last_severity)
        self._active_cooldowns: dict[str, tuple[datetime, Severity]] = {}

    def update_thresholds(self, new_thresholds: ThresholdConfig) -> None:
        self.thresholds = new_thresholds

    def reset_cooldowns(self) -> None:
        self._active_cooldowns.clear()

    def _classify(self, value: float, warn: float, crit: float) -> tuple[Severity, float] | None:
        if value >= crit:
            return Severity.CRITICAL, crit
        if value >= warn:
            return Severity.WARNING, warn
        return None

    def _should_emit(self, key: str, severity: Severity, now: datetime) -> bool:
        previous = self._active_cooldowns.get(key)
        if previous is None:
            self._active_cooldowns[key] = (now, severity)
            return True

        last_time, last_severity = previous
        cooldown = timedelta(seconds=self.thresholds.cooldown_seconds)

        # Allow immediate alert if severity escalates from WARNING to CRITICAL
        escalated = last_severity == Severity.WARNING and severity == Severity.CRITICAL
        expired = (now - last_time) >= cooldown

        if escalated or expired:
            self._active_cooldowns[key] = (now, severity)
            return True

        return False

    def _clear_if_recovered(self, key: str) -> None:
        self._active_cooldowns.pop(key, None)

    def evaluate(self, snapshot: SystemSnapshot) -> list[DetectedAnomaly]:
        now = snapshot.timestamp
        anomalies: list[DetectedAnomaly] = []

        # 1. System-wide CPU, Memory, and Disk checks
        system_checks = [
            (
                "system_cpu",
                AnomalyCategory.CPU,
                "cpu_usage_percent",
                snapshot.cpu.usage_percent,
                self.thresholds.cpu_warning,
                self.thresholds.cpu_critical,
                f"System CPU usage is {snapshot.cpu.usage_percent:.1f}%",
            ),
            (
                "system_memory",
                AnomalyCategory.MEMORY,
                "memory_usage_percent",
                snapshot.memory.usage_percent,
                self.thresholds.memory_warning,
                self.thresholds.memory_critical,
                (
                    f"System memory usage is {snapshot.memory.usage_percent:.1f}% "
                    f"({snapshot.memory.available_gb:.2f} GB available)"
                ),
            ),
            (
                "system_disk",
                AnomalyCategory.DISK,
                "disk_usage_percent",
                snapshot.disk.usage_percent,
                self.thresholds.disk_warning,
                self.thresholds.disk_critical,
                (
                    f"Primary disk ({snapshot.disk.primary_mount}) usage is "
                    f"{snapshot.disk.usage_percent:.1f}% ({snapshot.disk.free_gb:.2f} GB free)"
                ),
            ),
        ]

        for key, category, metric_name, value, warn, crit, base_msg in system_checks:
            result = self._classify(value, warn, crit)
            if result is None:
                self._clear_if_recovered(key)
                continue

            severity, threshold_hit = result
            if self._should_emit(key, severity, now):
                anomalies.append(
                    DetectedAnomaly(
                        timestamp=now,
                        category=category,
                        severity=severity,
                        metric_name=metric_name,
                        current_value=value,
                        threshold_value=threshold_hit,
                        message=f"{base_msg} (threshold: {threshold_hit:.1f}%)",
                    )
                )

        # 2. Per-process CPU anomalies
        active_proc_cpu_keys: set[str] = set()
        for proc in snapshot.processes.top_cpu:
            result = self._classify(
                proc.cpu_percent,
                self.thresholds.process_cpu_warning,
                self.thresholds.process_cpu_critical,
            )
            if result is None:
                continue

            key = f"proc_cpu:{proc.pid}"
            active_proc_cpu_keys.add(key)
            severity, threshold_hit = result
            if self._should_emit(key, severity, now):
                anomalies.append(
                    DetectedAnomaly(
                        timestamp=now,
                        category=AnomalyCategory.PROCESS_CPU,
                        severity=severity,
                        metric_name="process_cpu_percent",
                        current_value=proc.cpu_percent,
                        threshold_value=threshold_hit,
                        message=(
                            f"Process '{proc.name}' (PID {proc.pid}) is consuming "
                            f"{proc.cpu_percent:.1f}% CPU (threshold: {threshold_hit:.1f}%)"
                        ),
                        process_pid=proc.pid,
                        process_name=proc.name,
                        is_protected_process=proc.is_protected,
                    )
                )

        # Clean up recovered process CPU keys
        for key in list(self._active_cooldowns.keys()):
            if key.startswith("proc_cpu:") and key not in active_proc_cpu_keys:
                self._clear_if_recovered(key)

        # 3. Per-process Memory anomalies
        active_proc_mem_keys: set[str] = set()
        for proc in snapshot.processes.top_memory:
            result = self._classify(
                proc.memory_percent,
                self.thresholds.process_memory_warning,
                self.thresholds.process_memory_critical,
            )
            if result is None:
                continue

            key = f"proc_mem:{proc.pid}"
            active_proc_mem_keys.add(key)
            severity, threshold_hit = result
            if self._should_emit(key, severity, now):
                anomalies.append(
                    DetectedAnomaly(
                        timestamp=now,
                        category=AnomalyCategory.PROCESS_MEMORY,
                        severity=severity,
                        metric_name="process_memory_percent",
                        current_value=proc.memory_percent,
                        threshold_value=threshold_hit,
                        message=(
                            f"Process '{proc.name}' (PID {proc.pid}) is consuming "
                            f"{proc.memory_percent:.1f}% RAM ({proc.memory_mb:.1f} MB, "
                            f"threshold: {threshold_hit:.1f}%)"
                        ),
                        process_pid=proc.pid,
                        process_name=proc.name,
                        is_protected_process=proc.is_protected,
                    )
                )

        # Clean up recovered process memory keys
        for key in list(self._active_cooldowns.keys()):
            if key.startswith("proc_mem:") and key not in active_proc_mem_keys:
                self._clear_if_recovered(key)

        return anomalies