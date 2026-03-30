"""Playwright UI test fixtures.

Starts a real uvicorn server on a free port, seeds demo data
from sample_goals.tsv, and provides a Playwright page fixture.
"""

import socket
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.database import Base


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: int = 15) -> bool:
    """Wait until the server is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.3)
    return False


@pytest.fixture(scope="session")
def ui_port() -> int:
    """Allocate a free port for the UI test server."""
    return _find_free_port()


@pytest.fixture(scope="session")
def _seed_test_data() -> None:
    """Seed the database with demo data for UI tests.

    Imports sample_goals.tsv and configures entity levels.
    Runs once per test session.
    """
    engine = create_engine(DATABASE_URL, echo=False)
    test_session = sessionmaker(bind=engine)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    db = test_session()
    try:
        from app.models.entity import StructuralEntity
        from app.models.goal import Goal
        from app.models.review import GoalConfidence, MonthlyReview, QuarterlyReview

        # Always clear review data so stale values from a previous test session
        # never leak into this one.  Without this, a review submitted in one run
        # (e.g. support_request=True) persists in the DB and causes pre-fill
        # state to bleed into unrelated tests on the next run.
        db.query(GoalConfidence).delete()
        db.query(MonthlyReview).delete()
        db.query(QuarterlyReview).delete()
        db.commit()

        # Only seed goals/entities if data is already complete (levels set).
        existing = db.query(StructuralEntity).all()
        if existing and all(e.level is not None for e in existing):
            return

        # Clean up partially-seeded data (e.g. entities without levels)
        if existing:
            db.query(Goal).delete()
            db.query(StructuralEntity).delete()
            db.flush()

        # Import from sample TSV (path anchored to this file so it works in CI)
        sample_path = Path(__file__).parent.parent / "fixtures" / "sample_goals.tsv"
        if sample_path.exists():
            from app.services.import_service import import_goals_from_tsv

            import_goals_from_tsv(db, sample_path)

        # Configure entity levels
        for entity in db.query(StructuralEntity).all():
            if entity.name == "Acme Corp":
                entity.level = "org"
            elif entity.name == "Engineering":
                entity.level = "domain"
            else:
                entity.level = "team"
                # Assign teams to Engineering domain
                engineering = (
                    db.query(StructuralEntity)
                    .filter(StructuralEntity.name == "Engineering")
                    .first()
                )
                if engineering:
                    entity.parent_id = engineering.id

        db.commit()
    finally:
        db.close()
        engine.dispose()


@pytest.fixture(scope="session")
def _live_server(ui_port: int, _seed_test_data: None):
    """Start a real uvicorn server for Playwright tests."""
    proc = subprocess.Popen(
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not _wait_for_server(ui_port):
        proc.kill()
        raise RuntimeError(f"Server failed to start on port {ui_port}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="session")
def base_url(ui_port: int, _live_server: None) -> str:
    """Return the base URL for the live test server."""
    return f"http://127.0.0.1:{ui_port}"


@pytest.fixture()
def ui_page(page: Page, base_url: str) -> Page:
    """Provide a Playwright page pointed at the live server."""
    page.set_default_timeout(10_000)
    return page
