from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.anomalies.rules import AnomalyCategory, DetectedAnomaly, Severity
from app.api.deps import sentinel_agent
from app.db import repository
from app.db.database import get_db
from app.db.models import AnomalyRecord

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


class InvestigateRequest(BaseModel):
    anomaly_id: int | None = None
    prompt: str | None = None


@router.post("/investigate")
def run_investigation(request: InvestigateRequest, db: Session = Depends(get_db)) -> dict:
    if request.anomaly_id is None and (not request.prompt or not request.prompt.strip()):
        raise HTTPException(
            status_code=400,
            detail="Provide either 'anomaly_id' or a non-empty 'prompt'.",
        )

    if request.anomaly_id is not None:
        anomaly_row = db.get(AnomalyRecord, request.anomaly_id)
        if anomaly_row is None:
            raise HTTPException(status_code=404, detail=f"Anomaly {request.anomaly_id} not found.")

        detected = DetectedAnomaly(
            timestamp=anomaly_row.timestamp,
            category=AnomalyCategory(anomaly_row.category),
            severity=Severity(anomaly_row.severity),
            metric_name=anomaly_row.metric_name,
            current_value=anomaly_row.current_value,
            threshold_value=anomaly_row.threshold_value,
            message=anomaly_row.message,
            process_pid=anomaly_row.process_pid,
            process_name=anomaly_row.process_name,
            is_protected_process=anomaly_row.is_protected_process,
        )
        trigger_summary = f"Anomaly #{anomaly_row.id} ({anomaly_row.severity}): {anomaly_row.message}"
        try:
            report = sentinel_agent.investigate_anomaly(detected)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AI Agent investigation failed: {exc}") from exc
    else:
        trigger_summary = request.prompt.strip()  # type: ignore[union-attr]
        try:
            report = sentinel_agent.investigate(trigger_summary)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AI Agent investigation failed: {exc}") from exc

    incident, report_row, remediation_row = repository.save_investigation_result(
        db,
        trigger_summary=trigger_summary,
        report=report,
        anomaly_id=request.anomaly_id,
    )

    return {
        "incident_id": incident.id,
        "status": incident.status,
        "report": repository.serialize_report(report_row),
        "remediation": repository.serialize_remediation(remediation_row),
    }


@router.get("/reports")
def list_reports(limit: int = 30, db: Session = Depends(get_db)) -> list[dict]:
    return repository.list_reports(db, limit=max(1, min(limit, 100)))