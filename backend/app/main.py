from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import api_v1_router
from app.config import settings
from app.db.base import Base
from app.db.migrations import run_startup_migrations
from app.db.session import SessionLocal, engine
from app.services.benchmark_service import BenchmarkService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 1. Create tables & enable SQLite foreign keys
    Base.metadata.create_all(bind=engine)
    # ponytail: inline SQLite migrations; upgrade to Alembic when schema churn
    # grows beyond a handful of columns.
    run_startup_migrations(engine)
    with SessionLocal() as db:
        if settings.DATABASE_URL.startswith("sqlite"):
            db.execute(text("PRAGMA foreign_keys=ON;"))
        # 2. Seed catalogs from configs/
        BenchmarkService.seed_catalogs(db)
        # 3. Reconcile stale runs per ARCHITECTURE §6.4 & clear GPU lock
        BenchmarkService.reconcile_stale_runs(db)
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title="Rapier Bench API",
        description="Domain-aware AI model benchmarking platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(api_v1_router)

    return app

app = create_app()
