from datetime import datetime, timezone

from app.agent.schemas import RemediationActionType, RemediationProposal
from app.monitoring.collector import SystemMonitor
from app.remediation.actions import (
    execute_clear_temp_directory,
    execute_restart_managed_service,
    execute_terminate_process,
)
from app.remediation.guards import (
    validate_clear_temp_directory,
    validate_restart_managed_service,
    validate_terminate_process,
)
from app.remediation.schemas import (
    GuardCheckResult,
    RemediationOutcome,
    RemediationStatus,
)
from app.remediation.verifier import RemediationVerifier


class RemediationEngine:
    """Executes only user-approved, allowlisted, guard-verified remediation actions."""

    def __init__(self, monitor: SystemMonitor, settle_seconds: float = 1.0) -> None:
        self.monitor = monitor
        self.verifier = RemediationVerifier(monitor, settle_seconds=settle_seconds)

    def handle_proposal(
        self,
        proposal: RemediationProposal,
        approved: bool,
    ) -> RemediationOutcome:
        now = datetime.now(timezone.utc)

        # 1. Explicit human approval gate
        if not approved:
            return RemediationOutcome(
                action_type=proposal.action_type,
                target_pid=proposal.target_pid,
                target_name=proposal.target_name,
                status=RemediationStatus.REJECTED,
                approved_by_user=False,
                guard_check=GuardCheckResult(
                    allowed=False,
                    reason="Action was rejected by the user.",
                ),
                executed_at=now,
            )

        # 2. Reject 'none' or non-executable proposals
        if proposal.action_type == RemediationActionType.NONE:
            return RemediationOutcome(
                action_type=proposal.action_type,
                target_pid=proposal.target_pid,
                target_name=proposal.target_name,
                status=RemediationStatus.BLOCKED,
                approved_by_user=True,
                guard_check=GuardCheckResult(
                    allowed=False,
                    reason="No executable remediation action was proposed (action_type='none').",
                ),
                executed_at=now,
            )

        # 3. Run action-specific safety guard
        guard_result = self._run_guard(proposal)
        if not guard_result.allowed:
            return RemediationOutcome(
                action_type=proposal.action_type,
                target_pid=proposal.target_pid,
                target_name=proposal.target_name,
                status=RemediationStatus.BLOCKED,
                approved_by_user=True,
                guard_check=guard_result,
                executed_at=now,
            )

        # 4. Capture pre-action baseline metrics
        baseline = self.verifier.capture_baseline()

        # 5. Dispatch strictly to allowlisted Python handler
        execution = self._dispatch_action(proposal)

        # 6. Independently verify outcome with post-action metrics
        verification = self.verifier.verify(
            action_type=proposal.action_type,
            baseline=baseline,
            execution=execution,
            target_pid=proposal.target_pid,
            target_name=proposal.target_name,
        )

        if not execution.executed:
            final_status = RemediationStatus.FAILED
        elif verification.resolved:
            final_status = RemediationStatus.VERIFIED_RESOLVED
        else:
            final_status = RemediationStatus.EXECUTED_UNRESOLVED

        return RemediationOutcome(
            action_type=proposal.action_type,
            target_pid=proposal.target_pid,
            target_name=proposal.target_name,
            status=final_status,
            approved_by_user=True,
            guard_check=guard_result,
            execution=execution,
            verification=verification,
            executed_at=datetime.now(timezone.utc),
        )

    def _run_guard(self, proposal: RemediationProposal) -> GuardCheckResult:
        if proposal.action_type == RemediationActionType.TERMINATE_PROCESS:
            return validate_terminate_process(
                self.monitor, proposal.target_pid, proposal.target_name
            )
        if proposal.action_type == RemediationActionType.RESTART_MANAGED_SERVICE:
            return validate_restart_managed_service(proposal.target_name)
        if proposal.action_type == RemediationActionType.CLEAR_TEMP_DIRECTORY:
            return validate_clear_temp_directory()
        return GuardCheckResult(
            allowed=False,
            reason=f"Action '{proposal.action_type}' is not in the remediation allowlist.",
        )

    def _dispatch_action(self, proposal: RemediationProposal):
        if proposal.action_type == RemediationActionType.TERMINATE_PROCESS:
            return execute_terminate_process(
                target_pid=proposal.target_pid,  # type: ignore[arg-type]
                target_name=proposal.target_name or "",
            )
        if proposal.action_type == RemediationActionType.RESTART_MANAGED_SERVICE:
            return execute_restart_managed_service(proposal.target_name or "")
        if proposal.action_type == RemediationActionType.CLEAR_TEMP_DIRECTORY:
            return execute_clear_temp_directory()
        raise ValueError(f"Unregistered action: {proposal.action_type}")