import type { ChartPoint, DiskPartitionMetrics } from "../types/sentinel";

interface ResourceChartsProps {
  history: ChartPoint[];
  partitions: DiskPartitionMetrics[];
}

interface MetricChartCardProps {
  title: string;
  subtitle: string;
  dataKey: "cpu" | "memory" | "disk";
  stroke: string;
  fill: string;
  history: ChartPoint[];
}

function MetricChartCard({
  title,
  subtitle,
  dataKey,
  stroke,
  fill,
  history,
}: MetricChartCardProps) {
  const width = 600;
  const height = 220;
  const left = 42;
  const right = 10;
  const top = 12;
  const bottom = 28;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const points = history.map((point, index) => {
    const rawValue = Number(point[dataKey]);
    const value = Number.isFinite(rawValue) ? Math.max(0, Math.min(100, rawValue)) : 0;
    const x = left + (history.length > 1 ? (index / (history.length - 1)) * plotWidth : plotWidth / 2);
    const y = top + ((100 - value) / 100) * plotHeight;
    return { x, y, value, time: point.time };
  });
  const linePoints = points.map(({ x, y }) => `${x},${y}`).join(" ");
  const areaPath = points.length
    ? `M ${points[0].x} ${top + plotHeight} L ${points.map(({ x, y }) => `${x} ${y}`).join(" L ")} L ${points[points.length - 1].x} ${top + plotHeight} Z`
    : "";

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">{title}</h3>
          <p className="card-subtitle">{subtitle}</p>
        </div>
      </div>
      <div className="chart-box">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${title} over time`}
          style={{ width: "100%", height: "100%" }}
        >
          {[0, 25, 50, 75, 100].map((value) => {
            const y = top + ((100 - value) / 100) * plotHeight;
            return (
              <g key={value}>
                <line x1={left} x2={width - right} y1={y} y2={y} stroke="#e5e7eb" strokeDasharray="3 3" />
                <text x={left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#6b7280">{value}%</text>
              </g>
            );
          })}
          {areaPath && <path d={areaPath} fill={fill} />}
          {points.length > 1 && <polyline points={linePoints} fill="none" stroke={stroke} strokeWidth="2" />}
          {points.map((point, index) => (
            <circle key={`${point.time}-${index}`} cx={point.x} cy={point.y} r="3" fill={stroke}>
              <title>{`${point.time}: ${point.value.toFixed(1)}%`}</title>
            </circle>
          ))}
          {[0, Math.floor((history.length - 1) / 2), history.length - 1]
            .filter((index, position, indexes) => index >= 0 && indexes.indexOf(index) === position)
            .map((index) => {
              const x = left + (history.length > 1 ? (index / (history.length - 1)) * plotWidth : plotWidth / 2);
              return (
                <text key={`time-${index}`} x={x} y={height - 6} textAnchor="middle" fontSize="11" fill="#6b7280">
                  {history[index]?.time}
                </text>
              );
            })}
        </svg>
      </div>
    </div>
  );
}

export function ResourceCharts({ history, partitions }: ResourceChartsProps) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div className="charts-grid">
        <MetricChartCard
          title="CPU Utilisation"
          subtitle="Live sliding window (0–100%)"
          dataKey="cpu"
          stroke="#c8102e"
          fill="rgba(200, 16, 46, 0.1)"
          history={history}
        />
        <MetricChartCard
          title="Memory Utilisation"
          subtitle="Physical RAM percentage"
          dataKey="memory"
          stroke="#1f2937"
          fill="rgba(31, 41, 55, 0.1)"
          history={history}
        />
        <MetricChartCard
          title="Primary Disk Utilisation"
          subtitle="Primary OS mount percentage"
          dataKey="disk"
          stroke="#4b5563"
          fill="rgba(75, 85, 99, 0.1)"
          history={history}
        />
      </div>

      {partitions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Mounted Disk Partitions</h3>
              <p className="card-subtitle">Cross-platform filtered storage volumes</p>
            </div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Mount</th>
                <th>Device</th>
                <th>Filesystem</th>
                <th>Used</th>
                <th>Free</th>
                <th>Total</th>
                <th>Usage</th>
              </tr>
            </thead>
            <tbody>
              {partitions.map((part) => (
                <tr key={`${part.device}-${part.mountpoint}`}>
                  <td><strong>{part.mountpoint}</strong></td>
                  <td>{part.device}</td>
                  <td>{part.fstype}</td>
                  <td>{part.used_gb.toFixed(1)} GB</td>
                  <td>{part.free_gb.toFixed(1)} GB</td>
                  <td>{part.total_gb.toFixed(1)} GB</td>
                  <td>{part.usage_percent.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}