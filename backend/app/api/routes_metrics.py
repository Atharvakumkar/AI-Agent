from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.anomalies.rules import ThresholdConfig
from app.api.deps import detector, monitor
from app.db import repository
from app.db.database import get_db

router = APIRouter(prefix="/api", tags=["Metrics & Sessions"])


@router.get("/metrics/snapshot")
def get_live_snapshot(top_n: int = 10) -> dict:
    safe_top_n = max(1, min(top_n, 25))
    snapshot = monitor.collect_snapshot(top_n=safe_top_n)
    return snapshot.model_dump(mode="json")


@router.get("/metrics/thresholds", response_model=ThresholdConfig)
def get_thresholds() -> ThresholdConfig:
    return detector.thresholds


@router.put("/metrics/thresholds", response_model=ThresholdConfig)
def update_thresholds(payload: ThresholdConfig) -> ThresholdConfig:
    detector.update_thresholds(payload)
    detector.reset_cooldowns()
    return detector.thresholds


@router.get("/sessions")
def get_sessions(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    return repository.list_sessions(db, limit=max(1, min(limit, 100)))