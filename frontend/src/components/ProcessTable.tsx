import { useState } from "react";
import type { ProcessOverview } from "../types/sentinel";

interface ProcessTableProps {
  processes: ProcessOverview;
}

export function ProcessTable({ processes }: ProcessTableProps) {
  const [sortBy, setSortBy] = useState<"cpu" | "memory">("cpu");
  const rows = sortBy === "cpu" ? processes.top_cpu : processes.top_memory;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Process Monitor</h3>
          <p className="card-subtitle">
            Showing top {rows.length} of {processes.total_running} running processes
          </p>
        </div>
        <div className="segmented">
          <button
            type="button"
            className={sortBy === "cpu" ? "active" : ""}
            onClick={() => setSortBy("cpu")}
          >
            Top CPU
          </button>
          <button
            type="button"
            className={sortBy === "memory" ? "active" : ""}
            onClick={() => setSortBy("memory")}
          >
            Top Memory
          </button>
        </div>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>PID</th>
            <th>Process Name</th>
            <th>Status</th>
            <th>CPU %</th>
            <th>Memory %</th>
            <th>Memory (MB)</th>
            <th>Safety Class</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((proc) => (
            <tr key={proc.pid}>
              <td>{proc.pid}</td>
              <td><strong>{proc.name}</strong></td>
              <td>{proc.status}</td>
              <td>{proc.cpu_percent.toFixed(1)}%</td>
              <td>{proc.memory_percent.toFixed(2)}%</td>
              <td>{proc.memory_mb.toFixed(1)} MB</td>
              <td>
                <span className={`badge ${proc.is_protected ? "badge-protected" : "badge-user"}`}>
                  {proc.is_protected ? "Protected OS" : "Standard"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}