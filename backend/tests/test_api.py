from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.agent.schemas import (
    InvestigationReport,
    RemediationActionType,
    RemediationProposal,
    RiskLevel,
)
from app.db import database
from app.main import app
from app.remediation.guards import get_sentinel_temp_dir


@pytest.fixture()
def client(tmp_path: Path):
    test_db_url = f"sqlite:///{tmp_path / 'test_sentinelai.db'}"
    database.configure_database(test_db_url)
    database.init_db()
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_snapshot_endpoints(client: TestClient):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    snap = client.get("/api/metrics/snapshot?top_n=3")
    assert snap.status_code == 200
    body = snap.json()
    assert "cpu" in body and "memory" in body and "disk" in body


def test_threshold_update_and_validation(client: TestClient):
    current = client.get("/api/metrics/thresholds")
    assert current.status_code == 200

    updated = client.put(
        "/api/metrics/thresholds",
        json={
            "cpu_warning": 70.0,
            "cpu_critical": 88.0,
            "memory_warning": 75.0,
            "memory_critical": 90.0,
            "disk_warning": 80.0,
            "disk_critical": 92.0,
            "process_cpu_warning": 35.0,
            "process_cpu_critical": 65.0,
            "process_memory_warning": 20.0,
            "process_memory_critical": 45.0,
            "cooldown_seconds": 60,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["cpu_warning"] == 70.0

    invalid = client.put(
        "/api/metrics/thresholds",
        json={"cpu_warning": 95.0, "cpu_critical": 80.0},
    )
    assert invalid.status_code == 422


def test_websocket_starts_and_closes_monitoring_session(client: TestClient):
    with client.websocket_connect("/ws/metrics") as ws:
        payload = ws.receive_json()
        assert payload["type"] == "metrics_update"
        assert payload["session_id"] is not None
        assert "cpu" in payload["snapshot"]

    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["status"] == "CLOSED"
    assert sessions[0]["ended_at"] is not None


def test_investigation_and_remediation_approval_flow(client: TestClient):
    # Create a dummy scratch file so clear_temp_directory has real work to verify
    temp_file = get_sentinel_temp_dir() / "api_test_junk.tmp"
    temp_file.write_bytes(b"x" * 1024)

    mock_report = InvestigationReport(
        summary="Scratch temp directory contains removable temporary files.",
        severity="WARNING",
        confirmed_observations=["Disk usage checked via get_disk_metrics."],
        suspected_causes=["Temporary files accumulated in scratch directory."],
        recommended_remediation=RemediationProposal(
            action_type=RemediationActionType.CLEAR_TEMP_DIRECTORY,
            rationale="Clear SentinelAI scratch temp files safely.",
            risk_level=RiskLevel.LOW,
        ),
        tools_used=["get_disk_metrics"],
    )

    with patch("app.api.routes_agent.sentinel_agent.investigate", return_value=mock_report):
        inv_resp = client.post(
            "/api/agent/investigate",
            json={"prompt": "Check disk health and clean temp files if needed."},
        )

    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    remediation_id = inv_data["remediation"]["id"]
    assert inv_data["remediation"]["status"] == "PENDING"

    # Confirm it shows up in pending queue
    pending = client.get("/api/remediation/pending").json()
    assert any(item["id"] == remediation_id for item in pending)

    # Approve and execute remediation
    decision = client.post(
        f"/api/remediation/{remediation_id}/decide",
        json={"approved": True},
    )
    assert decision.status_code == 200
    result = decision.json()
    assert result["status"] == "VERIFIED_RESOLVED"
    assert result["verification_resolved"] is True
    assert not temp_file.exists()

    # Re-deciding an already processed remediation returns 409 Conflict
    duplicate = client.post(
        f"/api/remediation/{remediation_id}/decide",
        json={"approved": True},
    )
    assert duplicate.status_code == 409

    # Incident history reflects RESOLVED status
    incidents = client.get("/api/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["status"] == "RESOLVED"