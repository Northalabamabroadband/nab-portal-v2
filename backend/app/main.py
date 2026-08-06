import asyncio

from app.core.audit_middleware import AuditMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.core.database import Base, SessionLocal, database_ready, engine
from app.core.redis_client import redis_ready
from app.core.settings import get_settings
from app.modules.auth.service import bootstrap_identity
from app.modules.desktop.router import router as desktop_router
from app.modules.mikrotik.collector import collector
from app.modules.mikrotik.fanout import fanout

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(AuditMiddleware)

app.include_router(api_router)
app.include_router(desktop_router)


@app.on_event("startup")
async def startup() -> None:
    def initialize_database() -> None:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as session:
            bootstrap_identity(session)

    await asyncio.to_thread(initialize_database)
    fanout.start()
    if settings.mikrotik_collector_enabled:
        collector.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await collector.stop()
    await fanout.stop()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/ready")
def ready() -> dict[str, object]:
    database = database_ready()
    redis = redis_ready()
    return {
        "ready": database and redis,
        "database": database,
        "redis": redis,
    }
