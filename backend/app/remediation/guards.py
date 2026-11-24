import os
from pathlib import Path
import psutil

from app.monitoring.collector import SystemMonitor
from app.remediation.schemas import GuardCheckResult

ALLOWED_MANAGED_SERVICES: frozenset[str] = frozenset({"sentinel-demo-worker"})


def get_sentinel_temp_dir() -> Path:
    """Return the dedicated scratch directory that SentinelAI is allowed to clean."""
    base = Path(__file__).resolve().parent.parent.parent / "runtime" / "temp_scratch"
    base.mkdir(parents=True, exist_ok=True)
    return base


def validate_terminate_process(
    monitor: SystemMonitor,
    target_pid: int | None,
    target_name: str | None,
) -> GuardCheckResult:
    if target_pid is None or target_pid <= 0:
        return GuardCheckResult(allowed=False, reason="Missing or invalid target_pid.")

    if not target_name or not target_name.strip():
        return GuardCheckResult(
            allowed=False,
            reason="Missing target_name; exact process name is required for PID verification.",
        )

    # Prevent SentinelAI from terminating itself or its immediate parent runner
    protected_self_pids = {os.getpid(), os.getppid()}
    if target_pid in protected_self_pids:
        return GuardCheckResult(
            allowed=False,
            reason=f"Blocked: PID {target_pid} belongs to SentinelAI or its parent runtime.",
        )

    # Check OS-level protected list before inspecting the process handle
    if monitor.adapter.is_protected_process(target_pid, target_name):
        return GuardCheckResult(
            allowed=False,
            reason=f"Blocked: '{target_name}' (PID {target_pid}) is a protected system process.",
        )

    try:
        proc = psutil.Process(target_pid)
        live_name = proc.name()
    except psutil.NoSuchProcess:
        return GuardCheckResult(
            allowed=False,
            reason=f"Process PID {target_pid} no longer exists.",
        )
    except psutil.AccessDenied:
        return GuardCheckResult(
            allowed=False,
            reason=f"Access denied while inspecting PID {target_pid}.",
        )

    # Re-check protected list against the live process name from the OS
    if monitor.adapter.is_protected_process(target_pid, live_name):
        return GuardCheckResult(
            allowed=False,
            reason=f"Blocked: live process '{live_name}' (PID {target_pid}) is protected.",
        )

    # Defend against PID reuse between investigation and user approval
    if live_name.lower() != target_name.strip().lower():
        return GuardCheckResult(
            allowed=False,
            reason=(
                f"PID reuse guard triggered: expected '{target_name}' at PID {target_pid}, "
                f"but found '{live_name}'."
            ),
        )

    return GuardCheckResult(
        allowed=True,
        reason=f"Verified non-protected process '{live_name}' (PID {target_pid}).",
    )


def validate_restart_managed_service(target_name: str | None) -> GuardCheckResult:
    if not target_name or target_name.strip().lower() not in ALLOWED_MANAGED_SERVICES:
        allowed_list = ", ".join(sorted(ALLOWED_MANAGED_SERVICES))
        return GuardCheckResult(
            allowed=False,
            reason=(
                f"Blocked: '{target_name}' is not an allowlisted managed service. "
                f"Allowed: [{allowed_list}]."
            ),
        )
    return GuardCheckResult(
        allowed=True,
        reason=f"Verified allowlisted managed service '{target_name}'.",
    )


def validate_clear_temp_directory() -> GuardCheckResult:
    temp_dir = get_sentinel_temp_dir().resolve()
    # Confine deletion strictly to SentinelAI's own scratch folder
    if temp_dir.name != "temp_scratch" or not temp_dir.exists():
        return GuardCheckResult(
            allowed=False,
            reason=f"Blocked: temp directory '{temp_dir}' failed safety confinement check.",
        )
    return GuardCheckResult(
        allowed=True,
        reason=f"Verified confined temp directory '{temp_dir}'.",
    )