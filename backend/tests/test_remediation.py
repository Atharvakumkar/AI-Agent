import os
import platform
import subprocess
import sys
import time
from pathlib import Path
import psutil

from app.agent.schemas import RemediationActionType, RemediationProposal, RiskLevel
from app.monitoring.collector import SystemMonitor
from app.remediation.guards import get_sentinel_temp_dir
from app.remediation.registry import RemediationEngine
from app.remediation.schemas import RemediationStatus


def test_unapproved_proposal_is_rejected_without_execution():
    engine = RemediationEngine(SystemMonitor(), settle_seconds=0.1)
    proposal = RemediationProposal(
        action_type=RemediationActionType.CLEAR_TEMP_DIRECTORY,
        rationale="Free scratch disk space.",
        risk_level=RiskLevel.LOW,
    )
    outcome = engine.handle_proposal(proposal, approved=False)

    assert outcome.status == RemediationStatus.REJECTED
    assert outcome.execution is None
    assert outcome.verification is None


def test_self_termination_is_blocked():
    engine = RemediationEngine(SystemMonitor(), settle_seconds=0.1)
    current_pid = os.getpid()
    current_name = psutil.Process(current_pid).name()

    proposal = RemediationProposal(
        action_type=RemediationActionType.TERMINATE_PROCESS,
        target_pid=current_pid,
        target_name=current_name,
        rationale="Attempt to kill self.",
        risk_level=RiskLevel.HIGH,
    )
    outcome = engine.handle_proposal(proposal, approved=True)

    assert outcome.status == RemediationStatus.BLOCKED
    assert "parent runtime" in outcome.guard_check.reason or "SentinelAI" in outcome.guard_check.reason
    assert psutil.pid_exists(current_pid)


def test_protected_os_process_is_blocked():
    engine = RemediationEngine(SystemMonitor(), settle_seconds=0.1)
    if platform.system().lower() == "windows":
        pid, name = 4, "System"
    else:
        pid, name = 1, "systemd"

    proposal = RemediationProposal(
        action_type=RemediationActionType.TERMINATE_PROCESS,
        target_pid=pid,
        target_name=name,
        rationale="Attempt to stop critical OS process.",
        risk_level=RiskLevel.HIGH,
    )
    outcome = engine.handle_proposal(proposal, approved=True)

    assert outcome.status == RemediationStatus.BLOCKED
    assert "protected" in outcome.guard_check.reason.lower()


def test_unlisted_service_is_blocked_and_allowed_service_restarts():
    engine = RemediationEngine(SystemMonitor(), settle_seconds=0.1)

    bad_proposal = RemediationProposal(
        action_type=RemediationActionType.RESTART_MANAGED_SERVICE,
        target_name="sshd",
        rationale="Try restarting real OS service.",
        risk_level=RiskLevel.HIGH,
    )
    bad_outcome = engine.handle_proposal(bad_proposal, approved=True)
    assert bad_outcome.status == RemediationStatus.BLOCKED

    good_proposal = RemediationProposal(
        action_type=RemediationActionType.RESTART_MANAGED_SERVICE,
        target_name="sentinel-demo-worker",
        rationale="Restart allowlisted demo worker.",
        risk_level=RiskLevel.LOW,
    )
    good_outcome = engine.handle_proposal(good_proposal, approved=True)
    assert good_outcome.status == RemediationStatus.VERIFIED_RESOLVED
    assert good_outcome.verification is not None
    assert good_outcome.verification.resolved is True


def test_clear_temp_directory_cleans_and_verifies():
    temp_dir = get_sentinel_temp_dir()
    dummy_file = temp_dir / "sentinel_test_junk.tmp"
    dummy_file.write_bytes(b"0" * 1024 * 64)  # 64 KB dummy file

    engine = RemediationEngine(SystemMonitor(), settle_seconds=0.1)
    proposal = RemediationProposal(
        action_type=RemediationActionType.CLEAR_TEMP_DIRECTORY,
        rationale="Clean scratch temp directory.",
        risk_level=RiskLevel.LOW,
    )
    outcome = engine.handle_proposal(proposal, approved=True)

    assert outcome.status == RemediationStatus.VERIFIED_RESOLVED
    assert not dummy_file.exists()
    assert outcome.execution is not None
    assert outcome.execution.details["files_removed"] >= 1


def test_terminate_live_load_simulator_and_verify():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "load_simulator.py"
    proc = subprocess.Popen(
        [sys.executable, str(script_path), "--mode", "cpu", "--duration", "20"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.5)
        live_name = psutil.Process(proc.pid).name()
        engine = RemediationEngine(SystemMonitor(), settle_seconds=0.3)

        # First verify PID-name mismatch guard blocks wrong name
        mismatch_proposal = RemediationProposal(
            action_type=RemediationActionType.TERMINATE_PROCESS,
            target_pid=proc.pid,
            target_name="totally_wrong_name.exe",
            rationale="Mismatched process name test.",
            risk_level=RiskLevel.MEDIUM,
        )
        mismatch_outcome = engine.handle_proposal(mismatch_proposal, approved=True)
        assert mismatch_outcome.status == RemediationStatus.BLOCKED
        assert psutil.pid_exists(proc.pid)

        # Now approve with exact verified PID and name
        valid_proposal = RemediationProposal(
            action_type=RemediationActionType.TERMINATE_PROCESS,
            target_pid=proc.pid,
            target_name=live_name,
            rationale="Stop runaway CPU load simulator.",
            risk_level=RiskLevel.LOW,
        )
        outcome = engine.handle_proposal(valid_proposal, approved=True)

        assert outcome.status == RemediationStatus.VERIFIED_RESOLVED
        assert outcome.verification is not None
        assert outcome.verification.resolved is True
        assert not psutil.pid_exists(proc.pid)
    finally:
        if proc.poll() is None:
            proc.kill()