from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class RemediationActionType(str, Enum):
    TERMINATE_PROCESS = "terminate_process"
    RESTART_MANAGED_SERVICE = "restart_managed_service"
    CLEAR_TEMP_DIRECTORY = "clear_temp_directory"
    NONE = "none"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RemediationProposal(BaseModel):
    action_type: RemediationActionType = Field(
        ...,
        description="Must be one of the allowlisted remediation actions, or 'none' if no action is safe/needed.",
    )
    target_pid: int | None = Field(
        default=None,
        description="Target process PID if action_type is terminate_process.",
    )
    target_name: str | None = Field(
        default=None,
        description="Exact process name or service name observed in tool output.",
    )
    rationale: str = Field(
        ...,
        description="Why this remediation is recommended (or why no action is recommended).",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Estimated operational risk of executing this remediation.",
    )


class InvestigationReport(BaseModel):
    summary: str = Field(
        ...,
        description="Concise 2-3 sentence executive summary of the investigation.",
    )
    severity: Literal["INFO", "WARNING", "CRITICAL"] = Field(
        ...,
        description="Overall assessed severity based on tool evidence.",
    )
    confirmed_observations: list[str] = Field(
        ...,
        min_length=1,
        description="Factual findings directly observed in tool outputs (exact metrics, PIDs, names).",
    )
    suspected_causes: list[str] = Field(
        ...,
        min_length=1,
        description="Probable root causes inferred from observations. Clearly marked as hypotheses, not certainties.",
    )
    recommended_remediation: RemediationProposal = Field(
        ...,
        description="Structured remediation recommendation using only allowlisted actions.",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Populated deterministically by the agent runner from executed tool calls.",
    )