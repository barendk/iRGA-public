"""Application configuration loaded from environment variables."""

import os

# Database connection URL
# Docker internal: postgresql://postgres:postgres@db:5432/goalreview
# Local dev:       postgresql://postgres:postgres@localhost:5433/goalreview
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/goalreview",
)

# Secret key for session signing (not used in MVP, placeholder for Phase 1)
APP_SECRET_KEY: str = os.environ.get("APP_SECRET_KEY", "dev-secret-key")

# Organisation branding (configurable for white-label deployments)
ORG_NAME: str = os.environ.get("ORG_NAME", "My Organisation")
ORG_TAGLINE: str = os.environ.get("ORG_TAGLINE", "")
ORG_HEADER: str = os.environ.get("ORG_HEADER", "")
