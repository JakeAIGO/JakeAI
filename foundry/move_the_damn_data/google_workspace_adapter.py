"""Provider boundary for a future Google Sheets -> Gmail draft connector.

This module performs no network calls and contains no credentials. It normalizes a
Google-Sheets-like row into a validated lead and produces a Gmail-draft request object.
A deployment adapter may later execute the draft creation after separate connector review.
Sending remains outside this adapter and requires explicit human approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import ValidationError

from private_connector_service import LeadIntake, prepare_lead


@dataclass(frozen=True)
class AdapterResult:
    status: str
    event_id: str
    draft_request: Mapping[str, Any] | None = None
    reason: str | None = None


class GoogleWorkspaceAdapter:
    """Normalize a Sheets row and prepare, never send, a Gmail draft request."""

    REQUIRED_COLUMNS = {"event_id", "name", "email", "request", "opt_in"}

    def __init__(self, *, operator_token: str) -> None:
        if not operator_token:
            raise ValueError("operator_token is required")
        self.operator_token = operator_token

    def prepare_from_sheet_row(self, row: Mapping[str, Any]) -> AdapterResult:
        missing = sorted(name for name in self.REQUIRED_COLUMNS if name not in row)
        if missing:
            return AdapterResult(
                status="human_review",
                event_id=str(row.get("event_id") or "missing"),
                reason="missing columns: " + ", ".join(missing),
            )

        try:
            intake = LeadIntake(
                event_id=str(row["event_id"]),
                name=str(row["name"]),
                email=str(row["email"]),
                request=str(row["request"]),
                opt_in=self._strict_bool(row["opt_in"]),
            )
        except (ValidationError, ValueError) as exc:
            return AdapterResult(
                status="human_review",
                event_id=str(row.get("event_id") or "missing"),
                reason="sheet row failed validation",
            )

        prepared = prepare_lead(intake, x_jakeai_operator_token=self.operator_token)
        if prepared.status != "awaiting_approval" or not prepared.prepared_draft:
            return AdapterResult(
                status=prepared.status,
                event_id=prepared.event_id,
                reason=prepared.reason,
            )

        draft = prepared.prepared_draft
        return AdapterResult(
            status="draft_ready",
            event_id=prepared.event_id,
            draft_request={
                "operation": "gmail.create_draft",
                "to": draft["to"],
                "subject": draft["subject"],
                "body": draft["body"],
                "send": False,
                "human_approval_required_before_send": True,
            },
        )

    @staticmethod
    def _strict_bool(value: Any) -> bool:
        if value is True:
            return True
        if value is False:
            return False
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        raise ValueError("opt_in must be an explicit boolean")
