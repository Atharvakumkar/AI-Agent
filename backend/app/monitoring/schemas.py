from datetime import datetime
from pydantic import BaseModel, Field


class CpuMetrics(BaseModel):
    usage_percent: float = Field(..., ge=0.0, le=100.0)
    per_core_percent: list[float]
    logical_cores: int
    physical_cores: int | None
    frequency_mhz: float | None = None


class MemoryMetrics(BaseModel):
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float = Field(..., ge=0.0, le=100.0)
    swap_total_gb: float
    swap_used_gb: float
    swap_percent: float = Field(..., ge=0.0, le=100.0)


class DiskPartitionMetrics(BaseModel):
    device: str
    mountpoint: str
    fstype: str
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float = Field(..., ge=0.0, le=100.0)


class DiskMetrics(BaseModel):
    primary_mount: str
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float = Field(..., ge=0.0, le=100.0)
    partitions: list[DiskPartitionMetrics]


class ProcessSummary(BaseModel):
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    username: str | None = None
    is_protected: bool = False


class ProcessDetail(ProcessSummary):
    cmdline: list[str] = Field(default_factory=list)
    exe: str | None = None
    parent_pid: int | None = None
    create_time: datetime | None = None
    num_threads: int | None = None


class ProcessOverview(BaseModel):
    total_running: int
    top_cpu: list[ProcessSummary]
    top_memory: list[ProcessSummary]


class SystemInfo(BaseModel):
    hostname: str
    os_name: str
    os_release: str
    os_version: str
    architecture: str
    processor: str
    boot_time: datetime
    uptime_seconds: int
    uptime_human: str


class SystemSnapshot(BaseModel):
    timestamp: datetime
    system_info: SystemInfo
    cpu: CpuMetrics
    memory: MemoryMetrics
    disk: DiskMetrics
    processes: ProcessOverview