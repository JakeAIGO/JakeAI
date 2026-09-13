"""JakeAI Customer Evidence Intake v1 — private text-only prototype.

No network calls, files, credentials, or production actions. Fail closed.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

MAX_FIELD = 2000
MAX_TOTAL = 8000

SECRET_PATTERNS = [
    # Named secrets using assignment-like or natural-language separators.
    re.compile(r"(?i)\b(api[_ -]?key|access[_ -]?token|secret[_ -]?key|password|passwd|client[_ -]?secret)\b\s*(?::|=|is)\s*\S+"),
    # Authorization headers/tokens.
    re.compile(r"(?i)\bauthorization\s*:\s*(?:bearer|basic)\s+\S+"),
    # PEM private keys.
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    # Stripe secret/restricted keys.
    re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{12,}\b"),
    # GitHub classic and fine-grained token forms.
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    # AWS access key IDs.
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # JWT-like bearer material. Conservative because intake should not need JWTs.
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
]
SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
]
HIGH_CONSEQUENCE = re.compile(
    r"(?i)\b(medical|patient|diagnos|prescription|tax return|bank account|wire transfer|"
    r"payroll payment|payroll disbursement|hire|fire|terminate employee|legal advice|court filing|"
    r"safety-critical|life safety)\b"
)

REQUIRED = (
    "software_or_ai", "normal_automation", "residual_human_intervention",
    "frequency", "minutes_per_occurrence", "consequence_if_unhandled",
    "evidence_used_by_human",
)

@dataclass(frozen=True)
class IntakeResult:
    status: str
    reason: str
    packet: dict[str, Any] | None = None


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("all intake fields must be text")
    return " ".join(value.strip().split())


def screen_submission(raw: dict[str, Any]) -> IntakeResult:
    if not isinstance(raw, dict):
        return IntakeResult("REJECTED_INPUT", "submission must be an object")

    cleaned: dict[str, str] = {}
    try:
        for key in REQUIRED:
            cleaned[key] = _clean(raw.get(key, ""))
        contact = _clean(raw.get("contact", ""))
    except ValueError as exc:
        return IntakeResult("REJECTED_INPUT", str(exc))

    if any(not cleaned[k] for k in REQUIRED):
        return IntakeResult("REJECTED_INPUT", "all required fields must be completed")
    if any(len(v) > MAX_FIELD for v in [*cleaned.values(), contact]):
        return IntakeResult("REJECTED_INPUT", "field exceeds bounded text limit")

    joined = "\n".join([*cleaned.values(), contact])
    if len(joined) > MAX_TOTAL:
        return IntakeResult("REJECTED_INPUT", "submission exceeds total text limit")
    if any(p.search(joined) for p in SECRET_PATTERNS):
        return IntakeResult("BLOCKED_SECRET_DETECTED", "remove credentials or secrets and resubmit")
    if any(p.search(joined) for p in SENSITIVE_PATTERNS):
        return IntakeResult("BLOCKED_SENSITIVE_DATA", "remove sensitive identifiers/payment data and resubmit")
    if HIGH_CONSEQUENCE.search(joined):
        return IntakeResult("HUMAN_REVIEW", "potential high-consequence domain; no autonomous processing")

    try:
        minutes = float(cleaned["minutes_per_occurrence"])
        if minutes < 0 or minutes > 1440:
            raise ValueError
    except ValueError:
        return IntakeResult("REJECTED_INPUT", "minutes_per_occurrence must be a number from 0 to 1440")

    now = datetime.now(timezone.utc).isoformat()
    signature_material = "|".join([
        cleaned["software_or_ai"].lower(),
        cleaned["residual_human_intervention"].lower(),
        cleaned["evidence_used_by_human"].lower(),
    ])
    packet = {
        "submission_id": hashlib.sha256((now + signature_material).encode()).hexdigest()[:20],
        "received_at": now,
        **cleaned,
        "contact": contact or None,
        "minutes_per_occurrence": minutes,
        "safety_class": "LOW_CONSEQUENCE_CANDIDATE",
        "recurrence_signature": hashlib.sha256(signature_material.encode()).hexdigest(),
        "product_factory_status": "EVIDENCE_PACKETED",
        "limitations": "Evidence only; not proof of automation feasibility, safety, savings, or product demand.",
    }
    return IntakeResult("ACCEPTED", "safe text-only evidence packet created", packet)


def public_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Convenience wrapper suitable for tests; does not persist or transmit data."""
    return asdict(screen_submission(raw))
