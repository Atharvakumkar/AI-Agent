import { useCallback, useEffect, useState } from "react";
import { AlertsPanel } from "./components/AlertsPanel";
import { IncidentHistory } from "./components/IncidentHistory";
import { InvestigationReport } from "./components/InvestigationReport";
import { ProcessTable } from "./components/ProcessTable";
import { RemediationModal } from "./components/RemediationModal";
import { ResourceCharts } from "./components/ResourceCharts";
import { SystemOverview } from "./components/SystemOverview";
import { api } from "./services/api";
import { useMetricsStream } from "./services/useMetricsStream";
import "./styles/dashboard.css";
import type {
  AnomalyItem,
  IncidentItem,
  InvestigationReportItem,
  RemediationItem,
} from "./types/sentinel";

type TabId = "overview" | "processes" | "agent" | "history";

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [alerts, setAlerts] = useState<AnomalyItem[]>([]);
  const [reports, setReports] = useState<InvestigationReportItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [pendingRemediations, setPendingRemediations] = useState<RemediationItem[]>([]);
  const [latestOutcome, setLatestOutcome] = useState<RemediationItem | null>(null);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const refreshAuditData = useCallback(async () => {
    try {
      const [fetchedAlerts, fetchedReports, fetchedIncidents, fetchedPending] =
        await Promise.all([
          api.getAlerts(50),
          api.getReports(30),
          api.getIncidents(30),
          api.getPendingRemediations(),
        ]);
      setAlerts(fetchedAlerts);
      setReports(fetchedReports);
      setIncidents(fetchedIncidents);
      setPendingRemediations(fetchedPending);
    } catch {
      // Backend may still be starting up; WebSocket reconnects automatically
    }
  }, []);

  useEffect(() => {
    refreshAuditData();
  }, [refreshAuditData]);

  const handleNewAnomalies = useCallback((incoming: AnomalyItem[]) => {
    setAlerts((prev) => {
      const existingIds = new Set(prev.map((a) => a.id));
      const fresh = incoming.filter((a) => !existingIds.has(a.id));
      return [...fresh, ...prev].slice(0, 100);
    });
  }, []);

  const { status, sessionId, snapshot, history, isMonitoring, toggleMonitoring } =
    useMetricsStream(handleNewAnomalies);

  const handleInvestigateAnomaly = async (anomalyId: number) => {
    setIsInvestigating(true);
    setErrorBanner(null);
    try {
      await api.runInvestigation({ anomaly_id: anomalyId });
      await refreshAuditData();
      setActiveTab("agent");
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "AI investigation request failed."
      );
    } finally {
      setIsInvestigating(false);
    }
  };

  const handleRunPromptInvestigation = async (prompt: string) => {
    setIsInvestigating(true);
    setErrorBanner(null);
    try {
      await api.runInvestigation({ prompt });
      await refreshAuditData();
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "AI investigation request failed."
      );
    } finally {
      setIsInvestigating(false);
    }
  };

  const handleDecideRemediation = async (remediationId: number, approved: boolean) => {
    setErrorBanner(null);
    try {
      const outcome = await api.decideRemediation(remediationId, approved);
      setLatestOutcome(outcome);
      await refreshAuditData();
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to process remediation decision."
      );
    }
  };

  const statusLabel: Record<typeof status, string> = {
    connected: sessionId ? `Live · Session #${sessionId}` : "Live",
    connecting: "Connecting...",
    paused: "Session Stopped",
    error: "Connection Error",
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-group">
          <h1 className="brand-title">SentinelAI</h1>
          <span className="brand-sub">Local Server Health &amp; Remediation Agent</span>
        </div>

        <div className="topbar-controls">
          <div className="status-pill">
            <span className={`status-dot ${status}`} />
            <span>{statusLabel[status]}</span>
          </div>
          <button
            type="button"
            className={`btn ${isMonitoring ? "" : "btn-primary"}`}
            onClick={toggleMonitoring}
          >
            {isMonitoring ? "Stop Session" : "Start Session"}
          </button>
        </div>
      </header>

      <nav className="nav-tabs">
        <button
          type="button"
          className={`nav-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview &amp; Charts
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === "processes" ? "active" : ""}`}
          onClick={() => setActiveTab("processes")}
        >
          Processes
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === "agent" ? "active" : ""}`}
          onClick={() => setActiveTab("agent")}
        >
          Alerts &amp; AI Agent
          {(pendingRemediations.length > 0 || alerts.length > 0) && (
            <span className="tab-badge">
              {pendingRemediations.length > 0
                ? pendingRemediations.length
                : alerts.length}
            </span>
          )}
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === "history" ? "active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          Incident History
        </button>
      </nav>

      <main className="main-content">
        {errorBanner && (
          <div className="alert-banner">
            <span>{errorBanner}</span>
            <button
              type="button"
              className="btn"
              onClick={() => setErrorBanner(null)}
            >
              Close
            </button>
          </div>
        )}

        <RemediationModal
          pendingItems={pendingRemediations}
          latestOutcome={latestOutcome}
          onDecide={handleDecideRemediation}
          onDismissOutcome={() => setLatestOutcome(null)}
        />

        {!snapshot ? (
          <div className="card empty-state">
            {isMonitoring
              ? "Waiting for live telemetry from FastAPI backend (ws://127.0.0.1:8000/ws/metrics)..."
              : "Monitoring session is stopped. Click 'Start Session' to resume live collection."}
          </div>
        ) : (
          <>
            {activeTab === "overview" && (
              <>
                <SystemOverview snapshot={snapshot} />
                <ResourceCharts
                  history={history}
                  partitions={snapshot.disk.partitions}
                />
              </>
            )}

            {activeTab === "processes" && (
              <ProcessTable processes={snapshot.processes} />
            )}

            {activeTab === "agent" && (
              <>
                <InvestigationReport
                  reports={reports}
                  isInvestigating={isInvestigating}
                  onRunPromptInvestigation={handleRunPromptInvestigation}
                />
                <AlertsPanel
                  alerts={alerts}
                  isInvestigating={isInvestigating}
                  onInvestigateAnomaly={handleInvestigateAnomaly}
                />
              </>
            )}

            {activeTab === "history" && (
              <IncidentHistory
                incidents={incidents}
                onRefresh={refreshAuditData}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}