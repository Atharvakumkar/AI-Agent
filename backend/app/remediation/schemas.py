from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from app.agent.schemas import RemediationActionType


class RemediationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    VERIFIED_RESOLVED = "VERIFIED_RESOLVED"
    EXECUTED_UNRESOLVED = "EXECUTED_UNRESOLVED"
    FAILED = "FAILED"


class GuardCheckResult(BaseModel):
    allowed: bool
    reason: str


class ActionExecutionResult(BaseModel):
    executed: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class MetricDelta(BaseModel):
    cpu_before: float
    cpu_after: float
    memory_before: float
    memory_after: float
    disk_before: float
    disk_after: float


class VerificationResult(BaseModel):
    resolved: bool
    summary: str
    metrics: MetricDelta


class RemediationOutcome(BaseModel):
    action_type: RemediationActionType
    target_pid: int | None = None
    target_name: str | None = None
    status: RemediationStatus
    approved_by_user: bool
    guard_check: GuardCheckResult
    execution: ActionExecutionResult | None = None
    verification: VerificationResult | None = None
    executed_at: datetime