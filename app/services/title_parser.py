"""Parse GitHub issue titles into structured goal data.

Title format: "<unit> - <period> - <goal text>"
Split on " - " (space-dash-space), max 2 splits.

Examples:
  "Acme Corp - 2026 - Become market leader"  → goal (yearly)
  "Engineering - 2026Q1 - Reduce technical debt" → goal (quarterly)
  "Team Alpha" → structural entity (no period)
"""

import re
from dataclasses import dataclass


@dataclass
class ParsedTitle:
    """Result of parsing a GitHub issue title."""

    unit_name: str
    period: str | None  # "2026" or "2026Q1" or None
    period_type: str | None  # "yearly" or "quarterly" or None
    goal_text: str | None  # The goal description, or None for entities
    is_goal: bool  # True if this has a period (it's a goal, not just an entity)


# Match yearly period: exactly 4 digits (e.g. "2026")
_YEARLY_PATTERN = re.compile(r"^\d{4}$")

# Match quarterly period: 4 digits + Q + 1-4 (e.g. "2026Q1", case-insensitive)
_QUARTERLY_PATTERN = re.compile(r"^(\d{4})[Qq]([1-4])$")


def parse_period(period_str: str) -> tuple[str | None, str | None]:
    """Parse a period string and return (normalized_period, period_type).

    Returns (None, None) if the period format is invalid.

    Args:
        period_str: Raw period string like "2026", "2026Q1", "2026q2"

    Returns:
        Tuple of (period, period_type) where period is normalized
        (e.g. "2026Q1" uppercase) and period_type is "yearly" or "quarterly".
    """
    period_str = period_str.strip()

    if _YEARLY_PATTERN.match(period_str):
        return period_str, "yearly"

    match = _QUARTERLY_PATTERN.match(period_str)
    if match:
        year, quarter = match.groups()
        return f"{year}Q{quarter}", "quarterly"

    return None, None


def parse_title(title: str) -> ParsedTitle:
    """Parse a GitHub issue title into its components.

    Split on " - " (space-dash-space) with max 2 splits.
    Goal text can contain dashes.

    Args:
        title: Raw GitHub issue title

    Returns:
        ParsedTitle with parsed components
    """
    parts = title.strip().split(" - ", maxsplit=2)

    # Single part: structural entity only (e.g. "Team Alpha")
    if len(parts) == 1:
        return ParsedTitle(
            unit_name=parts[0].strip(),
            period=None,
            period_type=None,
            goal_text=None,
            is_goal=False,
        )

    unit_name = parts[0].strip()

    # Two parts: could be "<unit> - <period>" (entity with period but no goal text)
    # or "<unit> - <something>" where something isn't a valid period
    if len(parts) == 2:
        period, period_type = parse_period(parts[1])
        if period is not None:
            # Valid period but no goal text — treat as structural entity
            return ParsedTitle(
                unit_name=unit_name,
                period=period,
                period_type=period_type,
                goal_text=None,
                is_goal=False,
            )
        # Not a valid period — treat entire thing as entity name
        return ParsedTitle(
            unit_name=title.strip(),
            period=None,
            period_type=None,
            goal_text=None,
            is_goal=False,
        )

    # Three parts: "<unit> - <period> - <goal text>"
    period, period_type = parse_period(parts[1])
    if period is None:
        # Invalid period format — treat entire title as entity name
        return ParsedTitle(
            unit_name=title.strip(),
            period=None,
            period_type=None,
            goal_text=None,
            is_goal=False,
        )

    return ParsedTitle(
        unit_name=unit_name,
        period=period,
        period_type=period_type,
        goal_text=parts[2].strip(),
        is_goal=True,
    )
