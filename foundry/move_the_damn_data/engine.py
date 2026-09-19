"""Fail-closed reference engine for Move the Damn Data.

Synthetic/reference implementation only. It deliberately separates interpretation from
execution, requires explicit permissions, records provenance, and routes ambiguity to
human review instead of guessing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Protocol, Set


GATED_ACTIONS = {
    "send_external_message",
    "change_price",
    "spend_money",
    "delete_record",
    "publish_publicly",
}


@dataclass(frozen=True)
class RelayEvent:
    event_id: str
    source: str
    subject_id: str
    payload: Mapping[str, Any]
    requested_action: str
    permissions: Set[str] = field(default_factory=set)
    approval_token: Optional[str] = None


@dataclass(frozen=True)
class RelayResult:
    status: str
    event_id: str
    destination: Optional[str] = None
    transformed: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    reason: Optional[str] = None
    audit_id: Optional[str] = None


class IdempotencyStore(Protocol):
    def get(self, event_id: str) -> Optional[Dict[str, Any]]: ...

    def put(self, event_id: str, result: Mapping[str, Any]) -> None: ...


class RelayEngine:
    """Deterministic administrative relay with fail-closed safety behavior."""

    def __init__(self, *, idempotency_store: IdempotencyStore | None = None) -> None:
        self._processed: MutableMapping[str, RelayResult] = {}
        self._audit: list[Dict[str, Any]] = []
        self._idempotency_store = idempotency_store

    @property
    def audit_log(self) -> tuple[Dict[str, Any], ...]:
        return tuple(self._audit)

    def process(
        self,
        event: RelayEvent,
        *,
        required_fields: Iterable[str],
        destination: str,
        field_map: Mapping[str, str],
        allowed_actions: Set[str],
    ) -> RelayResult:
        original = self._lookup_processed(event.event_id)
        if original is not None:
            return RelayResult(
                status="duplicate",
                event_id=event.event_id,
                destination=original.destination,
                transformed=original.transformed,
                action=original.action,
                reason="event_id already processed; no second action performed",
                audit_id=original.audit_id,
            )

        missing = [name for name in required_fields if self._is_missing(event.payload.get(name))]
        if missing:
            return self._record(
                event,
                RelayResult(
                    status="human_review",
                    event_id=event.event_id,
                    reason=f"missing required fields: {', '.join(sorted(missing))}",
                ),
            )

        if event.requested_action not in allowed_actions:
            return self._record(
                event,
                RelayResult(
                    status="blocked",
                    event_id=event.event_id,
                    reason="requested action is not allowed by this workflow",
                ),
            )

        required_permission = f"action:{event.requested_action}"
        if required_permission not in event.permissions:
            return self._record(
                event,
                RelayResult(
                    status="blocked",
                    event_id=event.event_id,
                    reason=f"missing explicit permission: {required_permission}",
                ),
            )

        if event.requested_action in GATED_ACTIONS and not event.approval_token:
            return self._record(
                event,
                RelayResult(
                    status="awaiting_approval",
                    event_id=event.event_id,
                    reason="gated action requires explicit human approval",
                ),
            )

        transformed = {dst: event.payload[src] for src, dst in field_map.items() if src in event.payload}
        result = RelayResult(
            status="prepared" if event.requested_action in GATED_ACTIONS else "completed",
            event_id=event.event_id,
            destination=destination,
            transformed=transformed,
            action=event.requested_action,
        )
        return self._record(event, result)

    def _lookup_processed(self, event_id: str) -> RelayResult | None:
        cached = self._processed.get(event_id)
        if cached is not None:
            return cached
        if self._idempotency_store is None:
            return None
        stored = self._idempotency_store.get(event_id)
        if stored is None:
            return None
        try:
            restored = RelayResult(**stored)
        except TypeError as exc:
            raise RuntimeError("persisted idempotency record is invalid") from exc
        self._processed[event_id] = restored
        return restored

    def _record(self, event: RelayEvent, result: RelayResult) -> RelayResult:
        audit_id = sha256(f"{event.event_id}|{event.source}|{event.subject_id}".encode()).hexdigest()[:16]
        result = RelayResult(
            status=result.status,
            event_id=result.event_id,
            destination=result.destination,
            transformed=result.transformed,
            action=result.action,
            reason=result.reason,
            audit_id=audit_id,
        )
        if self._idempotency_store is not None:
            self._idempotency_store.put(event.event_id, asdict(result))
        self._processed[event.event_id] = result
        self._audit.append(
            {
                "audit_id": audit_id,
                "event_id": event.event_id,
                "source": event.source,
                "subject_id": event.subject_id,
                "requested_action": event.requested_action,
                "status": result.status,
            }
        )
        return result

    @staticmethod
    def _is_missing(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())
