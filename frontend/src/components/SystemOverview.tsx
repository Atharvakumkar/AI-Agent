import type { SystemSnapshot } from "../types/sentinel";

interface SystemOverviewProps {
  snapshot: SystemSnapshot;
}

export function SystemOverview({ snapshot }: SystemOverviewProps) {
  const { cpu, memory, disk, processes, system_info } = snapshot;

  return (
    <section>
      <div className="kpi-grid">
        <div className="card">
          <div className="kpi-label">CPU Utilisation</div>
          <div className="kpi-value">{cpu.usage_percent.toFixed(1)}%</div>
          <div className="kpi-meta">
            {cpu.logical_cores} logical cores
            {cpu.frequency_mhz ? ` · ${cpu.frequency_mhz} MHz` : ""}
          </div>
        </div>

        <div className="card">
          <div className="kpi-label">Memory Utilisation</div>
          <div className="kpi-value">{memory.usage_percent.toFixed(1)}%</div>
          <div className="kpi-meta">
            {memory.used_gb.toFixed(2)} / {memory.total_gb.toFixed(2)} GB ({memory.available_gb.toFixed(2)} GB free)
          </div>
        </div>

        <div className="card">
          <div className="kpi-label">Disk ({disk.primary_mount})</div>
          <div className="kpi-value">{disk.usage_percent.toFixed(1)}%</div>
          <div className="kpi-meta">
            {disk.used_gb.toFixed(1)} / {disk.total_gb.toFixed(1)} GB ({disk.free_gb.toFixed(1)} GB free)
          </div>
        </div>

        <div className="card">
          <div className="kpi-label">Active Processes</div>
          <div className="kpi-value">{processes.total_running}</div>
          <div className="kpi-meta">Uptime: {system_info.uptime_human}</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: "16px" }}>
        <div className="card-title">Host Environment</div>
        <div className="meta-strip">
          <div>
            <span>Hostname</span>
            <strong>{system_info.hostname}</strong>
          </div>
          <div>
            <span>Operating System</span>
            <strong>
              {system_info.os_name} {system_info.os_release}
            </strong>
          </div>
          <div>
            <span>Architecture</span>
            <strong>{system_info.architecture}</strong>
          </div>
          <div>
            <span>Swap Memory</span>
            <strong>
              {memory.swap_used_gb.toFixed(2)} / {memory.swap_total_gb.toFixed(2)} GB ({memory.swap_percent}%)
            </strong>
          </div>
        </div>
      </div>
    </section>
  );
}