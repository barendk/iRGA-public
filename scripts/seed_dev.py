"""Seed the database with sample demo data.

Imports sample_goals.tsv and configures entity levels so the app is
immediately usable after a fresh install.  Safe to run multiple times
(idempotent: skips seeding if fully-configured entities already exist).

Usage
-----
Local development (with venv active):
    python scripts/seed_dev.py

Inside the running Docker container:
    docker-compose exec app python scripts/seed_dev.py

Via docker-compose on first start (automatic):
    SEED_DATA=1 docker-compose up
"""

import sys
from pathlib import Path

# Allow running as a script from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.database import Base
from app.models.entity import StructuralEntity
from app.models.goal import Goal
from app.services.import_service import import_goals_from_tsv

SAMPLE_TSV = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_goals.tsv"


def seed() -> None:
    """Seed the DB with sample data and configure entity levels."""
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        existing = db.query(StructuralEntity).all()

        # Already fully seeded: all entities have a level set.
        if existing and all(e.level is not None for e in existing):
            count = len(existing)
            goal_count = db.query(Goal).count()
            print(f"Database already seeded ({count} entities, {goal_count} goals). Skipping.")
            return

        # Partially seeded (entities without levels): clean up and re-seed.
        if existing:
            print("Removing partially-seeded data...")
            db.query(Goal).delete()
            db.query(StructuralEntity).delete()
            db.flush()

        if not SAMPLE_TSV.exists():
            print(f"ERROR: Sample TSV not found at {SAMPLE_TSV}", file=sys.stderr)
            sys.exit(1)

        print(f"Importing goals from {SAMPLE_TSV}...")
        import_goals_from_tsv(db, SAMPLE_TSV)

        # Configure entity levels based on name.
        engineering = (
            db.query(StructuralEntity).filter(StructuralEntity.name == "Engineering").first()
        )
        # Entity names below are coupled to sample_goals.tsv — update both if names change.
        for entity in db.query(StructuralEntity).all():
            if entity.name == "Acme Corp":
                entity.level = "org"
            elif entity.name == "Engineering":
                entity.level = "domain"
            else:
                entity.level = "team"
                if engineering:
                    entity.parent_id = engineering.id

        db.commit()

        entity_count = db.query(StructuralEntity).count()
        goal_count = db.query(Goal).count()
        print(f"Done. Seeded {entity_count} entities and {goal_count} goals.")

    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    seed()
