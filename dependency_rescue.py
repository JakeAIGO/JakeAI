"""JakeAI Dependency Rescue v1.

Offline, fail-closed scanner for redacted text artifacts. It identifies known
vendor deprecations without executing customer code or requiring credentials.
Rule packs are explicit, reviewable, and tied to current primary-source evidence.
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
    confirmed_patterns: tuple[str, ...]
    candidate_patterns: tuple[str, ...]
    remediation: str
    verification: str
    source_url: str
    source_checked: str
    severity: str = "high"
    timing_note: str = ""

RULES: tuple[Rule, ...] = (
    Rule(
        "cloudflare-service-key", "Cloudflare", "Legacy Service Key authentication", "2026-09-30",
        (r"(?i)X-Auth-User-Service-Key",),
        (r"(?i)origin.?ca.*service.?key", r"(?i)v1\.0-[A-Za-z0-9_-]+"),
        "Inventory each caller and migrate to a scoped API Token using least privilege; rotate/revoke the legacy key only after verification.",
        "Exercise each affected certificate/API path with the replacement token and confirm expected authorization before revocation.",
        "https://developers.cloudflare.com/changelog/post/2026-03-19-service-key-authentication-deprecated/", "2026-09-12"),
    Rule(
        "coralogix-legacy-ingest", "Coralogix", "Legacy ingestion endpoint/authentication", "2026-09-30",
        (r"(?i)api\.[A-Za-z0-9.-]*coralogix[^\s'\"]*/api/v1/logs", r"(?i)api\.[A-Za-z0-9.-]*coralogix[^\s'\"]*/logs/rest/(?:singles|bulk)"),
        (r"(?i)private-link(?:-api)?\.[A-Za-z0-9.-]*coralogix", r"(?i)coralogix.*(?:logstash|filebeat)"),
        "Map the caller to the current region endpoint, Bearer authentication, network allowlist requirements, and supported ingestion path.",
        "Send a controlled test event and verify it is searchable at the destination before retiring the legacy path.",
        "https://coralogix.com/docs/user-guides/latest-updates/deprecations/endpoints/", "2026-09-12"),
    Rule(
        "databricks-supervisor-api", "Databricks", "Supervisor API (Beta) end of life", "2026-09-30",
        (r"(?i)databricks.{0,120}supervisor.{0,40}api", r"(?i)supervisor[_ -]?api"),
        (r"(?i)supervisor.{0,120}databricks",),
        "Inventory Supervisor API callers and migrate the affected agent workflow to custom agents on Databricks Apps after validating feature and deployment requirements.",
        "Run representative agent tasks against the replacement in a non-production environment and confirm the retired Supervisor API is no longer called.",
        "https://docs.databricks.com/aws/en/release-notes/whats-coming", "2026-09-12"),
    Rule(
        "google-ads-v22", "Google Ads", "Google Ads API v22 dependency", "2026-10-07",
        (r"google\.ads\.googleads\.v22", r"(?i)googleads/v22", r"(?i)googleads\.v22"),
        (r"(?i)google.?ads.{0,80}\bv22\b",),
        "Upgrade the client/API surface after reviewing version-specific breaking changes; update affected service/method usage.",
        "Run representative read/write regression tests in a non-destructive environment and confirm no v22 requests remain.",
        "https://ads-developers.googleblog.com/2026/09/", "2026-09-12"),
    Rule(
        "qlik-cloudevent-legacy", "Qlik", "Qlik webhook CloudEvent migration candidate", "2026-10-06",
        (),
        (r"(?i)qlik.{0,120}webhook", r"(?i)qlik.{0,120}cloudevent", r"(?i)cloudevent.{0,120}qlik"),
        "Inspect the workflow against Qlik's current CloudEvent payload mapping and remap every downstream legacy-field reference.",
        "Replay representative webhook payloads and verify conditions, templates and outbound payloads end-to-end.",
        "https://community.qlik.com/t5/Official-Support-Articles/Qlik-Cloud-webhooks-Migrate-Qlik-Automate-workflows-to/ta-p/2549672", "2026-09-12"),
    Rule(
        "ews-exchange-online", "Microsoft Exchange Online", "Exchange Web Services phased disablement", "2026-10-01",
        (r"(?i)https://outlook\.office365\.com/EWS/Exchange\.asmx", r"(?i)Microsoft\.Exchange\.WebServices"),
        (r"(?i)ExchangeService\b", r"(?i)/EWS/Exchange\.asmx"),
        "Classify the caller as Exchange Online, on-premises, vendor-owned, Graph-replaceable, or parity-gap/manual-review required before changing it.",
        "Verify required behavior against the replacement interface; do not assume Microsoft Graph feature parity.",
        "https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-ews-exchange-online", "2026-09-13", "high",
        "Phased Exchange Online EWS disablement begins 2026-10-01; permanent retirement is 2027-04-01. Applicability can differ by workload and tenant configuration; on-premises Exchange EWS is not covered by this retirement."),
)

def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)

def _collect(patterns: tuple[str, ...], text: str) -> list[dict]:
    matches = []
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            matches.append({"line": text.count("\n", 0, m.start()) + 1, "evidence": m.group(0)[:160]})
    return matches[:20]

def scan_text(text: str, filename: str = "artifact.txt", today: date | None = None) -> dict:
    """Scan one text artifact. Secret detection fails closed before analysis."""
    today = today or date.today()
    if contains_secret(text):
        return {"status": "BLOCKED_SECRET_DETECTED", "filename": filename,
                "message": "Potential secret detected. Redact credentials and resubmit; JakeAI did not analyze the artifact.", "findings": []}
    findings = []
    for rule in RULES:
        confirmed = _collect(rule.confirmed_patterns, text)
        candidates = _collect(rule.candidate_patterns, text)
        if confirmed or candidates:
            deadline = date.fromisoformat(rule.deadline)
            confidence = "confirmed-signature" if confirmed else "review-candidate"
            findings.append({**asdict(rule), "days_to_deadline": (deadline - today).days,
                             "matches": confirmed + candidates, "confidence": confidence,
                             "human_verification_required": True})
    return {"status": "REVIEW_REQUIRED" if findings else "NO_KNOWN_MATCHES",
            "filename": filename, "findings": findings,
            "limitations": "Rule-pack scan only. A candidate is not proof of impact, and no-match does not prove the artifact is dependency-safe."}

def scan_files(files: Iterable[tuple[str, str]], today: date | None = None) -> dict:
    results = [scan_text(text, name, today) for name, text in files]
    blocked = any(r["status"] == "BLOCKED_SECRET_DETECTED" for r in results)
    return {"status": "BLOCKED_SECRET_DETECTED" if blocked else "COMPLETE", "results": results}
