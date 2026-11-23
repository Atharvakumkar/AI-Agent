from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, model_validator

from app.config import get_settings


class Severity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AnomalyCategory(str, Enum):
    CPU = "CPU"
    MEMORY = "MEMORY"
    DISK = "DISK"
    PROCESS_CPU = "PROCESS_CPU"
    PROCESS_MEMORY = "PROCESS_MEMORY"


class ThresholdConfig(BaseModel):
    cpu_warning: float = Field(default=75.0, ge=1.0, le=99.0)
    cpu_critical: float = Field(default=90.0, ge=2.0, le=100.0)

    memory_warning: float = Field(default=80.0, ge=1.0, le=99.0)
    memory_critical: float = Field(default=92.0, ge=2.0, le=100.0)

    disk_warning: float = Field(default=80.0, ge=1.0, le=99.0)
    disk_critical: float = Field(default=90.0, ge=2.0, le=100.0)

    process_cpu_warning: float = Field(default=40.0, ge=1.0, le=99.0)
    process_cpu_critical: float = Field(default=70.0, ge=2.0, le=100.0)

    process_memory_warning: float = Field(default=25.0, ge=1.0, le=99.0)
    process_memory_critical: float = Field(default=50.0, ge=2.0, le=100.0)

    cooldown_seconds: int = Field(default=120, ge=0, le=3600)

    @model_validator(mode="after")
    def validate_warning_below_critical(self) -> "ThresholdConfig":
        pairs = [
            ("cpu_warning", "cpu_critical"),
            ("memory_warning", "memory_critical"),
            ("disk_warning", "disk_critical"),
            ("process_cpu_warning", "process_cpu_critical"),
            ("process_memory_warning", "process_memory_critical"),
        ]
        for warn_field, crit_field in pairs:
            if getattr(self, warn_field) >= getattr(self, crit_field):
                raise ValueError(f"{warn_field} must be strictly less than {crit_field}")
        return self

    @classmethod
    def from_settings(cls) -> "ThresholdConfig":
        s = get_settings()
        return cls(
            cpu_warning=s.cpu_warning_threshold,
            cpu_critical=s.cpu_critical_threshold,
            memory_warning=s.memory_warning_threshold,
            memory_critical=s.memory_critical_threshold,
            disk_warning=s.disk_warning_threshold,
            disk_critical=s.disk_critical_threshold,
            cooldown_seconds=s.alert_cooldown_seconds,
        )


class DetectedAnomaly(BaseModel):
    timestamp: datetime
    category: AnomalyCategory
    severity: Severity
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    process_pid: int | None = None
    process_name: str | None = None
    is_protected_process: bool | None = None