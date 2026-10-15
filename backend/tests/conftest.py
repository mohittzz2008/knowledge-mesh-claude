"""Shared pytest fixtures.

Tests run against whatever DATABASE_URL points at (environment or backend/.env),
so they keep using your PostgreSQL. Only when NO database is configured at all
do they fall back to a throw-away SQLite file, with the schema built from the ORM
metadata - handy for CI and offline runs, no Alembic or Postgres required.
"""

import os
from pathlib import Path

import pytest


def _database_configured() -> bool:
    if os.environ.get("DATABASE_URL"):
        return True
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return True
    return False


if not _database_configured():
    os.environ["DATABASE_URL"] = "sqlite:///./.pytest_km.db"


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    from app.database import engine
    from app.models.base import Base
    import app.models  # noqa: F401  (register every model on Base.metadata)

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def db_session():
    """A real SQLAlchemy session; uncommitted work is rolled back on teardown."""
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: hits real third-party APIs; skipped unless RUN_LIVE_TESTS=1"
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="live network test (set RUN_LIVE_TESTS=1 to run)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
