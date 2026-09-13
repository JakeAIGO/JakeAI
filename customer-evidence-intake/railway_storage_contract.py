"""Unreleased storage/deletion contract for Railway Customer Evidence Intake v1.

No database connection is opened here and no Railway resource is created. The
module defines the minimum production contract for an isolated PostgreSQL store
and a durable deletion-token authority. Public intake remains disabled until a
real implementation satisfies this contract and the release gate is approved.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class RailwayEvidenceStorageContract:
    database_url: str
    encryption_key_id: str
    deletion_pepper_id: str

    def validate(self) -> None:
        parsed = urlparse(self.database_url)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("evidence store must be PostgreSQL")
        if not parsed.hostname:
            raise ValueError("evidence store hostname is required")
        if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("production evidence store may not use localhost")
        if not parsed.path or parsed.path == "/":
            raise ValueError("dedicated evidence database name is required")
        if not self.encryption_key_id.strip():
            raise ValueError("encryption key id is required")
        if not self.deletion_pepper_id.strip():
            raise ValueError("deletion-token pepper id is required")


POSTGRES_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS intake_evidence (
    submission_id TEXT PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    encryption_key_id TEXT NOT NULL,
    ciphertext BYTEA NOT NULL,
    recurrence_signature TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intake_recurrence (
    recurrence_signature TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count >= 1)
);

CREATE TABLE IF NOT EXISTS intake_recurrence_contributions (
    submission_id TEXT PRIMARY KEY,
    recurrence_signature TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intake_deletion_credentials (
    submission_id TEXT PRIMARY KEY,
    token_digest TEXT NOT NULL,
    pepper_id TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NULL
);
""".strip()


@dataclass(frozen=True)
class DeletionCredentialRecord:
    submission_id: str
    token_digest: str
    pepper_id: str
    issued_at: str
    consumed_at: str | None = None


class DurableDeletionRepository(Protocol):
    """Persistence boundary; implementations must use the isolated store."""

    def put(self, record: DeletionCredentialRecord) -> None: ...
    def get(self, submission_id: str) -> DeletionCredentialRecord | None: ...
    def mark_consumed(self, submission_id: str, consumed_at: str) -> bool: ...


class DeletionTokenDigester:
    """HMAC deletion-token digests using a deploy-time secret pepper.

    The pepper value itself must come from the deployment secret store and must
    never be persisted alongside the digest. Only its non-secret identifier is
    stored for rotation bookkeeping.
    """

    def __init__(self, *, pepper: bytes, pepper_id: str):
        if len(pepper) < 32:
            raise ValueError("deletion-token pepper must be at least 32 bytes")
        if not pepper_id.strip():
            raise ValueError("pepper_id is required")
        self._pepper = pepper
        self.pepper_id = pepper_id

    def digest(self, token: str) -> str:
        if not token:
            raise ValueError("deletion token is required")
        return hmac.new(self._pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, token: str, expected_digest: str) -> bool:
        if not token or not expected_digest:
            return False
        return hmac.compare_digest(self.digest(token), expected_digest)

    def record(self, *, submission_id: str, token: str, issued_at: datetime | None = None) -> DeletionCredentialRecord:
        if not submission_id:
            raise ValueError("submission_id is required")
        now = issued_at or datetime.now(timezone.utc)
        return DeletionCredentialRecord(
            submission_id=submission_id,
            token_digest=self.digest(token),
            pepper_id=self.pepper_id,
            issued_at=now.isoformat(),
        )


def assert_deletion_record_usable(record: DeletionCredentialRecord | None, *, pepper_id: str) -> DeletionCredentialRecord:
    """Fail closed on missing, consumed, or wrong-pepper deletion records."""
    if record is None:
        raise PermissionError("deletion credential not found")
    if record.consumed_at is not None:
        raise PermissionError("deletion credential already consumed")
    if record.pepper_id != pepper_id:
        raise PermissionError("deletion credential pepper version mismatch")
    return record
