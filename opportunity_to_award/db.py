from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class PersistenceNotConfigured(RuntimeError):
    """Raised when persistent storage is requested without an approved DB configuration."""


def database_url() -> Optional[str]:
    value = os.environ.get("OPPORTUNITY_TO_AWARD_DATABASE_URL", "").strip()
    return value or None


def persistence_enabled() -> bool:
    return os.environ.get("OPPORTUNITY_TO_AWARD_PERSISTENCE_ENABLED", "false").strip().lower() == "true"


@contextmanager
def connect() -> Iterator[object]:
    """Open a PostgreSQL connection only when persistence has been explicitly enabled.

    The driver import is intentionally lazy so the staged module remains inert unless
    the persistence gate is deliberately activated.
    """
    if not persistence_enabled():
        raise PersistenceNotConfigured(
            "Opportunity-to-Award persistence is disabled pending explicit human approval."
        )
    url = database_url()
    if not url:
        raise PersistenceNotConfigured(
            "OPPORTUNITY_TO_AWARD_DATABASE_URL is required when persistence is enabled."
        )

    import psycopg

    conn = psycopg.connect(url)
    try:
        yield conn
    finally:
        conn.close()


def initialize_schema() -> None:
    """Create Phase 1 tables in the explicitly configured PostgreSQL database."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
