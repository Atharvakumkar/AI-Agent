import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { AnomalyItem, ThresholdConfig } from "../types/sentinel";

interface AlertsPanelProps {
  alerts: AnomalyItem[];
  isInvestigating: boolean;
  onInvestigateAnomaly: (anomalyId: number) => Promise<void>;
}

export function AlertsPanel({
  alerts,
  isInvestigating,
  onInvestigateAnomaly,
}: AlertsPanelProps) {
  const [showThresholds, setShowThresholds] = useState(false);
  const [thresholds, setThresholds] = useState<ThresholdConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getThresholds()
      .then(setThresholds)
      .catch((err: Error) => setError(err.message));
  }, []);

  const handleFieldChange = (field: keyof ThresholdConfig, raw: string) => {
    if (!thresholds) return;
    const parsed = Number(raw);
    if (Number.isNaN(parsed)) return;
    setThresholds({ ...thresholds, [field]: parsed });
  };

  const handleSaveThresholds = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!thresholds) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const updated = await api.updateThresholds(thresholds);
      setThresholds(updated);
      setFeedback("Thresholds updated and active cooldowns reset.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update thresholds.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Alerts &amp; Anomaly Detection</h3>
          <p className="card-subtitle">
            Threshold-based anomalies with deduplication cooldowns
          </p>
        </div>
        <button
          type="button"
          className="btn"
          onClick={() => setShowThresholds((prev) => !prev)}
        >
          {showThresholds ? "Hide Thresholds" : "Configure Thresholds"}
        </button>
      </div>

      {showThresholds && thresholds && (
        <form onSubmit={handleSaveThresholds} style={{ marginBottom: "20px" }}>
          <div className="threshold-grid">
            <div className="field-group">
              <label>CPU Warning (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.cpu_warning}
                onChange={(e) => handleFieldChange("cpu_warning", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>CPU Critical (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.cpu_critical}
                onChange={(e) => handleFieldChange("cpu_critical", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Memory Warning (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.memory_warning}
                onChange={(e) => handleFieldChange("memory_warning", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Memory Critical (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.memory_critical}
                onChange={(e) => handleFieldChange("memory_critical", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Disk Warning (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.disk_warning}
                onChange={(e) => handleFieldChange("disk_warning", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Disk Critical (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.disk_critical}
                onChange={(e) => handleFieldChange("disk_critical", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Process CPU Warn (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.process_cpu_warning}
                onChange={(e) => handleFieldChange("process_cpu_warning", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Process CPU Crit (%)</label>
              <input
                type="number"
                step="1"
                className="number-input"
                value={thresholds.process_cpu_critical}
                onChange={(e) => handleFieldChange("process_cpu_critical", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label>Cooldown (seconds)</label>
              <input
                type="number"
                step="5"
                className="number-input"
                value={thresholds.cooldown_seconds}
                onChange={(e) => handleFieldChange("cooldown_seconds", e.target.value)}
              />
            </div>
          </div>

          <div className="action-row" style={{ marginTop: "14px" }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Save Thresholds"}
            </button>
            {feedback && (
              <span style={{ fontSize: "0.82rem", color: "#15803d" }}>{feedback}</span>
            )}
            {error && (
              <span style={{ fontSize: "0.82rem", color: "#c8102e" }}>{error}</span>
            )}
          </div>
        </form>
      )}

      {alerts.length === 0 ? (
        <div className="empty-state">
          No anomalies detected yet. Lower a threshold or run{" "}
          <code>scripts/load_simulator.py</code> to test detection.
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Severity</th>
              <th>Category</th>
              <th>Details</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id}>
                <td>{new Date(alert.timestamp).toLocaleTimeString()}</td>
                <td>
                  <span
                    className={`badge ${
                      alert.severity === "CRITICAL" ? "badge-crit" : "badge-warn"
                    }`}
                  >
                    {alert.severity}
                  </span>
                </td>
                <td>{alert.category}</td>
                <td>{alert.message}</td>
                <td>
                  <button
                    type="button"
                    className="btn"
                    disabled={isInvestigating}
                    onClick={() => onInvestigateAnomaly(alert.id)}
                  >
                    {isInvestigating ? "Running..." : "Investigate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}