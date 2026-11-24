import { useState } from "react";
import type { RemediationItem } from "../types/sentinel";

interface RemediationModalProps {
  pendingItems: RemediationItem[];
  latestOutcome: RemediationItem | null;
  onDecide: (remediationId: number, approved: boolean) => Promise<void>;
  onDismissOutcome: () => void;
}

export function RemediationModal({
  pendingItems,
  latestOutcome,
  onDecide,
  onDismissOutcome,
}: RemediationModalProps) {
  const [submittingId, setSubmittingId] = useState<number | null>(null);

  const handleDecision = async (id: number, approved: boolean) => {
    setSubmittingId(id);
    try {
      await onDecide(id, approved);
    } finally {
      setSubmittingId(null);
    }
  };

  if (pendingItems.length === 0 && !latestOutcome) {
    return null;
  }

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {latestOutcome && (
        <div className="card">
          <div className="card-header" style={{ marginBottom: "8px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span
                className={`badge ${
                  latestOutcome.status === "VERIFIED_RESOLVED"
                    ? "badge-ok"
                    : latestOutcome.status === "REJECTED"
                    ? "badge-neutral"
                    : "badge-crit"
                }`}
              >
                {latestOutcome.status}
              </span>
              <strong>
                Remediation Outcome · {latestOutcome.action_type}
              </strong>
            </div>
            <button type="button" className="btn" onClick={onDismissOutcome}>
              Dismiss
            </button>
          </div>

          <p style={{ margin: "0 0 6px", fontSize: "0.88rem" }}>
            {latestOutcome.verification_summary ||
              latestOutcome.execution_message ||
              latestOutcome.guard_reason}
          </p>

          {latestOutcome.metrics_delta && (
            <div className="delta-strip">
              <span>
                CPU: {latestOutcome.metrics_delta.cpu_before.toFixed(1)}% &rarr;{" "}
                <strong>{latestOutcome.metrics_delta.cpu_after.toFixed(1)}%</strong>
              </span>
              <span>
                Memory: {latestOutcome.metrics_delta.memory_before.toFixed(1)}% &rarr;{" "}
                <strong>{latestOutcome.metrics_delta.memory_after.toFixed(1)}%</strong>
              </span>
              <span>
                Disk: {latestOutcome.metrics_delta.disk_before.toFixed(1)}% &rarr;{" "}
                <strong>{latestOutcome.metrics_delta.disk_after.toFixed(1)}%</strong>
              </span>
            </div>
          )}
        </div>
      )}

      {pendingItems.map((item) => {
        const busy = submittingId === item.id;
        return (
          <div key={item.id} className="remediation-card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div>
                <h3 className="card-title">
                  Remediation Approval Required · Incident #{item.incident_id}
                </h3>
                <p className="card-subtitle">
                  Explicit human authorization is required before SentinelAI executes any system change
                </p>
              </div>
              <span
                className={`badge ${
                  item.risk_level === "HIGH"
                    ? "badge-crit"
                    : item.risk_level === "MEDIUM"
                    ? "badge-warn"
                    : "badge-info"
                }`}
              >
                Risk: {item.risk_level}
              </span>
            </div>

            <div className="remediation-meta">
              <div>
                <span>Allowlisted Action</span>
                <strong>{item.action_type}</strong>
              </div>
              {item.target_name && (
                <div>
                  <span>Target Name</span>
                  <strong>{item.target_name}</strong>
                </div>
              )}
              {item.target_pid !== null && (
                <div>
                  <span>Target PID</span>
                  <strong>{item.target_pid}</strong>
                </div>
              )}
            </div>

            <p style={{ margin: 0, fontSize: "0.88rem", lineHeight: 1.5 }}>
              <strong>Rationale:</strong> {item.rationale}
            </p>

            <div className="action-row">
              <button
                type="button"
                className="btn btn-danger"
                disabled={busy}
                onClick={() => handleDecision(item.id, true)}
              >
                {busy ? "Executing & Verifying..." : "Approve & Execute"}
              </button>
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => handleDecision(item.id, false)}
              >
                Reject Action
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}