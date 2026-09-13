"""Private data-control and encryption interfaces for Customer Evidence Intake v1.

NOT DEPLOYED. This module does not open a network socket and does not provide a
bundled production cipher. Production callers must inject a reviewed encryption
provider; plaintext/no-op protection is intentionally unavailable here.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol

from storage import EvidenceStore


class PayloadProtector(Protocol):
    """Production encryption boundary.

    Implementations must provide authenticated encryption and key management
    appropriate to the deployment. JakeAI v1 deliberately does not roll its own
    cryptography.
    """

    key_id: str

    def seal(self, plaintext: bytes, *, context: bytes) -> bytes: ...
    def open(self, ciphertext: bytes, *, context: bytes) -> bytes: ...


@dataclass(frozen=True)
class DeletionCredential:
    submission_id: str
    deletion_token: str


class DeletionAuthority:
    """Issue and verify one-time deletion credentials without storing plaintext tokens."""

    def __init__(self) -> None:
        self._token_hashes: dict[str, str] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, submission_id: str) -> DeletionCredential:
        if not submission_id:
            raise ValueError("submission_id is required")
        token = secrets.token_urlsafe(32)
        self._token_hashes[submission_id] = self._digest(token)
        return DeletionCredential(submission_id=submission_id, deletion_token=token)

    def revoke(self, submission_id: str) -> None:
        self._token_hashes.pop(submission_id, None)

    def verify(self, submission_id: str, deletion_token: str) -> bool:
        expected = self._token_hashes.get(submission_id)
        if not expected or not deletion_token:
            return False
        supplied = self._digest(deletion_token)
        return hmac.compare_digest(expected, supplied)


@dataclass(frozen=True)
class DeletionResult:
    status: str
    message: str


class DataControlService:
    """Authenticated customer deletion for raw evidence and recurrence contribution."""

    def __init__(self, store: EvidenceStore, authority: DeletionAuthority):
        self.store = store
        self.authority = authority

    def delete(self, *, submission_id: str, deletion_token: str) -> DeletionResult:
        if not self.authority.verify(submission_id, deletion_token):
            return DeletionResult("AUTH_REJECTED", "Deletion authorization was not accepted.")

        deleted = self.store.delete_submission(submission_id)
        # Token is one-time regardless of whether the row already disappeared by retention.
        self.authority.revoke(submission_id)
        if deleted:
            return DeletionResult("DELETED", "Stored evidence and its recurrence contribution were removed.")
        return DeletionResult("ALREADY_GONE", "No stored contribution remains for this submission.")


def require_production_protector(protector: PayloadProtector | None) -> PayloadProtector:
    """Fail closed unless deployment injects an explicit encryption provider."""
    if protector is None:
        raise RuntimeError("production evidence storage requires an encryption provider")
    key_id = getattr(protector, "key_id", "")
    if not isinstance(key_id, str) or not key_id.strip():
        raise RuntimeError("encryption provider must expose a non-empty key_id")
    if not callable(getattr(protector, "seal", None)) or not callable(getattr(protector, "open", None)):
        raise RuntimeError("invalid encryption provider")
    return protector
