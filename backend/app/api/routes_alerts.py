from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import repository
from app.db.database import get_db
from app.db.models import IncidentRecord

router = APIRouter(prefix="/api", tags=["Alerts & Incidents"])


@router.get("/alerts")
def get_alerts(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return repository.list_anomalies(db, limit=max(1, min(limit, 200)))


@router.get("/incidents")
def get_incidents(limit: int = 30, db: Session = Depends(get_db)) -> list[dict]:
    return repository.list_incidents(db, limit=max(1, min(limit, 100)))


@router.get("/incidents/{incident_id}")
def get_incident_detail(incident_id: int, db: Session = Depends(get_db)) -> dict:
    inc = db.get(IncidentRecord, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return {
        "id": inc.id,
        "anomaly_id": inc.anomaly_id,
        "created_at": inc.created_at.isoformat(),
        "trigger_summary": inc.trigger_summary,
        "severity": inc.severity,
        "status": inc.status,
        "reports": [repository.serialize_report(r) for r in inc.reports],
        "remediations": [repository.serialize_remediation(rem) for rem in inc.remediations],
    }