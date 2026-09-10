"""
JakeAI Opportunity Radar
Stage 0 of the Autonomous Product Discovery Pipeline

Version 0.2.1

Routes signals to:
- PROMOTE_TO_DISCOVERY
- NEEDS_MORE_EVIDENCE
- REJECT_NOISE

Core rule:
UNKNOWN is not NEGATIVE.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RADAR_VERSION = "0.2.1"


OPERATIONAL_TERMS = {
    "shortage", "bottleneck", "capacity", "delay",
    "downtime", "scrap", "rework", "yield",
    "maintenance", "compliance", "integration",
    "supplier", "supply chain", "inventory",
    "quality", "inspection", "scheduling",
    "planning", "forecasting", "monitoring",
    "optimization", "cost", "labor", "workforce",
    "risk", "incident", "failure", "production",
    "manufacturing", "deployment", "logistics",
    "energy", "infrastructure", "construction",
    "robotics", "recall", "defect", "constraint",
    "backlog",
}


VALUE_TERMS = {
    "save", "reduce", "increase", "improve",
    "accelerate", "prevent", "avoid", "optimize",
    "automate", "streamline", "efficiency",
    "productivity", "revenue", "cost", "downtime",
    "scrap", "rework", "yield", "capacity",
    "margin", "profit", "savings", "growth",
    "billion", "million", "investment",
}


AI_EXECUTABLE_TERMS = {
    "data", "analysis", "monitor", "detect",
    "classify", "compare", "score", "rank",
    "forecast", "schedule", "report", "alert",
    "document", "research", "review", "optimize",
    "recommend", "triage", "coordinate",
    "workflow", "software", "api", "digital",
    "model", "tracking", "planning", "inspection",
    "prediction",
}


BUSINESS_CHANGE_TERMS = {
    "acquisition", "acquire", "acquires", "acquiring",
    "merger", "buy", "buys", "buying", "purchase",
    "expansion", "expand", "factory opening",
    "new factory", "new plant", "plant opening",
    "facility opening", "investment", "contract",
    "partnership", "supplier", "production increase",
    "production ramp", "capacity expansion",
    "layoff", "layoffs", "restructuring", "recall",
    "regulation", "regulatory", "shortage",
    "bottleneck", "backlog", "failure", "shutdown",
    "downtime",
}


HIGH_IMPACT_TERMS = {
    "billion", "million", "major", "largest",
    "record", "critical", "mission-critical",
    "global", "national", "industry-wide",
    "shortage", "bottleneck", "capacity",
}


UNRESOLVED_VALUES = {
    "", "unknown", "unresolved", "none",
    "null", "n/a",
}


def normalize(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def matches(text: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if term in text)


def unresolved(value: Any) -> bool:
    return normalize(value) in UNRESOLVED_VALUES


def build_text(signal: dict[str, Any]) -> str:
    fields = [
        signal.get("title"),
        signal.get("summary"),
        signal.get("description"),
        signal.get("content"),
        signal.get("problem"),
        signal.get("industry"),
        signal.get("why_it_matters"),
        signal.get("economic_value"),
        signal.get("work_created"),
    ]
    return normalize(" ".join(str(x or "") for x in fields))


def evaluate_signal(signal: dict[str, Any]) -> dict[str, Any]:
    text = build_text(signal)

    operational = matches(text, OPERATIONAL_TERMS)
    value = matches(text, VALUE_TERMS)
    executable = matches(text, AI_EXECUTABLE_TERMS)
    business_change = matches(text, BUSINESS_CHANGE_TERMS)
    impact = matches(text, HIGH_IMPACT_TERMS)

    source = signal.get("source") or signal.get("source_name")
    source_url = signal.get("source_url") or signal.get("url")
    published_at = signal.get("published_at")

    problem_score = min(25, len(operational) * 4)
    value_score = min(20, len(value) * 4)
    executable_score = min(20, len(executable) * 3)
    business_score = min(20, len(business_change) * 5)
    impact_score = min(10, len(impact) * 3)

    evidence_score = 0
    if source:
        evidence_score += 5
    if source_url:
        evidence_score += 5
    if published_at:
        evidence_score += 3

    try:
        independent_sources = int(
            signal.get("independent_sources", 1)
        )
    except (TypeError, ValueError):
        independent_sources = 1

    if independent_sources > 1:
        evidence_score += min(7, independent_sources - 1)

    evidence_score = min(15, evidence_score)

    total = min(
        100,
        problem_score
        + value_score
        + executable_score
        + business_score
        + impact_score
        + evidence_score,
    )

    research_fields = {
        "buyer_unresolved": unresolved(signal.get("buyer")),
        "work_created_unresolved": unresolved(
            signal.get("work_created")
        ),
        "economic_value_unresolved": unresolved(
            signal.get("economic_value")
        ),
        "repeatability_unresolved": unresolved(
            signal.get("repeatable")
        ),
    }

    unresolved_count = sum(research_fields.values())

    meaningful_signal = bool(
        operational or business_change or impact
    )

    if total >= 70 and unresolved_count <= 1:
        disposition = "PROMOTE_TO_DISCOVERY"

    elif meaningful_signal and (
        total >= 25 or unresolved_count >= 2
    ):
        disposition = "NEEDS_MORE_EVIDENCE"

    else:
        disposition = "REJECT_NOISE"

    if disposition == "PROMOTE_TO_DISCOVERY":
        if not source or not source_url:
            disposition = "NEEDS_MORE_EVIDENCE"

    if disposition == "PROMOTE_TO_DISCOVERY":
        next_action = "SEND_TO_PRODUCT_DISCOVERY"
    elif disposition == "NEEDS_MORE_EVIDENCE":
        next_action = "RESEARCH_COMMERCIAL_EVIDENCE"
    else:
        next_action = "ARCHIVE_SIGNAL"

    research_fields["unresolved_fields"] = unresolved_count

    return {
        "radar_version": RADAR_VERSION,
        "evaluated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "signal_id": (
            signal.get("signal_id")
            or signal.get("id")
        ),
        "title": signal.get(
            "title",
            "Untitled signal",
        ),
        "industry": signal.get(
            "industry",
            "Unknown",
        ),
        "source": source,
        "source_url": source_url,
        "published_at": published_at,
        "radar_score": total,
        "disposition": disposition,
        "next_action": next_action,
        "score_breakdown": {
            "real_operational_problem": problem_score,
            "economic_value_signal": value_score,
            "ai_executability": executable_score,
            "business_change_signal": business_score,
            "impact_signal": impact_score,
            "evidence_quality": evidence_score,
        },
        "research_status": research_fields,
        "evidence": {
            "operational_signals": operational,
            "value_signals": value,
            "ai_executable_signals": executable,
            "business_change_signals": business_change,
            "high_impact_signals": impact,
            "independent_sources": independent_sources,
        },
        "original_signal": signal,
    }


def save_result(result: dict[str, Any]) -> Path:
    output_dir = Path(
        "product-discovery/radar-output"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    signal_id = result.get("signal_id")

    if not signal_id:
        signal_id = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d-%H%M%S-%f")

    safe_id = re.sub(
        r"[^A-Za-z0-9._-]",
        "-",
        str(signal_id),
    )

    output_path = (
        output_dir
        / f"{safe_id}-radar.json"
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return output_path


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python "
            "product-discovery/opportunity_radar.py "
            "<signal.json>"
        )
        return 2

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(
            f"ERROR: Signal file not found: {input_path}"
        )
        return 2

    signal = json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
    )

    result = evaluate_signal(signal)
    output_path = save_result(result)

    print("=" * 70)
    print(
        "JAKEAI OPPORTUNITY RADAR — STAGE 0 v0.2.1"
    )
    print("=" * 70)
    print(f"Signal: {result['title']}")
    print(f"Industry: {result['industry']}")
    print(
        f"Radar score: "
        f"{result['radar_score']} / 100"
    )
    print(
        f"Disposition: "
        f"{result['disposition']}"
    )
    print(
        f"Next action: "
        f"{result['next_action']}"
    )
    print()

    print("Score breakdown:")
    for key, value in result[
        "score_breakdown"
    ].items():
        print(f"  {key}: {value}")

    print()
    print("Research status:")
    for key, value in result[
        "research_status"
    ].items():
        print(f"  {key}: {value}")

    print()
    print(f"Output: {output_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
