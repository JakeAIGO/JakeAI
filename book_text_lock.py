"""JakeAI Book Factory exact-text lock.

The canonical book body is immutable once locked. Production formatting, narration,
and delivery may reference or segment the locked text, but may not alter any byte
inside that canonical body.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class FidelityResult:
    exact: bool
    expected_sha256: str
    actual_sha256: str
    expected_bytes: int
    actual_bytes: int
    first_difference: int | None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_exact(canonical: bytes, candidate: bytes) -> FidelityResult:
    """Byte-for-byte fidelity check. No Unicode/whitespace/punctuation normalization."""
    expected = sha256_bytes(canonical)
    actual = sha256_bytes(candidate)
    first = None
    if canonical != candidate:
        limit = min(len(canonical), len(candidate))
        for i in range(limit):
            if canonical[i] != candidate[i]:
                first = i
                break
        if first is None:
            first = limit
    return FidelityResult(
        exact=canonical == candidate,
        expected_sha256=expected,
        actual_sha256=actual,
        expected_bytes=len(canonical),
        actual_bytes=len(candidate),
        first_difference=first,
    )


def require_exact(canonical: bytes, candidate: bytes) -> FidelityResult:
    result = verify_exact(canonical, candidate)
    if not result.exact:
        raise ValueError(
            "JakeAI exact-text invariant failed: canonical book body was changed "
            f"(first difference byte {result.first_difference}; "
            f"expected {result.expected_sha256}, got {result.actual_sha256})."
        )
    return result


def lock_record(canonical: bytes, *, source_url: str, source_id: str,
                body_start_rule: str, body_end_rule: str) -> dict:
    """Create the immutable source record after non-book wrapper boundaries are chosen."""
    return {
        "algorithm": "sha256",
        "canonical_sha256": sha256_bytes(canonical),
        "canonical_bytes": len(canonical),
        "encoding": "UTF-8",
        "comparison": "exact_bytes",
        "normalization": "none",
        "source_url": source_url,
        "source_id": source_id,
        "body_start_rule": body_start_rule,
        "body_end_rule": body_end_rule,
        "locked": True,
    }
