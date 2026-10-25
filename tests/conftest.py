import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.services.benchmark_service import BenchmarkService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def temp_db_path() -> Generator[str]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def db_session(temp_db_path: str) -> Generator[Session]:
    engine = create_engine(
        f"sqlite:///{temp_db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    # Seed catalog configs
    configs_dir = Path(__file__).resolve().parent.parent / "configs"
    BenchmarkService.seed_catalogs(session, configs_dir=configs_dir)

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    def override_get_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
