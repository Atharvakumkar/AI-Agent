from datetime import datetime
from app.time_utils import now_ist

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base



class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_ist)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hostname: Mapped[str] = mapped_column(String(128))
    os_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")

    snapshots: Mapped[list["MetricSnapshotRecord"]] = relationship(back_populates="session")
    anomalies: Mapped[list["AnomalyRecord"]] = relationship(back_populates="session")


class MetricSnapshotRecord(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("monitoring_sessions.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_ist)
    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    available_memory_gb: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    free_disk_gb: Mapped[float] = mapped_column(Float)
    total_processes: Mapped[int] = mapped_column(Integer)
    raw_json: Mapped[str] = mapped_column(Text)

    session: Mapped[MonitoringSession | None] = relationship(back_populates="snapshots")


class AnomalyRecord(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("monitoring_sessions.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_ist)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    metric_name: Mapped[str] = mapped_column(String(64))
    current_value: Mapped[float] = mapped_column(Float)
    threshold_value: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    process_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_protected_process: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    session: Mapped[MonitoringSession | None] = relationship(back_populates="anomalies")


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int | None] = mapped_column(ForeignKey("anomalies.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_ist)
    trigger_summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="INVESTIGATED")

    reports: Mapped[list["InvestigationReportRecord"]] = relationship(back_populates="incident")
    remediations: Mapped[list["RemediationActionRecord"]] = relationship(back_populates="incident")


class InvestigationReportRecord(Base):
    __tablename__ = "investigation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_ist)
    summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16))
    confirmed_observations_json: Mapped[str] = mapped_column(Text)
    suspected_causes_json: Mapped[str] = mapped_column(Text)
    tools_used_json: Mapped[str] = mapped_column(Text)

    incident: Mapped[IncidentRecord] = relationship(back_populates="reports")


class RemediationActionRecord(Base):
    __tablename__ = "remediation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"))
    report_id: Mapped[int] = mapped_column(ForeignKey("investigation_reports.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_ist)

    action_type: Mapped[str] = mapped_column(String(64))
    target_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(16))

    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    approved_by_user: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    guard_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    guard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_delta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped[IncidentRecord] = relationship(back_populates="remediations")