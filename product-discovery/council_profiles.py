"""Reusable review profiles for the JakeAI Multi-Model Council.

Profiles change the review lens, never the release authority. They are configuration
for advisory review only: no profile may merge, deploy, publish, spend money, or
turn a Council verdict into professional/legal approval.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CouncilProfile:
    name: str
    purpose: str
    review_lens: str
    required_seats: tuple[str, ...]
    human_approval_required: bool = True


ALL_SEATS = ("openai", "anthropic", "gemini", "perplexity", "grok")

PROFILES = {
    "full": CouncilProfile(
        name="full",
        purpose="General high-scrutiny review of a frozen evidence package.",
        review_lens="Evaluate architecture, evidence, safety, privacy, operations, market reality, commercial logic, and reasons to stop.",
        required_seats=ALL_SEATS,
    ),
    "product": CouncilProfile(
        name="product",
        purpose="Determine whether a proposed product solves a demonstrated problem and deserves further investment.",
        review_lens="Prioritize demonstrated pain, alternatives, measurable outcome, usability, implementation feasibility, willingness to pay, and kill criteria.",
        required_seats=ALL_SEATS,
    ),
    "security": CouncilProfile(
        name="security",
        purpose="Adversarial review of a proposed system, workflow, integration, or release boundary.",
        review_lens="Prioritize authorization, secrets, data exposure, abuse paths, fail-closed behavior, auditability, rollback, dependency risk, and incident containment.",
        required_seats=ALL_SEATS,
    ),
    "commercial": CouncilProfile(
        name="commercial",
        purpose="Challenge whether a bounded offer can earn money from an independent customer.",
        review_lens="Prioritize buyer, urgency, incumbent/free alternatives, differentiation, price, contribution margin, acquisition path, completion test, and reasons not to buy.",
        required_seats=ALL_SEATS,
    ),
    "release": CouncilProfile(
        name="release",
        purpose="Review whether an already-built release candidate is ready to be presented for human release approval.",
        review_lens="Prioritize evidence of tests, unresolved blockers, claims, privacy/legal/safety gates, rollback, observability, customer impact, and release-specific residual risk.",
        required_seats=ALL_SEATS,
    ),
}


def get_profile(name: str) -> CouncilProfile:
    """Resolve a known profile or fail closed on configuration mistakes."""
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown council profile: {name}") from exc


def profile_overlay(name: str) -> str:
    """Return a compact prompt overlay; does not replace provider seat focus."""
    p = get_profile(name)
    return (
        f"COUNCIL PROFILE: {p.name}. PURPOSE: {p.purpose} "
        f"REVIEW LENS: {p.review_lens} "
        "Preserve dissent. Do not infer peer opinions. Human approval remains required for consequential release or action."
    )


def release_authority(name: str) -> bool:
    """Council profiles never possess release authority."""
    get_profile(name)
    return False
