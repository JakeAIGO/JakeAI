"""Fail-closed connector recovery primitives for Move the Damn Data.

This module models connector delivery uncertainty without performing any real network
or external-system actions. Unknown outcomes are quarantined for reconciliation rather
than retried blindly. Optional DurableState preserves recovery decisions across restarts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Literal

from durable_state import DurableState


Outcome = Literal["not_attempted", "confirmed_success", "confirmed_failure", "unknown"]
Decision = Literal["execute", "retry", "complete", "quarantine", "blocked"]


@dataclass(frozen=True)
class DeliveryState:
    event_id: str
    action: str
    attempt_count: int
    outcome: Outcome
    external_reference: str | None = None


@dataclass(frozen=True)
class RecoveryDecision:
    decision: Decision
    reason: str


class RecoveryCoordinator:
    """Conservative state machine for retry and partial-failure handling."""

    def __init__(self, *, max_attempts: int = 3, durable_state: DurableState | None = None) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.max_attempts = max_attempts
        self._states: Dict[str, DeliveryState] = {}
        self._durable_state = durable_state

    def _load(self, event_id: str) -> DeliveryState | None:
        if event_id in self._states:
            return self._states[event_id]
        if self._durable_state is None:
            return None
        record = self._durable_state.recovery(event_id)
        if record is None:
            return None
        try:
            state = DeliveryState(
                event_id=event_id,
                action=str(record["action"]),
                attempt_count=int(record["attempt_count"]),
                outcome=record["outcome"],
                external_reference=record.get("external_reference"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("durable recovery state invalid; fail closed") from exc
        if state.outcome not in {"not_attempted", "confirmed_success", "confirmed_failure", "unknown"}:
            raise ValueError("durable recovery outcome invalid; fail closed")
        if state.attempt_count < 0 or not state.action:
            raise ValueError("durable recovery state invalid; fail closed")
        self._states[event_id] = state
        return state

    def _store(self, state: DeliveryState) -> DeliveryState:
        self._states[state.event_id] = state
        if self._durable_state is not None:
            self._durable_state.put_recovery(state.event_id, asdict(state))
        return state

    def begin(self, *, event_id: str, action: str) -> RecoveryDecision:
        if not event_id or not action:
            return RecoveryDecision("blocked", "missing event or action identity")

        state = self._load(event_id)
        if state is None:
            self._store(DeliveryState(event_id, action, 0, "not_attempted"))
            return RecoveryDecision("execute", "first attempt permitted")

        if state.action != action:
            return RecoveryDecision("blocked", "event identity reused for a different action")
        if state.outcome == "confirmed_success":
            return RecoveryDecision("complete", "already confirmed successful; do not execute again")
        if state.outcome == "unknown":
            return RecoveryDecision("quarantine", "prior outcome unknown; reconcile before any retry")
        if state.attempt_count >= self.max_attempts:
            return RecoveryDecision("quarantine", "retry budget exhausted")
        if state.outcome == "confirmed_failure":
            return RecoveryDecision("retry", "confirmed failure may be retried safely")
        if state.outcome == "not_attempted":
            return RecoveryDecision("execute", "attempt permitted")
        return RecoveryDecision("blocked", "unrecognized recovery state")

    def record_attempt(
        self,
        *,
        event_id: str,
        action: str,
        outcome: Outcome,
        external_reference: str | None = None,
    ) -> DeliveryState:
        if outcome == "not_attempted":
            raise ValueError("record_attempt requires an attempted outcome")
        current = self._load(event_id)
        if current is None:
            raise ValueError("begin must be called before record_attempt")
        if current.action != action:
            raise ValueError("event identity reused for a different action")
        if current.outcome == "confirmed_success":
            raise ValueError("successful event is immutable")

        updated = DeliveryState(
            event_id=event_id,
            action=action,
            attempt_count=current.attempt_count + 1,
            outcome=outcome,
            external_reference=external_reference,
        )
        return self._store(updated)

    def reconcile_success(self, *, event_id: str, external_reference: str) -> DeliveryState:
        current = self._load(event_id)
        if current is None:
            raise ValueError("unknown event")
        if current.outcome != "unknown":
            raise ValueError("only unknown outcomes may be reconciled")
        updated = DeliveryState(
            event_id=current.event_id,
            action=current.action,
            attempt_count=current.attempt_count,
            outcome="confirmed_success",
            external_reference=external_reference,
        )
        return self._store(updated)

    def reconcile_failure(self, *, event_id: str) -> DeliveryState:
        current = self._load(event_id)
        if current is None:
            raise ValueError("unknown event")
        if current.outcome != "unknown":
            raise ValueError("only unknown outcomes may be reconciled")
        updated = DeliveryState(
            event_id=current.event_id,
            action=current.action,
            attempt_count=current.attempt_count,
            outcome="confirmed_failure",
            external_reference=None,
        )
        return self._store(updated)

    def state(self, event_id: str) -> DeliveryState | None:
        return self._load(event_id)
