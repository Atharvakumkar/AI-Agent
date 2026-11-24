import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import detector, monitor
from app.config import get_settings
from app.db import database, repository

router = APIRouter(tags=["WebSocket"])


class MonitoringSessionManager:
    """Runs live metric polling only while at least one dashboard WebSocket is connected."""

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self.current_session_id: int | None = None
        self._poll_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

        if self._poll_task is None or self._poll_task.done():
            sys_info = await asyncio.to_thread(monitor.get_system_information)
            db = database.SessionLocal()
            try:
                session = repository.create_session(db, sys_info.hostname, sys_info.os_name)
                self.current_session_id = session.id
            finally:
                db.close()

            self._poll_task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

        if not self.active_connections:
            await self.stop_session()

    async def stop_session(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None

        if self.current_session_id is not None:
            session_id = self.current_session_id
            self.current_session_id = None
            db = database.SessionLocal()
            try:
                repository.close_session(db, session_id)
            finally:
                db.close()

    async def _poll_loop(self) -> None:
        interval = get_settings().poll_interval_seconds
        while self.active_connections:
            snapshot = await asyncio.to_thread(monitor.collect_snapshot, 10)
            anomalies = detector.evaluate(snapshot)

            saved_anomalies: list[dict] = []
            db = database.SessionLocal()
            try:
                repository.save_snapshot(db, snapshot, session_id=self.current_session_id)
                for anomaly in anomalies:
                    row = repository.save_anomaly(db, anomaly, session_id=self.current_session_id)
                    saved_anomalies.append(repository.serialize_anomaly(row))
            finally:
                db.close()

            payload = {
                "type": "metrics_update",
                "session_id": self.current_session_id,
                "snapshot": snapshot.model_dump(mode="json"),
                "anomalies": saved_anomalies,
            }

            stale: list[WebSocket] = []
            for ws in list(self.active_connections):
                try:
                    await ws.send_json(payload)
                except Exception:
                    stale.append(ws)

            for ws in stale:
                self.active_connections.discard(ws)

            await asyncio.sleep(interval)


session_manager = MonitoringSessionManager()


@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket) -> None:
    await session_manager.connect(websocket)
    try:
        while True:
            # Keep connection open; ignore client keepalive pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await session_manager.disconnect(websocket)
    except Exception:
        await session_manager.disconnect(websocket)