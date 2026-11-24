import json
import os
from datetime import datetime, timezone
from pathlib import Path
import psutil

from app.remediation.guards import get_sentinel_temp_dir
from app.remediation.schemas import ActionExecutionResult


def _get_managed_service_state_file(service_name: str) -> Path:
    runtime_dir = Path(__file__).resolve().parent.parent.parent / "runtime" / "services"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / f"{service_name}.json"


def execute_terminate_process(
    target_pid: int,
    target_name: str,
    timeout_seconds: float = 3.0,
) -> ActionExecutionResult:
    """Gracefully terminate a verified non-critical process, escalating to kill if needed."""
    try:
        proc = psutil.Process(target_pid)
        proc.terminate()
        try:
            proc.wait(timeout=timeout_seconds)
            method = "terminate"
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)
            method = "kill"

        return ActionExecutionResult(
            executed=True,
            message=f"Stopped process '{target_name}' (PID {target_pid}) via {method}.",
            details={"pid": target_pid, "name": target_name, "method": method},
        )
    except psutil.NoSuchProcess:
        return ActionExecutionResult(
            executed=True,
            message=f"Process '{target_name}' (PID {target_pid}) already exited before termination.",
            details={"pid": target_pid, "name": target_name, "method": "already_exited"},
        )
    except psutil.AccessDenied:
        return ActionExecutionResult(
            executed=False,
            message=(
                f"Permission denied while stopping '{target_name}' (PID {target_pid}). "
                "SentinelAI will not elevate privileges automatically."
            ),
            details={"pid": target_pid, "name": target_name, "error": "AccessDenied"},
        )
    except Exception as exc:
        return ActionExecutionResult(
            executed=False,
            message=f"Failed to stop '{target_name}' (PID {target_pid}): {exc}",
            details={"pid": target_pid, "name": target_name, "error": str(exc)},
        )


def execute_restart_managed_service(service_name: str) -> ActionExecutionResult:
    """Safely restart a controlled SentinelAI demo worker without touching OS services."""
    state_file = _get_managed_service_state_file(service_name)
    previous_restarts = 0
    if state_file.exists():
        try:
            existing = json.loads(state_file.read_text(encoding="utf-8"))
            previous_restarts = int(existing.get("restart_count", 0))
        except Exception:
            previous_restarts = 0

    new_state = {
        "service_name": service_name,
        "status": "running",
        "restart_count": previous_restarts + 1,
        "last_restarted_at": datetime.now(timezone.utc).isoformat(),
        "host_pid": os.getpid(),
    }
    try:
        state_file.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
        return ActionExecutionResult(
            executed=True,
            message=f"Restarted managed service '{service_name}' (restart #{new_state['restart_count']}).",
            details=new_state,
        )
    except PermissionError as exc:
        return ActionExecutionResult(
            executed=False,
            message=f"Permission error restarting managed service '{service_name}': {exc}",
            details={"service_name": service_name, "error": "PermissionError"},
        )


def execute_clear_temp_directory() -> ActionExecutionResult:
    """Delete files inside SentinelAI's confined scratch temp directory."""
    temp_dir = get_sentinel_temp_dir()
    files_removed = 0
    bytes_freed = 0
    errors: list[str] = []

    for item in temp_dir.iterdir():
        if item.is_file():
            try:
                size = item.stat().st_size
                item.unlink()
                files_removed += 1
                bytes_freed += size
            except PermissionError:
                errors.append(f"Permission denied: {item.name}")
            except OSError as exc:
                errors.append(f"Could not delete {item.name}: {exc}")

    if errors and files_removed == 0:
        return ActionExecutionResult(
            executed=False,
            message=f"Could not clear temp files: {'; '.join(errors)}",
            details={"files_removed": 0, "bytes_freed": 0, "errors": errors},
        )

    mb_freed = round(bytes_freed / (1024 ** 2), 2)
    return ActionExecutionResult(
        executed=True,
        message=f"Removed {files_removed} file(s) from scratch temp directory ({mb_freed} MB freed).",
        details={
            "directory": str(temp_dir),
            "files_removed": files_removed,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors,
        },
    )