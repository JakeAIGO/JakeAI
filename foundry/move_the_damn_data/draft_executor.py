"""Draft-only provider execution boundary for Move the Damn Data™.

This module permits creation of a provider-side draft object while making sending
structurally unavailable. It is suitable for a private pilot where Google credentials
live in a separately reviewed adapter. No provider SDK is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Any


class DraftProvider(Protocol):
    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str) -> str:
        """Create a draft and return a provider reference. Must not send it."""


@dataclass(frozen=True)
class DraftExecutionResult:
    status: str
    event_id: str
    provider_reference: str | None = None
    reason: str | None = None


class DraftOnlyExecutor:
    """Execute only a pre-approved draft-creation request; sending is impossible here."""

    def __init__(self, provider: DraftProvider) -> None:
        self.provider = provider
        self._executed: dict[str, str] = {}

    def execute(self, *, event_id: str, request: Mapping[str, Any]) -> DraftExecutionResult:
        if not event_id:
            return DraftExecutionResult("blocked", event_id, reason="missing event identity")
        if event_id in self._executed:
            return DraftExecutionResult(
                "duplicate",
                event_id,
                provider_reference=self._executed[event_id],
                reason="draft already created; no second provider call performed",
            )
        if request.get("operation") != "gmail.create_draft":
            return DraftExecutionResult("blocked", event_id, reason="operation is not draft creation")
        if request.get("send") is not False:
            return DraftExecutionResult("blocked", event_id, reason="send must be explicitly false")
        if request.get("human_approval_required_before_send") is not True:
            return DraftExecutionResult("blocked", event_id, reason="human send approval invariant missing")

        to = request.get("to")
        subject = request.get("subject")
        body = request.get("body")
        if not all(isinstance(v, str) and v.strip() for v in (to, subject, body)):
            return DraftExecutionResult("human_review", event_id, reason="draft fields are incomplete")

        reference = self.provider.create_draft(
            to=to.strip(),
            subject=subject.strip(),
            body=body,
            idempotency_key=event_id,
        )
        if not isinstance(reference, str) or not reference.strip():
            return DraftExecutionResult("quarantine", event_id, reason="provider returned no draft reference")
        self._executed[event_id] = reference.strip()
        return DraftExecutionResult("draft_created", event_id, provider_reference=reference.strip())
