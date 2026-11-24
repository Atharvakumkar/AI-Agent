import { useState } from "react";
import type { InvestigationReportItem } from "../types/sentinel";

interface InvestigationReportProps {
  reports: InvestigationReportItem[];
  isInvestigating: boolean;
  onRunPromptInvestigation: (prompt: string) => Promise<void>;
}

const DEFAULT_PROMPT =
  "Check current CPU, memory, and disk health, inspect the highest-consuming process in detail, and recommend safe remediation if needed.";

export function InvestigationReport({
  reports,
  isInvestigating,
  onRunPromptInvestigation,
}: InvestigationReportProps) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const activeReport = reports[selectedIndex] ?? reports[0] ?? null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isInvestigating) return;
    setSelectedIndex(0);
    await onRunPromptInvestigation(prompt.trim());
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">AI Agent Investigation</h3>
          <p className="card-subtitle">
            Multi-step LangGraph diagnostics separating confirmed facts from suspected causes
          </p>
        </div>
        {reports.length > 1 && (
          <select
            aria-label="Select investigation report"
            className="number-input"
            value={selectedIndex}
            onChange={(e) => setSelectedIndex(Number(e.target.value))}
          >
            {reports.map((rep, idx) => (
              <option key={rep.id} value={idx}>
                Incident #{rep.incident_id} · {new Date(rep.created_at).toLocaleTimeString()}
              </option>
            ))}
          </select>
        )}
      </div>

      <form onSubmit={handleSubmit} className="prompt-bar">
        <input
          type="text"
          className="text-input"
          placeholder="Ask SentinelAI to investigate system health..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isInvestigating}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={isInvestigating || !prompt.trim()}
        >
          {isInvestigating ? "Investigating..." : "Run Investigation"}
        </button>
      </form>

      {!activeReport ? (
        <div className="empty-state">
          No investigation reports yet. Click <strong>Run Investigation</strong> above or{" "}
          <strong>Investigate</strong> on any anomaly.
        </div>
      ) : (
        <div>
          <div className="card-header" style={{ marginBottom: "8px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span
                className={`badge ${
                  activeReport.severity === "CRITICAL"
                    ? "badge-crit"
                    : activeReport.severity === "WARNING"
                    ? "badge-warn"
                    : "badge-info"
                }`}
              >
                {activeReport.severity}
              </span>
              <strong>Incident #{activeReport.incident_id}</strong>
            </div>
            <span style={{ fontSize: "0.78rem", color: "#6b7280" }}>
              {new Date(activeReport.created_at).toLocaleString()}
            </span>
          </div>

          <p style={{ margin: "0 0 12px", fontSize: "0.92rem", lineHeight: 1.55 }}>
            {activeReport.summary}
          </p>

          <div className="report-grid">
            <div className="report-box">
              <h4>Confirmed Observations (Tool Evidence)</h4>
              <ul>
                {activeReport.confirmed_observations.map((obs, idx) => (
                  <li key={idx}>{obs}</li>
                ))}
              </ul>
            </div>

            <div className="report-box">
              <h4>Suspected Causes (Hypotheses)</h4>
              <ul>
                {activeReport.suspected_causes.map((cause, idx) => (
                  <li key={idx}>{cause}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="tool-chips">
            <span style={{ fontSize: "0.76rem", color: "#6b7280", alignSelf: "center" }}>
              Tools Invoked:
            </span>
            {activeReport.tools_used.length > 0 ? (
              activeReport.tools_used.map((toolName, idx) => (
                <span key={`${toolName}-${idx}`} className="tool-chip">
                  {toolName}()
                </span>
              ))
            ) : (
              <span className="tool-chip">none</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}