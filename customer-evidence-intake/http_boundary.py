"""Private HTTP-boundary prototype for JakeAI Customer Evidence Intake v1.

This is framework-neutral boundary logic only. It is NOT deployed and does not
open a socket. It enforces authentication, bounded request size, origin policy,
content type, consent acknowledgement, rate limiting, and non-sensitive audit
metadata before delegating to the screened intake service.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any, Callable

from service import CustomerEvidenceService

MAX_REQUEST_BYTES = 12_000
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    body: dict[str, Any]


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW_SECONDS):
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate limit and window must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        q = self._events[key]
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class AuditSink:
    """In-memory non-sensitive audit prototype; stores no request body."""
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, event: str, *, actor_fingerprint: str, outcome: str) -> None:
        self.events.append({
            "event": event,
            "actor_fingerprint": actor_fingerprint,
            "outcome": outcome,
        })


class IntakeHttpBoundary:
    def __init__(
        self,
        service: CustomerEvidenceService,
        *,
        api_key: str,
        allowed_origins: set[str],
        rate_limiter: SlidingWindowRateLimiter | None = None,
        audit_sink: AuditSink | None = None,
        clock: Callable[[], float] = time.time,
    ):
        if not api_key or len(api_key) < 20:
            raise ValueError("api_key must be a strong deploy-time secret")
        if not allowed_origins:
            raise ValueError("allowed_origins must not be empty")
        if "*" in allowed_origins:
            raise ValueError("wildcard origin is forbidden for intake")
        self.service = service
        self._api_key = api_key
        self.allowed_origins = frozenset(allowed_origins)
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.audit_sink = audit_sink or AuditSink()
        self.clock = clock

    @staticmethod
    def _fingerprint(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def handle_submit(
        self,
        *,
        body: bytes,
        content_type: str,
        origin: str,
        authorization: str,
        client_id: str,
    ) -> HttpResult:
        actor = self._fingerprint(client_id or "unknown")

        if origin not in self.allowed_origins:
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="ORIGIN_REJECTED")
            return HttpResult(403, {"status": "REJECTED", "reason": "origin not allowed"})

        expected = f"Bearer {self._api_key}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="AUTH_REJECTED")
            return HttpResult(401, {"status": "REJECTED", "reason": "authentication required"})

        if not self.rate_limiter.allow(actor, now=self.clock()):
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="RATE_LIMITED")
            return HttpResult(429, {"status": "REJECTED", "reason": "rate limit exceeded"})

        if len(body) > MAX_REQUEST_BYTES:
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="TOO_LARGE")
            return HttpResult(413, {"status": "REJECTED", "reason": "request too large"})

        normalized_ct = content_type.split(";", 1)[0].strip().lower()
        if normalized_ct != "application/json":
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="CONTENT_TYPE_REJECTED")
            return HttpResult(415, {"status": "REJECTED", "reason": "application/json required"})

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="INVALID_JSON")
            return HttpResult(400, {"status": "REJECTED", "reason": "invalid JSON"})

        if not isinstance(payload, dict):
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="INVALID_SHAPE")
            return HttpResult(400, {"status": "REJECTED", "reason": "JSON object required"})

        # Consent lives outside the evidence payload and is not persisted in raw evidence.
        if payload.pop("consent_to_process_for_intake", None) is not True:
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="CONSENT_REQUIRED")
            return HttpResult(400, {"status": "REJECTED", "reason": "explicit intake consent required"})
        if payload.pop("acknowledge_no_secrets_or_sensitive_data", None) is not True:
            self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome="ACK_REQUIRED")
            return HttpResult(400, {"status": "REJECTED", "reason": "safety acknowledgement required"})

        service_result = self.service.submit(payload)
        result = asdict(service_result)
        status = service_result.status
        self.audit_sink.record("intake_submit", actor_fingerprint=actor, outcome=status)

        if status == "ACCEPTED":
            return HttpResult(202, result)
        if status in {"BLOCKED_SECRET_DETECTED", "BLOCKED_SENSITIVE_DATA"}:
            return HttpResult(400, result)
        if status == "HUMAN_REVIEW":
            return HttpResult(202, result)
        return HttpResult(400, result)
