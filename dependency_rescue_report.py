"""Customer-facing report rendering for JakeAI Dependency Rescue.

This module renders scan results into a concise Markdown fulfillment artifact.
It intentionally omits internal regex/rule implementation details.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _risk_label(days: int) -> str:
    if days < 0:
        return "PAST DATE"
    if days <= 7:
        return "CRITICAL"
    if days <= 30:
        return "HIGH"
    return "REVIEW"


def render_markdown(scan_result: dict, report_id: str = "UNASSIGNED") -> str:
    lines: list[str] = []
    lines.append("# JakeAI Dependency Rescue Report")
    lines.append("")
    lines.append(f"Report ID: `{report_id}`")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")

    if scan_result.get("status") == "BLOCKED_SECRET_DETECTED":
        lines.extend([
            "## BLOCKED — potential credential detected",
            "JakeAI stopped before dependency analysis. Redact credentials, private keys, passwords, access tokens, and secrets, then resubmit.",
            "No dependency conclusions were produced from the blocked artifact.",
        ])
        return "\n".join(lines) + "\n"

    all_findings: list[tuple[str, dict]] = []
    for result in scan_result.get("results", []):
        for finding in result.get("findings", []):
            all_findings.append((result.get("filename", "artifact"), finding))

    if not all_findings:
        lines.extend([
            "## No supported signatures found",
            "The current JakeAI rule packs did not find a known supported dependency signature in the submitted artifacts.",
            "This is **not** proof that the artifacts are dependency-safe; unsupported vendors, indirect dependencies, generated configuration, and runtime-only usage may not be visible.",
        ])
        return "\n".join(lines) + "\n"

    confirmed = sum(1 for _, f in all_findings if f.get("confidence") == "confirmed-signature")
    candidates = len(all_findings) - confirmed
    lines.extend([
        "## Executive summary",
        f"Findings: **{len(all_findings)}** total — **{confirmed} confirmed signatures**, **{candidates} review candidates**.",
        "No production changes were made. Every finding requires human verification before action.",
        "",
    ])

    for index, (filename, finding) in enumerate(sorted(all_findings, key=lambda x: x[1].get("days_to_deadline", 99999)), 1):
        days = int(finding.get("days_to_deadline", 99999))
        timing_note = finding.get("timing_note") or ""
        lines.extend([
            f"## {index}. {_risk_label(days)} — {finding.get('vendor')}: {finding.get('title')}",
            f"- Artifact: `{filename}`",
            f"- Vendor date: **{finding.get('deadline')}** ({days} days from scan date)",
        ])
        if timing_note:
            lines.append(f"- Timing context: {timing_note}")
        lines.extend([
            f"- Classification: **{finding.get('confidence')}**",
            f"- Evidence source checked: {finding.get('source_checked')}",
            f"- Source: {finding.get('source_url')}",
            "- Evidence locations: " + ", ".join(f"line {m.get('line')}" for m in finding.get("matches", [])[:10]),
            f"- Recommended remediation: {finding.get('remediation')}",
            f"- Verification: {finding.get('verification')}",
            "",
        ])

    lines.extend([
        "## Safe cutover sequence",
        "1. Verify each finding against the current vendor source linked above.",
        "2. Confirm the affected system/environment and owner.",
        "3. Make the minimum change in a non-destructive/test environment where feasible.",
        "4. Run the listed verification checks.",
        "5. Only after successful verification, retire the deprecated path or credential.",
        "",
        "## Limitations",
        "JakeAI Dependency Rescue is an artifact-level diagnostic, not a guarantee that every dependency has been found. It does not execute migrations, rotate credentials, modify infrastructure, or certify legal/security compliance.",
    ])
    return "\n".join(lines) + "\n"
