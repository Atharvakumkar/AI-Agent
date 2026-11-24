from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import psutil
import pytest
from fastapi.testclient import TestClient

from app.agent.schemas import (
    InvestigationReport,
    RemediationActionType,
    RemediationProposal,
    RiskLevel,
)
from app.anomalies.rules import AnomalyCategory, DetectedAnomaly, Severity
from app.db import database, repository
from app.main import app
from app.monitoring.linux_adapter import LinuxAdapter
from app.monitoring.windows_adapter import WindowsAdapter
from app.remediation.actions import execute_terminate_process


@pytest.fixture()
def client(tmp_path: Path):
    test_db_url = f"sqlite:///{tmp_path / 'test_e2e_sentinelai.db'}"
    database.configure_database(test_db_url)
    database.init_db()
    with TestClient(app) as test_client:
        yield test_client


def test_anomaly_to_investigation_and_user_rejection_flow(client: TestClient):
    """Verify full flow from persisted anomaly -> AI investigation -> user rejection -> SQLite audit."""
    db = database.SessionLocal()
    try:
        anomaly_row = repository.save_anomaly(
            db,
            DetectedAnomaly(
                timestamp=datetime.now(timezone.utc),
                category=AnomalyCategory.PROCESS_CPU,
                severity=Severity.CRITICAL,
                metric_name="process_cpu_percent",
                current_value=84.5,
                threshold_value=70.0,
                message="Process 'worker.exe' (PID 5555) is consuming 84.5% CPU",
                process_pid=5555,
                process_name="worker.exe",
                is_protected_process=False,
            ),
        )
        anomaly_id = anomaly_row.id
    finally:
        db.close()

    mock_report = InvestigationReport(
        summary="Process worker.exe (PID 5555) is saturating CPU.",
        severity="CRITICAL",
        confirmed_observations=["worker.exe (PID 5555) measured at 84.5% CPU."],
        suspected_causes=["Tight compute loop inside worker.exe."],
        recommended_remediation=RemediationProposal(
            action_type=RemediationActionType.TERMINATE_PROCESS,
            target_pid=5555,
            target_name="worker.exe",
            rationale="Terminate runaway non-protected worker process.",
            risk_level=RiskLevel.MEDIUM,
        ),
        tools_used=["get_cpu_metrics", "get_top_processes", "get_process_details"],
    )

    with patch(
        "app.api.routes_agent.sentinel_agent.investigate_anomaly",
        return_value=mock_report,
    ):
        inv_resp = client.post(
            "/api/agent/investigate",
            json={"anomaly_id": anomaly_id},
        )

    assert inv_resp.status_code == 200
    data = inv_resp.json()
    remediation_id = data["remediation"]["id"]
    assert data["report"]["tools_used"] == [
        "get_cpu_metrics",
        "get_top_processes",
        "get_process_details",
    ]

    # User rejects the proposed action
    reject_resp = client.post(
        f"/api/remediation/{remediation_id}/decide",
        json={"approved": False},
    )
    assert reject_resp.status_code == 200
    rejected = reject_resp.json()
    assert rejected["status"] == "REJECTED"
    assert rejected["approved_by_user"] is False

    # Verify incident history reflects REJECTED status
    incidents = client.get("/api/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["anomaly_id"] == anomaly_id
    assert incidents[0]["status"] == "REJECTED"


def test_api_blocks_approved_termination_of_protected_process(client: TestClient):
    """Even if an LLM proposes a protected OS process and the user clicks Approve, backend guards must block it."""
    mock_report = InvestigationReport(
        summary="Critical system process activity observed.",
        severity="WARNING",
        confirmed_observations=["High kernel thread activity."],
        suspected_causes=["OS background indexing."],
        recommended_remediation=RemediationProposal(
            action_type=RemediationActionType.TERMINATE_PROCESS,
            target_pid=4,
            target_name="System",
            rationale="Unsafe proposal to stop System process.",
            risk_level=RiskLevel.HIGH,
        ),
        tools_used=["get_top_processes"],
    )

    with patch("app.api.routes_agent.sentinel_agent.investigate", return_value=mock_report):
        inv_resp = client.post(
            "/api/agent/investigate",
            json={"prompt": "Investigate kernel load."},
        )

    remediation_id = inv_resp.json()["remediation"]["id"]

    approve_resp = client.post(
        f"/api/remediation/{remediation_id}/decide",
        json={"approved": True},
    )
    assert approve_resp.status_code == 200
    body = approve_resp.json()
    assert body["status"] == "BLOCKED"
    assert body["guard_allowed"] is False
    assert "protected" in body["guard_reason"].lower()


def test_permission_error_handled_safely_without_crashing():
    """Verify AccessDenied during process termination returns a clean failure result."""
    mock_proc = MagicMock()
    mock_proc.terminate.side_effect = psutil.AccessDenied(pid=8888)

    with patch("app.remediation.actions.psutil.Process", return_value=mock_proc):
        result = execute_terminate_process(target_pid=8888, target_name="elevated_task.exe")

    assert result.executed is False
    assert result.details["error"] == "AccessDenied"
    assert "Permission denied" in result.message


def test_windows_and_linux_adapter_cross_platform_rules():
    """Verify both OS adapters enforce their mount filtering and protected-process lists."""
    win = WindowsAdapter()
    assert win.get_primary_disk_path().endswith("\\")
    assert win.is_protected_process(4, "System") is True
    assert win.is_protected_process(1200, "csrss.exe") is True
    assert win.is_protected_process(1200, "python.exe") is False
    assert win.should_skip_process(0, "System Idle Process") is True
    assert win.should_include_partition(SimpleNamespace(opts="cdrom", fstype="CDFS")) is False
    assert win.should_include_partition(SimpleNamespace(opts="rw,fixed", fstype="NTFS")) is True

    linux = LinuxAdapter()
    assert linux.get_primary_disk_path() == "/"
    assert linux.is_protected_process(1, "systemd") is True
    assert linux.is_protected_process(512, "sshd") is True
    assert linux.is_protected_process(512, "python3") is False
    assert (
        linux.should_include_partition(
            SimpleNamespace(mountpoint="/snap/core20/2318", fstype="squashfs")
        )
        is False
    )
    assert (
        linux.should_include_partition(SimpleNamespace(mountpoint="/", fstype="ext4"))
        is True
    )