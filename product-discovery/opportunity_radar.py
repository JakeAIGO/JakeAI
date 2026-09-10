"""
JakeAI Opportunity Radar
Stage 0 of the Autonomous Product Discovery Pipeline

Purpose:
Turn external signals into commercially grounded opportunity signals
before they enter JakeAI Stage 1 Product Discovery.

Pipeline:
Opportunity Radar -> Stage 1 Discovery -> Stage 2 Validation ->
Stage 3 Develop/Hold/Reject -> Build -> QA -> Marketplace
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RADAR_VERSION = "0.1.0"

# A signal does NOT qualify merely because it is interesting.
# It must indicate work, pain, cost, risk, demand, or operational change.
OPERATIONAL_TERMS = {
    "shortage", "bottleneck", "capacity", "delay", "downtime",
    "scrap", "rework", "yield", "maintenance", "compliance",
    "integration", "acquisition", "merger", "expansion", "factory",
    "plant", "supplier", "supply chain", "inventory", "quality",
    "inspection", "scheduling", "planning", "forecasting",
    "monitoring", "reporting", "optimization", "cost",
    "labor", "workforce", "risk", "incident", "failure",
    "production", "manufacturing", "deployment", "logistics",
    "energy", "infrastructure", "construction", "robotics",
}

VALUE_TERMS = {
    "save", "reduce", "increase", "improve", "accelerate",
    "prevent", "avoid", "optimize", "automate", "streamline",
    "efficiency", "productivity", "revenue", "cost",
    "downtime", "scrap", "rework", "yield", "capacity",
}

AI_EXECUTABLE_TERMS = {
    "data", "analysis", "monitor", "detect", "classify",
    "compare", "score", "rank", "forecast", "schedule",
    "report", "alert", "document", "research", "review",
    "optimize", "recommend", "triage", "coordinate",
    "workflow", "software", "api", "digital", "model",
}


def normalize(text: Any) -> str:
    """Normalize arbitrary input into searchable lowercase text."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def count_matches(text: str, vocabulary: set[str]) -> list[str]:
    """Return vocabulary terms found in text."""
    return sorted(term for term in vocabulary if term in text)


def clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def build_combined_text(signal: dict[str, Any]) -> str:
    fields = [
        signal.get("title"),
        signal.get("summary"),
        signal.get("description"),
        signal.get("content"),
        signal.get("problem"),
        signal.get("industry"),
        signal.get("why_it_matters"),
    ]
    return normalize(" ".join(str(x or "") for x in fields))


def evaluate_signal(signal: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluate whether an external signal deserves entry into
    JakeAI's product-discovery pipeline.

    This is intentionally conservative.
    """

    text = build_combined_text(signal)

    operational_hits = count_matches(text, OPERATIONAL_TERMS)
    value_hits = count_matches(text, VALUE_TERMS)
    executable_hits = count_matches(text, AI_EXECUTABLE_TERMS)

    # Evidence metadata supplied by ingestion layer.
    source = signal.get("source") or signal.get("source_name")
    source_url = signal.get("source_url") or signal.get("url")
    published_at = signal.get("published_at")
    industry = signal.get("industry", "unknown")

    # Scoring is transparent rather than pretending to be probabilistic.
    problem_score = min(25, len(operational_hits) * 4)
    value_score = min(25, len(value_hits) * 5)
    executable_score = min(25, len(executable_hits) * 4)

    evidence_score = 0
    if source:
        evidence_score += 8
    if source_url:
        evidence_score += 8
    if published_at:
        evidence_score += 4
    if signal.get("independent_sources"):
        try:
            count = int(signal["independent_sources"])
            evidence_score += min(5, max(0, count - 1))
        except (TypeError, ValueError):
            pass

    evidence_score = min(25, evidence_score)

    total = clamp(
        problem_score +
        value_score +
        executable_score +
        evidence_score
    )

    # Radar disposition thresholds.
    if total >= 70:
        disposition = "PROMOTE_TO_DISCOVERY"
    elif total >= 45:
        disposition = "NEEDS_MORE_EVIDENCE"
    else:
        disposition = "REJECT_NOISE"

    # Never allow weak evidence to masquerade as a qualified opportunity.
    if not source or not source_url:
        if disposition == "PROMOTE_TO_DISCOVERY":
            disposition = "NEEDS_MORE_EVIDENCE"

    opportunity = {
        "radar_version": RADAR_VERSION,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "signal_id": signal.get("signal_id") or signal.get("id"),
        "title": signal.get("title", "Untitled signal"),
        "industry": industry,
        "source": source,
        "source_url": source_url,
        "published_at": published_at,
        "radar_score": total,
        "disposition": disposition,
        "score_breakdown": {
            "real_operational_problem": problem_score,
            "economic_value_signal": value_score,
            "ai_executability": executable_score,
            "evidence_quality": evidence_score,
        },
        "evidence": {
            "operational_signals": operational_hits,
            "value_signals": value_hits,
            "ai_executable_signals": executable_hits,
            "independent_sources": signal.get("independent_sources", 1),
        },
        "commercial_questions": {
            "who_has_this_problem": signal.get("buyer") or "UNRESOLVED",
            "what_work_is_created": signal.get("work_created") or "UNRESOLVED",
            "why_would_they_pay": signal.get("economic_value") or "UNRESOLVED",
            "is_problem_repeatable": signal.get("repeatable") or "UNRESOLVED",
        },
        "original_signal": signal,
    }

    return opportunity


def save_result(result: dict[str, Any]) -> Path:
    output_dir = Path("product-discovery/radar-output")
    output_dir.mkdir(parents=True, exist_ok=True)

    signal_id = result.get("signal_id") or datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%S")

    safe_id = re.sub(r"[^A-Za-z0-9._-]", "-", str(signal_id))

    output_path = output_dir / f"{safe_id}-radar.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return output_path


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python product-discovery/opportunity_radar.py "
            "<signal.json>"
        )
        return 2

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"ERROR: Signal file not found: {input_path}")
        return 2

    with input_path.open("r", encoding="utf-8") as f:
        signal = json.load(f)

    result = evaluate_signal(signal)
    output_path = save_result(result)

    print("=" * 60)
    print("JAKEAI OPPORTUNITY RADAR — STAGE 0")
    print("=" * 60)
    print(f"Signal:      {result['title']}")
    print(f"Industry:    {result['industry']}")
    print(f"Radar score: {result['radar_score']} / 100")
    print(f"Disposition: {result['disposition']}")
    print()
    print("Score breakdown:")
    for key, value in result["score_breakdown"].items():
        print(f"  {key}: {value}")
    print()
    print(f"Output: {output_path}")
    print("=" * 60)

    # A rejected signal is still a successful Radar execution.
    # Disposition controls downstream routing, not process exit status.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
