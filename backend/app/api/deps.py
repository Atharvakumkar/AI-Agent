from app.agent.graph import SentinelAgent
from app.anomalies.detector import AnomalyDetector
from app.db.repository import get_recent_incidents_for_agent
from app.monitoring.collector import SystemMonitor
from app.remediation.registry import RemediationEngine

monitor = SystemMonitor()
detector = AnomalyDetector()
remediation_engine = RemediationEngine(monitor)
sentinel_agent = SentinelAgent(
    monitor=monitor,
    incident_provider=get_recent_incidents_for_agent,
)