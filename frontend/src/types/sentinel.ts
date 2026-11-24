export interface CpuMetrics {
  usage_percent: number;
  per_core_percent: number[];
  logical_cores: number;
  physical_cores: number | null;
  frequency_mhz: number | null;
}

export interface MemoryMetrics {
  total_gb: number;
  used_gb: number;
  available_gb: number;
  usage_percent: number;
  swap_total_gb: number;
  swap_used_gb: number;
  swap_percent: number;
}

export interface DiskPartitionMetrics {
  device: string;
  mountpoint: string;
  fstype: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  usage_percent: number;
}

export interface DiskMetrics {
  primary_mount: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  usage_percent: number;
  partitions: DiskPartitionMetrics[];
}

export interface ProcessSummary {
  pid: number;
  name: string;
  status: string;
  cpu_percent: number;
  memory_percent: number;
  memory_mb: number;
  username: string | null;
  is_protected: boolean;
}

export interface ProcessOverview {
  total_running: number;
  top_cpu: ProcessSummary[];
  top_memory: ProcessSummary[];
}

export interface SystemInfo {
  hostname: string;
  os_name: string;
  os_release: string;
  os_version: string;
  architecture: string;
  processor: string;
  boot_time: string;
  uptime_seconds: number;
  uptime_human: string;
}

export interface SystemSnapshot {
  timestamp: string;
  system_info: SystemInfo;
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  processes: ProcessOverview;
}

export interface ThresholdConfig {
  cpu_warning: number;
  cpu_critical: number;
  memory_warning: number;
  memory_critical: number;
  disk_warning: number;
  disk_critical: number;
  process_cpu_warning: number;
  process_cpu_critical: number;
  process_memory_warning: number;
  process_memory_critical: number;
  cooldown_seconds: number;
}

export interface AnomalyItem {
  id: number;
  session_id: number | null;
  timestamp: string;
  category: string;
  severity: "WARNING" | "CRITICAL";
  metric_name: string;
  current_value: number;
  threshold_value: number;
  message: string;
  process_pid: number | null;
  process_name: string | null;
  is_protected_process: boolean | null;
}

export interface InvestigationReportItem {
  id: number;
  incident_id: number;
  created_at: string;
  summary: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  confirmed_observations: string[];
  suspected_causes: string[];
  tools_used: string[];
}

export interface MetricsDelta {
  cpu_before: number;
  cpu_after: number;
  memory_before: number;
  memory_after: number;
  disk_before: number;
  disk_after: number;
}

export interface RemediationItem {
  id: number;
  incident_id: number;
  report_id: number;
  created_at: string;
  action_type: string;
  target_pid: number | null;
  target_name: string | null;
  rationale: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  status: string;
  approved_by_user: boolean | null;
  decision_at: string | null;
  guard_allowed: boolean | null;
  guard_reason: string | null;
  execution_message: string | null;
  verification_resolved: boolean | null;
  verification_summary: string | null;
  metrics_delta: MetricsDelta | null;
  executed_at: string | null;
}

export interface IncidentItem {
  id: number;
  anomaly_id: number | null;
  created_at: string;
  trigger_summary: string;
  severity: string;
  status: string;
  reports: InvestigationReportItem[];
  remediations: RemediationItem[];
}

export interface MetricsStreamMessage {
  type: "metrics_update";
  session_id: number | null;
  snapshot: SystemSnapshot;
  anomalies: AnomalyItem[];
}

export interface ChartPoint {
  time: string;
  cpu: number;
  memory: number;
  disk: number;
}