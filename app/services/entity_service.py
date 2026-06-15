"""Entity service — manage structural entity levels and team-domain assignments.

Business rules:
  - Exactly one entity may have level 'org' at a time.
  - Teams must be assigned to a domain (parent_id → domain entity).
  - Domain names are queried from the database, never hardcoded.
"""

from sqlalchemy.orm import Session

from app.models.entity import StructuralEntity


def get_all_entities(db: Session) -> list[StructuralEntity]:
    """Return all structural entities ordered by name."""
    return db.query(StructuralEntity).order_by(StructuralEntity.name).all()


def get_entities_by_level(db: Session, level: str) -> list[StructuralEntity]:
    """Return entities filtered by level (org, domain, team)."""
    return (
        db.query(StructuralEntity)
        .filter(StructuralEntity.level == level)
        .order_by(StructuralEntity.name)
        .all()
    )


def update_entity_levels(db: Session, level_updates: dict[int, str]) -> list[str]:
    """Update entity levels from a dict of {entity_id: new_level}.

    Enforces the single-org constraint: at most one entity can be 'org'.

    Args:
        db: Database session
        level_updates: Mapping of entity_id → new level ('org', 'domain', 'team')

    Returns:
        List of validation error messages (empty if all OK).
    """
    errors: list[str] = []
    valid_levels = {"org", "domain", "team"}

    # Validate all levels first
    for entity_id, level in level_updates.items():
        if level not in valid_levels:
            errors.append(
                f"Ongeldig niveau '{level}' voor entiteit {entity_id}. Kies uit: org, domain, team."
            )

    if errors:
        return errors

    # Check single-org constraint
    org_count = sum(1 for level in level_updates.values() if level == "org")
    if org_count > 1:
        errors.append("Er kan slechts één Organisatie niveau zijn.")
        return errors

    # Apply updates
    for entity_id, level in level_updates.items():
        entity = db.get(StructuralEntity, entity_id)
        if entity is None:
            errors.append(f"Entiteit met id {entity_id} niet gevonden.")
            continue
        entity.level = level

    if not errors:
        db.flush()

    return errors


def update_team_assignments(db: Session, assignments: dict[int, int | None]) -> list[str]:
    """Update team-to-domain parent assignments.

    Args:
        db: Database session
        assignments: Mapping of team_entity_id → domain_entity_id (or None)

    Returns:
        List of validation error messages (empty if all OK).
    """
    errors: list[str] = []

    for team_id, domain_id in assignments.items():
        team = db.get(StructuralEntity, team_id)
        if team is None:
            errors.append(f"Team met id {team_id} niet gevonden.")
            continue

        if domain_id is not None:
            domain = db.get(StructuralEntity, domain_id)
            if domain is None:
                errors.append(f"Domein met id {domain_id} niet gevonden.")
                continue
            if domain.level != "domain":
                errors.append(
                    f"Entiteit '{domain.name}' is geen domein (huidig niveau: {domain.level})."
                )
                continue

        team.parent_id = domain_id

    if not errors:
        db.flush()

    return errors
