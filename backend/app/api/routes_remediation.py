from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.schemas import RemediationActionType, RemediationProposal, RiskLevel
from app.api.deps import remediation_engine
from app.db import repository
from app.db.database import get_db
from app.db.models import RemediationActionRecord
from app.remediation.schemas import RemediationStatus

router = APIRouter(prefix="/api/remediation", tags=["Remediation"])


class RemediationDecisionRequest(BaseModel):
    approved: bool


@router.get("/pending")
def get_pending_remediations(db: Session = Depends(get_db)) -> list[dict]:
    return repository.list_pending_remediations(db)


@router.post("/{remediation_id}/decide")
def decide_remediation(
    remediation_id: int,
    decision: RemediationDecisionRequest,
    db: Session = Depends(get_db),
) -> dict:
    record = db.get(RemediationActionRecord, remediation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Remediation {remediation_id} not found.")

    if record.status != RemediationStatus.PENDING.value:
        raise HTTPException(
            status_code=409,
            detail=f"Remediation {remediation_id} has already been processed (status={record.status}).",
        )

    proposal = RemediationProposal(
        action_type=RemediationActionType(record.action_type),
        target_pid=record.target_pid,
        target_name=record.target_name,
        rationale=record.rationale,
        risk_level=RiskLevel(record.risk_level),
    )

    outcome = remediation_engine.handle_proposal(proposal, approved=decision.approved)
    updated = repository.apply_remediation_outcome(db, record, outcome)
    return repository.serialize_remediation(updated)