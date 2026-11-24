import type {
  AnomalyItem,
  IncidentItem,
  InvestigationReportItem,
  RemediationItem,
  SystemSnapshot,
  ThresholdConfig,
} from "../types/sentinel";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const WS_METRICS_URL =
  import.meta.env.VITE_WS_METRICS_URL ?? "ws://127.0.0.1:8000/ws/metrics";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export const api = {
  getSnapshot: (topN = 10) =>
    request<SystemSnapshot>(`/api/metrics/snapshot?top_n=${topN}`),

  getThresholds: () => request<ThresholdConfig>("/api/metrics/thresholds"),

  updateThresholds: (payload: ThresholdConfig) =>
    request<ThresholdConfig>("/api/metrics/thresholds", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  getAlerts: (limit = 50) => request<AnomalyItem[]>(`/api/alerts?limit=${limit}`),

  getReports: (limit = 30) =>
    request<InvestigationReportItem[]>(`/api/agent/reports?limit=${limit}`),

  getIncidents: (limit = 30) =>
    request<IncidentItem[]>(`/api/incidents?limit=${limit}`),

  getPendingRemediations: () =>
    request<RemediationItem[]>("/api/remediation/pending"),

  runInvestigation: (payload: { anomaly_id?: number; prompt?: string }) =>
    request<{
      incident_id: number;
      status: string;
      report: InvestigationReportItem;
      remediation: RemediationItem;
    }>("/api/agent/investigate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  decideRemediation: (remediationId: number, approved: boolean) =>
    request<RemediationItem>(`/api/remediation/${remediationId}/decide`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),
};