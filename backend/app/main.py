import platform
from contextlib import asynccontextmanager
from app.time_utils import now_ist
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_agent import router as agent_router
from app.api.routes_alerts import router as alerts_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_remediation import router as remediation_router
from app.api.ws_metrics import router as ws_router, session_manager
from app.config import get_settings
from app.db.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    await session_manager.stop_session()


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="AI-powered local server health monitoring and controlled remediation agent.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(alerts_router)
app.include_router(agent_router)
app.include_router(remediation_router)
app.include_router(ws_router)


@app.get("/health", tags=["System"])
def health_check() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "os": platform.system(),
        "os_release": platform.release(),
        "timestamp": now_ist().isoformat(),
    }