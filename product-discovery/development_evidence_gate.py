"""
JakeAI Product Development / Evidence Gate
Stage 3 of the Autonomous Product Factory

Consumes a Stage 2 or independent-validation artifact and routes a candidate
deterministically to DEVELOP, HOLD, or REJECT.

DEVELOP is advisory only. It means a bounded product-specification step is
eligible; it never authorizes construction, spending, checkout, publication,
deployment, or consequential external action.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

VERSION = "0.2.0"
DEVELOP_SCORE_THRESHOLD = 80
HOLD_SCORE_THRESHOLD = 50
DEVELOP_SOURCE_THRESHOLD = 5
DEVELOP_EVIDENCE_THRESHOLD = 3
ROUTE_DEVELOP = "DEVELOP"
ROUTE_HOLD = "HOLD"
ROUTE_REJECT = "REJECT"


def _as_int(value: Any, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field} must be non-negative")
    return result


def validate_stage2_artifact(data: dict[str, Any]) -> None:
    required = (
        "candidate_title", "proposed_skill", "validation_score",
        "independent_source_count", "evidence_count", "disposition",
    )
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError("Validation artifact missing required fields: " + ", ".join(missing))
    score = _as_int(data["validation_score"], "validation_score")
    if score > 100:
        raise ValueError("validation_score must be between 0 and 100")
    _as_int(data["independent_source_count"], "independent_source_count")
    _as_int(data["evidence_count"], "evidence_count")


def identify_evidence_gaps(data: dict[str, Any]) -> list[str]:
    score = _as_int(data["validation_score"], "validation_score")
    sources = _as_int(data["independent_source_count"], "independent_source_count")
    evidence = _as_int(data["evidence_count"], "evidence_count")
    gaps: list[str] = []
    if score < DEVELOP_SCORE_THRESHOLD:
        gaps.append(f"Raise validation score from {score} to at least {DEVELOP_SCORE_THRESHOLD} using independently reviewable evidence.")
    if sources < DEVELOP_SOURCE_THRESHOLD:
        gaps.append(f"Increase independent source count from {sources} to at least {DEVELOP_SOURCE_THRESHOLD}.")
    if evidence < DEVELOP_EVIDENCE_THRESHOLD:
        gaps.append(f"Increase supporting evidence items from {evidence} to at least {DEVELOP_EVIDENCE_THRESHOLD}.")
    if not (data.get("counter_evidence") or []):
        gaps.append("Actively search for and record counter-evidence before product-spec approval.")
    if data.get("independently_validated") is not True:
        gaps.append("Complete independent validation; evidence counts alone cannot authorize a DEVELOP route.")
    return gaps


def route_stage3(data: dict[str, Any]) -> dict[str, Any]:
    validate_stage2_artifact(data)
    score = _as_int(data["validation_score"], "validation_score")
    sources = _as_int(data["independent_source_count"], "independent_source_count")
    evidence = _as_int(data["evidence_count"], "evidence_count")
    stage2_disposition = str(data.get("disposition") or "").strip()
    counter_evidence = data.get("counter_evidence") or []
    independently_validated = data.get("independently_validated") is True

    hard_evidence_failure = stage2_disposition in {
        "INSUFFICIENT_INDEPENDENT_EVIDENCE", "REJECTED", "REJECT"
    }
    develop_ready = (
        score >= DEVELOP_SCORE_THRESHOLD
        and sources >= DEVELOP_SOURCE_THRESHOLD
        and evidence >= DEVELOP_EVIDENCE_THRESHOLD
        and independently_validated
        and bool(counter_evidence)
        and not hard_evidence_failure
    )

    if develop_ready:
        route = ROUTE_DEVELOP
        reason = (
            "Independent evidence, counter-evidence review, and numeric thresholds support "
            "advancing to a bounded product-specification step, subject to human approval "
            "and later technical, security, legal, and commercial gates."
        )
    elif score >= HOLD_SCORE_THRESHOLD or not hard_evidence_failure:
        route = ROUTE_HOLD
        reason = (
            "Candidate remains plausible but one or more evidence controls are incomplete. "
            "Gather only the identified missing evidence or validation."
        )
    else:
        route = ROUTE_REJECT
        reason = (
            "Current validation evidence is too weak to justify continued product development "
            "without materially new evidence."
        )

    return {
        "stage": "DEVELOPMENT_EVIDENCE_GATE_V0_2",
        "gate_version": VERSION,
        "candidate_title": data["candidate_title"],
        "proposed_skill": data["proposed_skill"],
        "previous_stage": data.get("stage", "VALIDATION"),
        "previous_disposition": stage2_disposition,
        "previous_validation_score": score,
        "independent_source_count": sources,
        "evidence_count": evidence,
        "independently_validated": independently_validated,
        "counter_evidence_count": len(counter_evidence),
        "route": route,
        "route_reason": reason,
        "evidence_gaps": identify_evidence_gaps(data),
        "history": {
            "prior_generated_at": data.get("generated_at"),
            "prior_validation_score": score,
            "prior_disposition": stage2_disposition,
        },
        "product_spec_eligible": route == ROUTE_DEVELOP,
        "build_authorized": False,
        "spending_authorized": False,
        "publication_authorized": False,
        "deployment_authorized": False,
        "checkout_authorized": False,
        "human_approval_required": True,
        "claim_boundary": (
            "A DEVELOP route authorizes no external or commercial action. It only indicates "
            "eligibility for a bounded product-specification step."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run(input_path: Path, output_path: Path) -> dict[str, Any]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    result = route_stage3(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Usage: python product-discovery/development_evidence_gate.py <validation.json> [stage3-output.json]")
        return 2
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) == 3 else Path("product-discovery/development/product-development-001.json")
    try:
        result = run(input_path, output_path)
    except Exception as exc:
        print(f"Stage 3 development/evidence gate failed: {exc}")
        return 1
    print("=" * 72)
    print("JAKEAI PRODUCT DEVELOPMENT / EVIDENCE GATE — STAGE 3")
    print("=" * 72)
    print(f"Candidate: {result['candidate_title']}")
    print(f"Previous score: {result['previous_validation_score']} / 100")
    print(f"Route: {result['route']}")
    print(f"Product-spec eligible: {result['product_spec_eligible']}")
    print("Build authorized: NO")
    print("Spending authorized: NO")
    print("Publication authorized: NO")
    print("Human approval: REQUIRED")
    print(f"Artifact: {output_path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
