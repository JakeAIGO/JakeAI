"""Synthetic connector sandbox for Move the Damn Data.

No network calls. No credentials. No external side effects. This adapter validates the
integration envelope and passes only normalized business data plus out-of-band authority
to the reference engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Set

from engine import RelayEngine, RelayEvent, RelayResult


FORBIDDEN_PAYLOAD_KEYS = {
    "password",
    "secret",
    "api_key",
    "token",
    "approval_token",
    "authorization",
    "permissions",
}


@dataclass(frozen=True)
class SandboxEnvelope:
    event_id: str
    tenant_id: str
    source: str
    subject_id: str
    occurred_at: str
    payload: Mapping[str, Any]
    requested_action: str


class FakeConnectorSandbox:
    """Validates connector boundaries before invoking the reference relay engine."""

    def __init__(self, *, tenant_id: str = "tenant-synthetic") -> None:
        self.tenant_id = tenant_id
        self.engine = RelayEngine()
        self.registered_connectors = {"synthetic_form", "synthetic_crm", "synthetic_accounting"}

    def submit(
        self,
        envelope: SandboxEnvelope,
        *,
        permissions: Set[str],
        approval_token: str | None = None,
        required_fields: Set[str] | None = None,
        destination: str = "synthetic_crm",
        field_map: Mapping[str, str] | None = None,
        allowed_actions: Set[str] | None = None,
    ) -> RelayResult:
        required_fields = required_fields or {"name", "email"}
        field_map = field_map or {"name": "contact_name", "email": "contact_email"}
        allowed_actions = allowed_actions or {"create_record", "send_external_message"}

        if envelope.tenant_id != self.tenant_id:
            return RelayResult(status="blocked", event_id=envelope.event_id, reason="tenant mismatch")

        if envelope.source not in self.registered_connectors:
            return RelayResult(status="blocked", event_id=envelope.event_id, reason="unknown connector")

        if not envelope.event_id or not envelope.subject_id or not envelope.occurred_at:
            return RelayResult(status="human_review", event_id=envelope.event_id or "missing", reason="invalid connector envelope")

        lowered = {str(k).lower() for k in envelope.payload.keys()}
        forbidden = sorted(lowered.intersection(FORBIDDEN_PAYLOAD_KEYS))
        if forbidden:
            return RelayResult(
                status="blocked",
                event_id=envelope.event_id,
                reason=f"secret/authority fields forbidden in payload: {', '.join(forbidden)}",
            )

        relay_event = RelayEvent(
            event_id=f"{envelope.tenant_id}:{envelope.event_id}",
            source=envelope.source,
            subject_id=envelope.subject_id,
            payload=envelope.payload,
            requested_action=envelope.requested_action,
            permissions=set(permissions),
            approval_token=approval_token,
        )
        return self.engine.process(
            relay_event,
            required_fields=required_fields,
            destination=destination,
            field_map=field_map,
            allowed_actions=allowed_actions,
        )
