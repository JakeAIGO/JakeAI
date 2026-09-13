from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import FrozenSet

from durable_state import DurableState


@dataclass(frozen=True)
class ApprovalGrant:
    grant_id: str
    principal_id: str
    event_id: str
    allowed_actions: FrozenSet[str]
    expires_at: datetime
    nonce: str


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    reason: str


class ApprovalGate:
    """Fail-closed approval validator with optional durable replay protection.

    Approval is bound to one principal and one event, scoped to explicit actions,
    time-limited, and single-use by grant_id+nonce. When a DurableState is supplied,
    consumption survives process restarts. Validation never performs the external
    action; callers may only use an allowed decision to prepare the next execution step.
    """

    def __init__(self, *, durable_state: DurableState | None = None) -> None:
        self._consumed: set[tuple[str, str]] = set()
        self._durable_state = durable_state

    def validate(
        self,
        *,
        grant: ApprovalGrant | None,
        principal_id: str,
        event_id: str,
        action: str,
        now: datetime | None = None,
    ) -> ApprovalDecision:
        if grant is None:
            return ApprovalDecision(False, "approval_missing")

        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            return ApprovalDecision(False, "invalid_clock")

        if not grant.grant_id or not grant.nonce:
            return ApprovalDecision(False, "approval_malformed")
        if grant.principal_id != principal_id:
            return ApprovalDecision(False, "principal_mismatch")
        if grant.event_id != event_id:
            return ApprovalDecision(False, "event_mismatch")
        if action not in grant.allowed_actions:
            return ApprovalDecision(False, "action_out_of_scope")
        if grant.expires_at.tzinfo is None:
            return ApprovalDecision(False, "approval_malformed")
        if current >= grant.expires_at:
            return ApprovalDecision(False, "approval_expired")

        replay_key = (grant.grant_id, grant.nonce)
        if replay_key in self._consumed:
            return ApprovalDecision(False, "approval_replayed")
        if self._durable_state is not None and self._durable_state.approval_consumed(*replay_key):
            return ApprovalDecision(False, "approval_replayed")

        if self._durable_state is not None:
            if not self._durable_state.consume_approval(*replay_key):
                return ApprovalDecision(False, "approval_replayed")
        self._consumed.add(replay_key)
        return ApprovalDecision(True, "approved_for_preparation")
