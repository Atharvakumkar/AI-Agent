import json
from app.time_utils import ensure_ist, now_ist
from typing import Any
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agent.schemas import InvestigationReport, RemediationActionType
from app.anomalies.rules import DetectedAnomaly
from app.db import database
from app.db.models import (
    AnomalyRecord,
    IncidentRecord,
    InvestigationReportRecord,
    MetricSnapshotRecord,
    MonitoringSession,
    RemediationActionRecord,
)
from app.monitoring.schemas import SystemSnapshot
from app.remediation.schemas import RemediationOutcome, RemediationStatus


def create_session(db: Session, hostname: str, os_name: str) -> MonitoringSession:
    session = MonitoringSession(hostname=hostname, os_name=os_name, status="ACTIVE")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_session(db: Session, session_id: int) -> None:
    session = db.get(MonitoringSession, session_id)
    if session and session.status == "ACTIVE":
        session.status = "CLOSED"
        session.ended_at = now_ist()
        db.commit()


def list_sessions(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(MonitoringSession).order_by(desc(MonitoringSession.started_at)).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "started_at": r.started_at.isoformat(),
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "hostname": r.hostname,
            "os_name": r.os_name,
            "status": r.status,
        }
        for r in rows
    ]


def save_snapshot(db: Session, snapshot: SystemSnapshot, session_id: int | None = None) -> MetricSnapshotRecord:
    record = MetricSnapshotRecord(
        session_id=session_id,
        timestamp=snapshot.timestamp,
        cpu_percent=snapshot.cpu.usage_percent,
        memory_percent=snapshot.memory.usage_percent,
        available_memory_gb=snapshot.memory.available_gb,
        disk_percent=snapshot.disk.usage_percent,
        free_disk_gb=snapshot.disk.free_gb,
        total_processes=snapshot.processes.total_running,
        raw_json=snapshot.model_dump_json(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def save_anomaly(db: Session, anomaly: DetectedAnomaly, session_id: int | None = None) -> AnomalyRecord:
    record = AnomalyRecord(
        session_id=session_id,
        timestamp=anomaly.timestamp,
        category=anomaly.category.value,
        severity=anomaly.severity.value,
        metric_name=anomaly.metric_name,
        current_value=anomaly.current_value,
        threshold_value=anomaly.threshold_value,
        message=anomaly.message,
        process_pid=anomaly.process_pid,
        process_name=anomaly.process_name,
        is_protected_process=anomaly.is_protected_process,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def serialize_anomaly(record: AnomalyRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "session_id": record.session_id,
        "timestamp": record.timestamp.isoformat(),
        "category": record.category,
        "severity": record.severity,
        "metric_name": record.metric_name,
        "current_value": record.current_value,
        "threshold_value": record.threshold_value,
        "message": record.message,
        "process_pid": record.process_pid,
        "process_name": record.process_name,
        "is_protected_process": record.is_protected_process,
    }


def list_anomalies(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AnomalyRecord).order_by(desc(AnomalyRecord.timestamp)).limit(limit)
    ).all()
    return [serialize_anomaly(r) for r in rows]


def save_investigation_result(
    db: Session,
    *,
    trigger_summary: str,
    report: InvestigationReport,
    anomaly_id: int | None = None,
) -> tuple[IncidentRecord, InvestigationReportRecord, RemediationActionRecord]:
    incident = IncidentRecord(
        anomaly_id=anomaly_id,
        trigger_summary=trigger_summary,
        severity=report.severity,
        status="INVESTIGATED",
    )
    db.add(incident)
    db.flush()

    report_record = InvestigationReportRecord(
        incident_id=incident.id,
        summary=report.summary,
        severity=report.severity,
        confirmed_observations_json=json.dumps(report.confirmed_observations),
        suspected_causes_json=json.dumps(report.suspected_causes),
        tools_used_json=json.dumps(report.tools_used),
    )
    db.add(report_record)
    db.flush()

    proposal = report.recommended_remediation
    initial_status = (
        "NO_ACTION"
        if proposal.action_type == RemediationActionType.NONE
        else RemediationStatus.PENDING.value
    )
    remediation_record = RemediationActionRecord(
        incident_id=incident.id,
        report_id=report_record.id,
        action_type=proposal.action_type.value,
        target_pid=proposal.target_pid,
        target_name=proposal.target_name,
        rationale=proposal.rationale,
        risk_level=proposal.risk_level.value,
        status=initial_status,
    )
    db.add(remediation_record)
    db.commit()
    db.refresh(incident)
    db.refresh(report_record)
    db.refresh(remediation_record)
    return incident, report_record, remediation_record


def serialize_report(record: InvestigationReportRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "incident_id": record.incident_id,
        "created_at": record.created_at.isoformat(),
        "summary": record.summary,
        "severity": record.severity,
        "confirmed_observations": json.loads(record.confirmed_observations_json),
        "suspected_causes": json.loads(record.suspected_causes_json),
        "tools_used": json.loads(record.tools_used_json),
    }


def serialize_remediation(record: RemediationActionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "incident_id": record.incident_id,
        "report_id": record.report_id,
        "created_at": record.created_at.isoformat(),
        "action_type": record.action_type,
        "target_pid": record.target_pid,
        "target_name": record.target_name,
        "rationale": record.rationale,
        "risk_level": record.risk_level,
        "status": record.status,
        "approved_by_user": record.approved_by_user,
        "decision_at": record.decision_at.isoformat() if record.decision_at else None,
        "guard_allowed": record.guard_allowed,
        "guard_reason": record.guard_reason,
        "execution_message": record.execution_message,
        "verification_resolved": record.verification_resolved,
        "verification_summary": record.verification_summary,
        "metrics_delta": json.loads(record.metrics_delta_json) if record.metrics_delta_json else None,
        "executed_at": record.executed_at.isoformat() if record.executed_at else None,
    }


def apply_remediation_outcome(
    db: Session,
    record: RemediationActionRecord,
    outcome: RemediationOutcome,
) -> RemediationActionRecord:
    record.status = outcome.status.value
    record.approved_by_user = outcome.approved_by_user
    record.decision_at = now_ist()
    record.guard_allowed = outcome.guard_check.allowed
    record.guard_reason = outcome.guard_check.reason
    record.executed_at = outcome.executed_at

    if outcome.execution:
        record.execution_message = outcome.execution.message
    if outcome.verification:
        record.verification_resolved = outcome.verification.resolved
        record.verification_summary = outcome.verification.summary
        record.metrics_delta_json = outcome.verification.metrics.model_dump_json()

    incident = db.get(IncidentRecord, record.incident_id)
    if incident:
        if outcome.status == RemediationStatus.VERIFIED_RESOLVED:
            incident.status = "RESOLVED"
        elif outcome.status == RemediationStatus.REJECTED:
            incident.status = "REJECTED"

    db.commit()
    db.refresh(record)
    return record


def list_pending_remediations(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(RemediationActionRecord)
        .where(RemediationActionRecord.status == RemediationStatus.PENDING.value)
        .order_by(desc(RemediationActionRecord.created_at))
    ).all()
    return [serialize_remediation(r) for r in rows]


def list_reports(db: Session, limit: int = 30) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(InvestigationReportRecord)
        .order_by(desc(InvestigationReportRecord.created_at))
        .limit(limit)
    ).all()
    return [serialize_report(r) for r in rows]


def list_incidents(db: Session, limit: int = 30) -> list[dict[str, Any]]:
    incidents = db.scalars(
        select(IncidentRecord).order_by(desc(IncidentRecord.created_at)).limit(limit)
    ).all()
    results: list[dict[str, Any]] = []
    for inc in incidents:
        results.append(
            {
                "id": inc.id,
                "anomaly_id": inc.anomaly_id,
                "created_at": inc.created_at.isoformat(),
                "trigger_summary": inc.trigger_summary,
                "severity": inc.severity,
                "status": inc.status,
                "reports": [serialize_report(r) for r in inc.reports],
                "remediations": [serialize_remediation(rem) for rem in inc.remediations],
            }
        )
    return results


def get_recent_incidents_for_agent(limit: int = 5) -> list[dict[str, Any]]:
    """Thread-safe incident provider injected into SentinelAgent's get_previous_incidents() tool."""
    db = database.SessionLocal()
    try:
        incidents = db.scalars(
            select(IncidentRecord).order_by(desc(IncidentRecord.created_at)).limit(limit)
        ).all()
        return [
            {
                "incident_id": inc.id,
                "created_at": inc.created_at.isoformat(),
                "severity": inc.severity,
                "status": inc.status,
                "trigger": inc.trigger_summary,
                "summary": inc.reports[0].summary if inc.reports else None,
            }
            for inc in incidents
        ]
    finally:
        db.close()