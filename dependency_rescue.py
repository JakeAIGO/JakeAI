"""JakeAI Dependency Rescue v1.

Offline, fail-closed scanner for redacted text artifacts. It identifies known
vendor deprecations without executing customer code or requiring credentials.
Rule packs are intentionally explicit and reviewable.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
import re
from typing import Iterable


SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
]


@dataclass(frozen=True)
class Rule:
    id: str
    vendor: str
    title: str
    deadline: str
    patterns: tuple[str, ...]
    remediation: str
    verification: str
    severity: str = "high"


RULES: tuple[Rule, ...] = (
    Rule("cloudflare-service-key", "Cloudflare", "Legacy Service Key authentication", "2026-09-30",
         (r"X-Auth-User-Service-Key", r"(?i)origin.?ca.*service.?key"),
         "Inventory each caller and migrate to a scoped API Token using least privilege; rotate/revoke the legacy key only after verification.",
         "Exercise each affected certificate/API path with the replacement token and confirm expected authorization before revocation."),
    Rule("coralogix-legacy-ingest", "Coralogix", "Legacy ingestion endpoint/authentication", "2026-09-30",
         (r"(?i)coralogix.*(?:token|logstash|filebeat)", r"(?i)(?:token)['\"]?\s*[:=].*coralogix"),
         "Map the caller to the current region endpoint, Bearer authentication, network allowlist requirements, and supported ingestion path.",
         "Send a controlled test event and verify it is searchable at the destination before retiring the legacy path."),
    Rule("google-ads-v22", "Google Ads", "Google Ads API v22 dependency", "2026-10-07",
         (r"google\.ads\.googleads\.v22", r"/v22/", r"(?i)google.?ads.*v22"),
         "Upgrade the client/API surface after reviewing version-specific breaking changes; update affected service/method usage.",
         "Run representative read/write regression tests in a non-destructive environment and confirm no v22 requests remain."),
    Rule("qlik-cloudevent-legacy", "Qlik", "Legacy Qlik webhook payload field reference", "2026-10-06",
         (r"(?i)qlik.*webhook", r"(?i)cloud.?event.*qlik"),
         "Inspect the workflow against Qlik's current CloudEvent payload mapping and remap every downstream legacy-field reference.",
         "Replay representative webhook payloads and verify conditions, templates and outbound payloads end-to-end."),
    Rule("ews-exchange-online", "Microsoft Exchange Online", "Exchange Web Services dependency", "2026-10-01",
         (r"(?i)ExchangeService\b", r"(?i)/EWS/Exchange\.asmx", r"(?i)Microsoft\.Exchange\.WebServices"),
         "Classify the caller as Exchange Online, on-premises, vendor-owned, Graph-replaceable, or parity-gap/manual-review required before changing it.",
         "Verify required behavior against the replacement interface; do not assume Microsoft Graph feature parity."),
)


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


def scan_text(text: str, filename: str = "artifact.txt", today: date | None = None) -> dict:
    """Scan one text artifact. Secret detection fails closed before analysis."""
    today = today or date.today()
    if contains_secret(text):
        return {"status": "BLOCKED_SECRET_DETECTED", "filename": filename,
                "message": "Potential secret detected. Redact credentials and resubmit; JakeAI did not analyze the artifact.", "findings": []}
    findings = []
    for rule in RULES:
        matches = []
        for pattern in rule.patterns:
            for m in re.finditer(pattern, text):
                line = text.count("\n", 0, m.start()) + 1
                matches.append({"line": line, "evidence": m.group(0)[:160]})
        if matches:
            deadline = date.fromisoformat(rule.deadline)
            findings.append({**asdict(rule), "days_to_deadline": (deadline - today).days,
                             "matches": matches[:20], "confidence": "pattern-confirmed; human verification required"})
    return {"status": "REVIEW_REQUIRED" if findings else "NO_KNOWN_MATCHES",
            "filename": filename, "findings": findings,
            "limitations": "Rule-pack scan only. No-match does not prove the artifact is dependency-safe."}


def scan_files(files: Iterable[tuple[str, str]], today: date | None = None) -> dict:
    results = [scan_text(text, name, today) for name, text in files]
    blocked = any(r["status"] == "BLOCKED_SECRET_DETECTED" for r in results)
    return {"status": "BLOCKED_SECRET_DETECTED" if blocked else "COMPLETE", "results": results}
