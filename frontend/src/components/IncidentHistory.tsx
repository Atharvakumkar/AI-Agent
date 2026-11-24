import type { IncidentItem } from "../types/sentinel";

interface IncidentHistoryProps {
  incidents: IncidentItem[];
  onRefresh: () => void;
}

export function IncidentHistory({ incidents, onRefresh }: IncidentHistoryProps) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Incident &amp; Remediation Audit History</h3>
          <p className="card-subtitle">
            Persisted SQLite records of investigations, approvals, and post-action verification
          </p>
        </div>
        <button type="button" className="btn" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {incidents.length === 0 ? (
        <div className="empty-state">
          No incidents recorded yet. Run an AI investigation to create the first audit record.
        </div>
      ) : (
        <div>
          {incidents.map((inc) => {
            const report = inc.reports[0];
            const rem = inc.remediations[0];

            return (
              <div key={inc.id} className="incident-item">
                <div className="card-header" style={{ marginBottom: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <strong>Incident #{inc.id}</strong>
                    <span
                      className={`badge ${
                        inc.severity === "CRITICAL"
                          ? "badge-crit"
                          : inc.severity === "WARNING"
                          ? "badge-warn"
                          : "badge-info"
                      }`}
                    >
                      {inc.severity}
                    </span>
                    <span
                      className={`badge ${
                        inc.status === "RESOLVED" ? "badge-ok" : "badge-neutral"
                      }`}
                    >
                      {inc.status}
                    </span>
                  </div>
                  <span style={{ fontSize: "0.78rem", color: "#6b7280" }}>
                    {new Date(inc.created_at).toLocaleString()}
                  </span>
                </div>

                <p style={{ margin: "0 0 8px", fontSize: "0.84rem", color: "#4b5563" }}>
                  <strong>Trigger:</strong> {inc.trigger_summary}
                </p>

                {report && (
                  <p style={{ margin: "0 0 10px", fontSize: "0.88rem", lineHeight: 1.5 }}>
                    {report.summary}
                  </p>
                )}

                {rem && (
                  <div
                    style={{
                      paddingTop: "10px",
                      borderTop: "1px solid #f3f4f6",
                      fontSize: "0.83rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "4px",
                    }}
                  >
                    <div>
                      <strong>Remediation:</strong> <code>{rem.action_type}</code>
                      {rem.target_name ? ` (${rem.target_name}${rem.target_pid ? ` · PID ${rem.target_pid}` : ""})` : ""}
                      {" · "}
                      Status: <strong>{rem.status}</strong>
                    </div>
                    {rem.guard_reason && (
                      <div style={{ color: "#4b5563" }}>
                        <strong>Safety Guard:</strong> {rem.guard_reason}
                      </div>
                    )}
                    {rem.verification_summary && (
                      <div style={{ color: "#15803d" }}>
                        <strong>Verification:</strong> {rem.verification_summary}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}