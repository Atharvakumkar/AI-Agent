import json
import time
import psutil

from app.agent.schemas import RemediationActionType
from app.monitoring.collector import SystemMonitor
from app.monitoring.schemas import SystemSnapshot
from app.remediation.actions import _get_managed_service_state_file
from app.remediation.guards import get_sentinel_temp_dir
from app.remediation.schemas import (
    ActionExecutionResult,
    MetricDelta,
    VerificationResult,
)


class RemediationVerifier:
    """Verifies remediation effectiveness by comparing pre- and post-action system state."""

    def __init__(self, monitor: SystemMonitor, settle_seconds: float = 1.0) -> None:
        self.monitor = monitor
        self.settle_seconds = settle_seconds

    def capture_baseline(self) -> SystemSnapshot:
        return self.monitor.collect_snapshot(top_n=5)

    def verify(
        self,
        action_type: RemediationActionType,
        baseline: SystemSnapshot,
        execution: ActionExecutionResult,
        target_pid: int | None = None,
        target_name: str | None = None,
    ) -> VerificationResult:
        if self.settle_seconds > 0:
            time.sleep(self.settle_seconds)

        after = self.monitor.collect_snapshot(top_n=5)
        delta = MetricDelta(
            cpu_before=baseline.cpu.usage_percent,
            cpu_after=after.cpu.usage_percent,
            memory_before=baseline.memory.usage_percent,
            memory_after=after.memory.usage_percent,
            disk_before=baseline.disk.usage_percent,
            disk_after=after.disk.usage_percent,
        )

        if not execution.executed:
            return VerificationResult(
                resolved=False,
                summary="Remediation did not execute successfully; issue remains unresolved.",
                metrics=delta,
            )

        if action_type == RemediationActionType.TERMINATE_PROCESS:
            still_same_process = False
            if target_pid is not None and psutil.pid_exists(target_pid):
                try:
                    live_name = psutil.Process(target_pid).name()
                    still_same_process = (
                        target_name is not None
                        and live_name.lower() == target_name.strip().lower()
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    still_same_process = False

            if not still_same_process:
                return VerificationResult(
                    resolved=True,
                    summary=(
                        f"Verified: '{target_name}' (PID {target_pid}) is no longer running. "
                        f"CPU {delta.cpu_before:.1f}% -> {delta.cpu_after:.1f}%, "
                        f"RAM {delta.memory_before:.1f}% -> {delta.memory_after:.1f}%."
                    ),
                    metrics=delta,
                )
            return VerificationResult(
                resolved=False,
                summary=f"Verification failed: '{target_name}' (PID {target_pid}) is still active.",
                metrics=delta,
            )

        if action_type == RemediationActionType.RESTART_MANAGED_SERVICE:
            state_file = _get_managed_service_state_file(target_name or "")
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding="utf-8"))
                if state.get("status") == "running":
                    return VerificationResult(
                        resolved=True,
                        summary=(
                            f"Verified: managed service '{target_name}' is running "
                            f"(restart #{state.get('restart_count')})."
                        ),
                        metrics=delta,
                    )
            return VerificationResult(
                resolved=False,
                summary=f"Verification failed: managed service '{target_name}' is not confirmed running.",
                metrics=delta,
            )

        if action_type == RemediationActionType.CLEAR_TEMP_DIRECTORY:
            temp_dir = get_sentinel_temp_dir()
            remaining_files = [p for p in temp_dir.iterdir() if p.is_file()]
            if len(remaining_files) == 0:
                return VerificationResult(
                    resolved=True,
                    summary=(
                        f"Verified: scratch temp directory is clean "
                        f"(removed {execution.details.get('files_removed', 0)} file(s)). "
                        f"Disk {delta.disk_before:.1f}% -> {delta.disk_after:.1f}%."
                    ),
                    metrics=delta,
                )
            return VerificationResult(
                resolved=False,
                summary=f"Verification partial: {len(remaining_files)} file(s) still remain in temp directory.",
                metrics=delta,
            )

        return VerificationResult(
            resolved=False,
            summary=f"Unsupported verification action type: {action_type.value}",
            metrics=delta,
        )