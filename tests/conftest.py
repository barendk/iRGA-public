"""Shared test fixtures for the Goal Review test suite.

Provides a test database session and a FastAPI test client.
Uses savepoint-based transaction rollback to isolate each test,
with table cleanup to handle pre-existing data.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL
from app.database import Base, get_db
from app.main import app

# Use the same DB with savepoint-based isolation
test_engine = create_engine(DATABASE_URL, echo=False)
TestSession = sessionmaker(bind=test_engine)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Provide a database session with clean tables, rolled back after each test.

    Cleans all application tables within a transaction, so
    tests start with an empty database and changes are rolled back.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)

    # Clean all application tables within this transaction
    # Uses metadata to dynamically find all tables in FK-safe order
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client with the test DB session injected."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def seed_entities(db: Session) -> list:
    """Seed the test DB with sample structural entities."""
    from app.models.entity import StructuralEntity

    entities = [
        StructuralEntity(name="Acme Corp", level="org"),
        StructuralEntity(name="Engineering", level="domain"),
        StructuralEntity(name="Team Alpha", level="team"),
        StructuralEntity(name="Team Beta", level="team"),
        StructuralEntity(name="Team Gamma", level="team"),
    ]
    for e in entities:
        db.add(e)
    db.flush()

    # Set parent relationships
    engineering = entities[1]
    for team in entities[2:]:
        team.parent_id = engineering.id
    db.flush()

    return entities
