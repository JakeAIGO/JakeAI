"""JakeAI Multi-Model Advisory Council.

Live provider calls are explicit, independent, provenance-recorded, parallelized,
and fail closed. A seat is never marked as participating unless a successful,
parseable response from that provider is captured. Council output is advisory
issue-spotting/research, not legal approval or professional advice.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_SYSTEM = """You are one independent member of the JakeAI Multi-Model Advisory Council. Analyze only the supplied frozen review package. Do not infer another council member's opinion and do not attempt consensus. Attack weak assumptions. Identify material risks, missing evidence, required mitigations, and questions for qualified counsel or operator verification. Do not claim legal approval. Return one complete JSON object only, with no markdown or commentary, containing: verdict (PASS_WITH_GATES|HOLD|REJECT), risks (array), mitigations (array), counsel_questions (array), confidence (0-1), rationale (string). Keep the complete response under 1800 tokens."""

SEAT_FOCUS = {
    "openai": "Focus on architecture, evidence quality, safety boundaries, failure modes, and synthesis-readiness.",
    "anthropic": "Focus on privacy, consent, liability, claims, retention, deletion, and subtle safety edge cases.",
    "gemini": "Focus on product UX, implementation feasibility, operational execution, abuse cases, and conversion flow.",
    "perplexity": "Focus on factual assumptions, current market/competitor/free-alternative risk, and claims needing external verification.",
    "grok": "Focus on commercial logic, differentiation, customer willingness to pay, adversarial objections, and reasons to kill the offer.",
}

PROVIDERS = {
    "openai": {"key": "OPENAI_API_KEY", "model_env": "OPENAI_COUNCIL_MODEL", "model": "gpt-5.6-sol"},
    "anthropic": {"key": "ANTHROPIC_API_KEY", "model_env": "ANTHROPIC_COUNCIL_MODEL", "model": "claude-sonnet-5"},
    "gemini": {"key": "GEMINI_API_KEY", "model_env": "GEMINI_COUNCIL_MODEL", "model": "gemini-3.8-flash"},
    "perplexity": {"key": "PERPLEXITY_API_KEY", "model_env": "PERPLEXITY_COUNCIL_MODEL", "model": "sonar-pro"},
    "grok": {"key": "XAI_API_KEY", "model_env": "XAI_COUNCIL_MODEL", "model": "grok-4.6"},
}

RETRYABLE_HTTP = {408, 409, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


class ProviderHTTPError(RuntimeError):
    """Sanitized provider failure safe for CI artifacts; never stores headers/keys."""
    def __init__(self, status, detail="provider_error"):
        self.status = int(status)
        self.detail = detail
        super().__init__(f"HTTP {self.status}: {detail}"[:500])


def _safe_error_detail(raw):
    """Extract only provider-declared error metadata; discard arbitrary bodies."""
    try:
        obj = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return "provider_error"
    err = obj.get("error", obj) if isinstance(obj, dict) else {}
    if not isinstance(err, dict):
        return "provider_error"
    fields = []
    for key in ("type", "code", "status", "message"):
        value = err.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            text = str(value).strip()
            text = re.sub(r"(?i)(api[_ -]?key|token|authorization|bearer)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
            fields.append(f"{key}={text[:240]}")
    return "; ".join(fields)[:420] or "provider_error"


def _retry_after_seconds(exc, attempt):
    raw = None
    if getattr(exc, "headers", None):
        raw = exc.headers.get("Retry-After")
    if raw:
        try:
            return min(max(float(raw), 0.0), 30.0)
        except ValueError:
            pass
    return min((2 ** attempt) + random.random(), 20.0)


def _post(url, body, headers):
    payload = json.dumps(body).encode()
    for attempt in range(MAX_ATTEMPTS):
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            status = exc.code
            if status in RETRYABLE_HTTP and attempt < MAX_ATTEMPTS - 1:
                time.sleep(_retry_after_seconds(exc, attempt))
                continue
            # Read only after retries are exhausted (or for a non-retryable error),
            # then retain a strict allowlist of provider error metadata.
            try:
                raw = exc.read(4096)
            except Exception:
                raw = b""
            raise ProviderHTTPError(status, _safe_error_detail(raw)) from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(min((2 ** attempt) + random.random(), 20.0))
    raise RuntimeError("provider request exhausted without response")


def _system_for(name):
    return f"{BASE_SYSTEM}\n\nSEAT-SPECIFIC FOCUS: {SEAT_FOCUS[name]}"


def _prompt(name, package):
    return f"{_system_for(name)}\n\nFROZEN REVIEW PACKAGE:\n{package}"


def _openai(name, package, key, model):
    d = _post(
        "https://api.openai.com/v1/responses",
        {"model": model, "input": _prompt(name, package), "store": False, "max_output_tokens": 2200},
        {"Authorization": f"Bearer {key}"},
    )
    texts = []
    for item in d.get("output", []):
        for c in item.get("content", []):
            if c.get("type") in ("output_text", "text") and c.get("text"):
                texts.append(c["text"])
    return "\n".join(texts), d.get("id")


def _anthropic(name, package, key, model):
    d = _post(
        "https://api.anthropic.com/v1/messages",
        {"model": model, "max_tokens": 4000, "temperature": 0, "system": _system_for(name), "messages": [{"role": "user", "content": package}]},
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    return "\n".join(x.get("text", "") for x in d.get("content", []) if x.get("type") == "text"), d.get("id")


def _gemini(name, package, key, model):
    # Keep the API key in a header rather than the URL so failures/logging cannot expose it.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent"
    d = _post(
        url,
        {"systemInstruction": {"parts": [{"text": _system_for(name)}]}, "contents": [{"role": "user", "parts": [{"text": package}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0, "maxOutputTokens": 3000}},
        {"x-goog-api-key": key},
    )
    texts = []
    for cand in d.get("candidates", []):
        texts += [p.get("text", "") for p in cand.get("content", {}).get("parts", []) if p.get("text")]
    return "\n".join(texts), d.get("responseId")


def _chat_compatible(name, url, package, key, model):
    d = _post(url, {"model": model, "messages": [{"role": "system", "content": _system_for(name)}, {"role": "user", "content": package}], "temperature": 0}, {"Authorization": f"Bearer {key}"})
    return d["choices"][0]["message"]["content"], d.get("id")


def _perplexity(name, package, key, model):
    return _chat_compatible(name, "https://api.perplexity.ai/chat/completions", package, key, model)


def _grok(name, package, key, model):
    return _chat_compatible(name, "https://api.x.ai/v1/chat/completions", package, key, model)


ADAPTERS = {"openai": _openai, "anthropic": _anthropic, "gemini": _gemini, "perplexity": _perplexity, "grok": _grok}


def _extract_json_object(text):
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if s.startswith("json"):
            s = s[4:].lstrip()
    try:
        return json.loads(s)
    except json.JSONDecodeError as first:
        decoder = json.JSONDecoder()
        for start in (i for i, ch in enumerate(s) if ch == "{"):
            try:
                obj, _ = decoder.raw_decode(s[start:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
        raise first


def _parse(text):
    obj = _extract_json_object(text)
    if obj.get("verdict") not in {"PASS_WITH_GATES", "HOLD", "REJECT"}:
        raise ValueError("invalid verdict")
    if not isinstance(obj.get("risks"), list) or not isinstance(obj.get("mitigations"), list):
        raise ValueError("risks and mitigations must be arrays")
    if not isinstance(obj.get("counsel_questions", []), list):
        raise ValueError("counsel_questions must be an array")
    confidence = obj.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if not isinstance(obj.get("rationale"), str):
        raise ValueError("rationale must be a string")
    return obj


def _run_member(name, cfg, package, live):
    key = os.getenv(cfg["key"])
    model = os.getenv(cfg["model_env"]) or cfg["model"]
    base = {"provider": name, "model_requested": model, "seat_focus": SEAT_FOCUS[name], "participated": False}
    if not key:
        return name, {**base, "status": "NOT_CONFIGURED"}
    if not live:
        return name, {**base, "status": "LIVE_CALL_NOT_AUTHORIZED"}
    try:
        text, request_id = ADAPTERS[name](name, package, key, model)
        analysis = _parse(text)
        return name, {**base, "status": "SUCCESS", "participated": True, "request_id": request_id, "received_at": int(time.time()), "response_sha256": hashlib.sha256(text.encode()).hexdigest(), "analysis": analysis}
    except Exception as e:
        return name, {**base, "status": "ERROR", "error_type": type(e).__name__, "error": str(e)[:500]}


def _deterministic_synthesis(members):
    successful = [m for m in members.values() if m.get("participated")]
    verdicts = [m["analysis"]["verdict"] for m in successful]
    counts = {v: verdicts.count(v) for v in ("PASS_WITH_GATES", "HOLD", "REJECT")}
    if not verdicts:
        decision = "HOLD_NO_VERIFIED_RESPONSES"
    elif counts["REJECT"]:
        decision = "REJECT_PRESENT"
    elif counts["HOLD"]:
        decision = "HOLD_PRESENT"
    elif len(successful) == len(PROVIDERS):
        decision = "PASS_WITH_GATES_ALL_SEATS"
    else:
        decision = "HOLD_INCOMPLETE_COUNCIL"
    return {"decision_rule": "Any REJECT blocks; otherwise any HOLD blocks; PASS requires all configured council seats to return PASS_WITH_GATES.", "decision": decision, "verdict_counts": counts, "unanimous": bool(verdicts) and len(set(verdicts)) == 1, "all_five_participated": len(successful) == len(PROVIDERS)}


def run(package, out_path="product-discovery/run-output/council-latest.json", live=None):
    live = (os.getenv("COUNCIL_LIVE_CALLS") == "1") if live is None else live
    report = {"schema": "jakeai.council.v3", "created_at": int(time.time()), "advisory_only": True, "package_sha256": hashlib.sha256(package.encode()).hexdigest(), "live_calls_authorized": bool(live), "independence_rule": "Each provider receives only the same frozen package plus its seat focus; no provider receives peer responses before voting.", "members": {}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(PROVIDERS)) as pool:
        futures = [pool.submit(_run_member, name, cfg, package, live) for name, cfg in PROVIDERS.items()]
        for future in concurrent.futures.as_completed(futures):
            name, result = future.result()
            report["members"][name] = result
    report["members"] = {name: report["members"][name] for name in PROVIDERS}
    successful = [v for v in report["members"].values() if v.get("participated")]
    report["participating_count"] = len(successful)
    report["status"] = "COUNCIL_COMPLETE" if len(successful) == len(PROVIDERS) else ("COUNCIL_PARTIAL" if successful else "HOLD_NO_VERIFIED_RESPONSES")
    report["synthesis"] = _deterministic_synthesis(report["members"])
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("usage: multimodel_council.py <review-package>")
    package = Path(sys.argv[1]).read_text(encoding="utf-8")
    print(json.dumps(run(package), indent=2))
