"""Private end-to-end service boundary for Customer Evidence Intake v1.

No HTTP server, no public endpoint, no external network, no production actions.
This composes screening + bounded persistence and returns minimal public-safe status.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from intake import screen_submission
from storage import EvidenceStore


@dataclass(frozen=True)
class ServiceResponse:
    status: str
    message: str
    submission_id: str | None = None
    recurrence_count: int | None = None


class CustomerEvidenceService:
    def __init__(self, store: EvidenceStore):
        self.store = store

    def submit(self, raw: dict[str, Any]) -> ServiceResponse:
        screened = screen_submission(raw)

        # Never echo rejected input or suspected secret/sensitive material.
        if screened.status != "ACCEPTED" or not screened.packet:
            public_message = {
                "BLOCKED_SECRET_DETECTED": "Remove credentials or secrets and resubmit.",
                "BLOCKED_SENSITIVE_DATA": "Remove sensitive identifiers/payment data and resubmit.",
                "HUMAN_REVIEW": "This submission requires human review and will not be processed autonomously.",
                "REJECTED_INPUT": "The submission could not be accepted. Check required fields and limits.",
            }.get(screened.status, "The submission could not be accepted.")
            return ServiceResponse(screened.status, public_message)

        packet = screened.packet
        self.store.save_accepted_packet(packet)
        count = self.store.recurrence_count(packet["recurrence_signature"])
        return ServiceResponse(
            "ACCEPTED",
            "Evidence received for Product Factory evaluation; this is not a promise of automation or a product.",
            submission_id=packet["submission_id"],
            recurrence_count=count,
        )

    def purge(self, *, now: datetime | None = None) -> int:
        return self.store.purge_expired_raw(now=now)

    def public_submit_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        return asdict(self.submit(raw))
