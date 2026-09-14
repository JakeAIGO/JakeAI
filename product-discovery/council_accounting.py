"""Provider-health and cost-accounting primitives for the JakeAI Council.

This module intentionally does not hard-code provider prices. Pricing changes and
may differ by account/model. A run may report token usage without claiming a
dollar cost unless explicit per-million-token rates are configured by the
operator. Missing data therefore stays UNKNOWN/UNPRICED rather than being
silently estimated.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return int(value)
    return None


def normalize_usage(provider: str, response: Mapping[str, Any]) -> Usage:
    """Normalize provider token accounting without guessing absent fields."""
    if provider == "gemini":
        raw = response.get("usageMetadata") or {}
        inp = _nonnegative_int(raw.get("promptTokenCount"))
        out = _nonnegative_int(raw.get("candidatesTokenCount"))
        total = _nonnegative_int(raw.get("totalTokenCount"))
    else:
        raw = response.get("usage") or {}
        if provider in {"openai", "anthropic"}:
            inp = _nonnegative_int(raw.get("input_tokens"))
            out = _nonnegative_int(raw.get("output_tokens"))
        else:  # OpenAI-compatible chat APIs: Perplexity and xAI/Grok.
            inp = _nonnegative_int(raw.get("prompt_tokens"))
            out = _nonnegative_int(raw.get("completion_tokens"))
        total = _nonnegative_int(raw.get("total_tokens"))

    if total is None and inp is not None and out is not None:
        total = inp + out
    return Usage(inp, out, total)


def parse_rate(value: str | None) -> Decimal | None:
    """Parse an operator-supplied USD-per-million-token rate, failing closed."""
    if value is None or not str(value).strip():
        return None
    try:
        rate = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return rate if rate >= 0 else None


def usage_cost_usd(
    usage: Usage,
    input_usd_per_million: str | None,
    output_usd_per_million: str | None,
) -> dict[str, Any]:
    """Return exact configured-rate cost or an explicit non-cost status."""
    if usage.input_tokens is None or usage.output_tokens is None:
        return {"status": "USAGE_UNAVAILABLE", "usd": None}
    input_rate = parse_rate(input_usd_per_million)
    output_rate = parse_rate(output_usd_per_million)
    if input_rate is None or output_rate is None:
        return {"status": "UNPRICED", "usd": None}
    million = Decimal(1_000_000)
    cost = (Decimal(usage.input_tokens) * input_rate + Decimal(usage.output_tokens) * output_rate) / million
    return {"status": "PRICED", "usd": float(cost), "currency": "USD"}


def provider_health(member: Mapping[str, Any]) -> str:
    """Convert a Council member result into a coarse operational health state."""
    status = member.get("status")
    if status == "SUCCESS" and member.get("participated"):
        return "HEALTHY"
    if status == "NOT_CONFIGURED":
        return "NOT_CONFIGURED"
    if status == "LIVE_CALL_NOT_AUTHORIZED":
        return "NOT_AUTHORIZED"

    text = f"{member.get('error_type', '')} {member.get('error', '')}".lower()
    if "insufficient_quota" in text or "credit_balance_exhausted" in text:
        return "ACCOUNT_BLOCKED"
    if any(x in text for x in ("http 408", "http 429", "http 500", "http 502", "http 503", "http 504", "timeout", "urlerror")):
        return "TRANSIENT_PROVIDER_FAILURE"
    if "jsondecodeerror" in text or "invalid verdict" in text:
        return "RESPONSE_FORMAT_FAILURE"
    return "PROVIDER_ERROR"


def summarize_health(members: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    states = {name: provider_health(member) for name, member in members.items()}
    return {
        "providers": states,
        "healthy_count": sum(state == "HEALTHY" for state in states.values()),
        "all_healthy": bool(states) and all(state == "HEALTHY" for state in states.values()),
    }
