import { useCallback, useEffect, useRef, useState } from "react";
import { WS_METRICS_URL } from "./api";
import type {
  AnomalyItem,
  ChartPoint,
  MetricsStreamMessage,
  SystemSnapshot,
} from "../types/sentinel";
import { formatIstTime } from "./time";

export type ConnectionStatus = "connecting" | "connected" | "paused" | "error";

const MAX_HISTORY_POINTS = 40;

function formatTimeLabel(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function useMetricsStream(onNewAnomalies?: (items: AnomalyItem[]) => void) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<SystemSnapshot | null>(null);
  const [history, setHistory] = useState<ChartPoint[]>([]);
  const [isMonitoring, setIsMonitoring] = useState<boolean>(true);

  const wsRef = useRef<WebSocket | null>(null);
  const onNewAnomaliesRef = useRef(onNewAnomalies);
  onNewAnomaliesRef.current = onNewAnomalies;

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!isMonitoring) {
      disconnect();
      setStatus("paused");
      setSessionId(null);
      return;
    }

    let cancelled = false;
    let reconnectTimer: number | undefined;

    const connect = () => {
      if (cancelled) return;
      setStatus("connecting");

      const ws = new WebSocket(WS_METRICS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) setStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as MetricsStreamMessage;
          if (msg.type !== "metrics_update") return;

          setSessionId(msg.session_id);
          setSnapshot(msg.snapshot);

          const point: ChartPoint = {
            time: formatIstTime(msg.snapshot.timestamp),
            cpu: msg.snapshot.cpu.usage_percent,
            memory: msg.snapshot.memory.usage_percent,
            disk: msg.snapshot.disk.usage_percent,
          };

          setHistory((prev) => [...prev.slice(-(MAX_HISTORY_POINTS - 1)), point]);

          if (msg.anomalies.length > 0 && onNewAnomaliesRef.current) {
            onNewAnomaliesRef.current(msg.anomalies);
          }
        } catch {
          // Ignore malformed frames
        }
      };

      ws.onerror = () => {
        if (!cancelled) setStatus("error");
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!cancelled && isMonitoring) {
          setStatus("connecting");
          reconnectTimer = window.setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      disconnect();
    };
  }, [isMonitoring, disconnect]);

  const toggleMonitoring = useCallback(() => {
    setIsMonitoring((prev) => !prev);
  }, []);

  return {
    status,
    sessionId,
    snapshot,
    history,
    isMonitoring,
    toggleMonitoring,
  };
}