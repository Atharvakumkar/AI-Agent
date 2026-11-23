import json
from typing import Any, Callable
from langchain_core.tools import BaseTool, tool

from app.monitoring.collector import SystemMonitor

IncidentProvider = Callable[[int], list[dict[str, Any]]]


def create_diagnostic_tools(
    monitor: SystemMonitor,
    incident_provider: IncidentProvider | None = None,
) -> list[BaseTool]:
    """Build the 7 read-only diagnostic tools bound to a SystemMonitor instance."""

    def _default_incidents(limit: int) -> list[dict[str, Any]]:
        return []

    fetch_incidents = incident_provider or _default_incidents

    @tool
    def get_cpu_metrics() -> str:
        """Get current overall CPU usage percentage, per-core usage, core counts, and CPU frequency."""
        return monitor.get_cpu_metrics(interval=0.2).model_dump_json()

    @tool
    def get_memory_metrics() -> str:
        """Get current RAM usage percentage, total/used/available GB, and swap memory usage."""
        return monitor.get_memory_metrics().model_dump_json()

    @tool
    def get_disk_metrics() -> str:
        """Get primary disk usage percentage, free/used/total GB, and mounted partition details."""
        return monitor.get_disk_metrics().model_dump_json()

    @tool
    def get_top_processes(limit: int = 5) -> str:
        """Get total running process count and the top CPU-consuming and memory-consuming processes."""
        safe_limit = max(1, min(limit, 10))
        return monitor.get_top_processes(limit=safe_limit).model_dump_json()

    @tool
    def get_system_information() -> str:
        """Get OS name, version, hostname, architecture, processor, boot time, and system uptime."""
        return monitor.get_system_information().model_dump_json()

    @tool
    def get_process_details(pid: int) -> str:
        """Inspect detailed metadata for a specific process PID, including command line, executable path, threads, and whether it is protected."""
        detail = monitor.get_process_details(pid)
        if detail is None:
            return json.dumps({"error": f"Process with PID {pid} not found or access denied."})
        return detail.model_dump_json()

    @tool
    def get_previous_incidents(limit: int = 5) -> str:
        """Retrieve recent historical anomalies and past incident investigations from the database."""
        safe_limit = max(1, min(limit, 20))
        incidents = fetch_incidents(safe_limit)
        return json.dumps({"count": len(incidents), "incidents": incidents}, default=str)

    return [
        get_cpu_metrics,
        get_memory_metrics,
        get_disk_metrics,
        get_top_processes,
        get_system_information,
        get_process_details,
        get_previous_incidents,
    ]