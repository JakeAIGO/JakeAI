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
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_SYSTEM = """You are one independent member of the JakeAI Multi-Model Advisory Council. Analyze only the supplied frozen review package. Do not infer another council member's opinion and do not attempt consensus. Attack weak assumptions. Identify material risks, missing evidence, required mitigations, and questions for qualified counsel or operator verification. Do not claim legal approval. Return JSON only with: verdict (PASS_WITH_GATES|HOLD|REJECT), risks (array), mitigations (array), counsel_questions (array), confidence (0-1), rationale (string)."""

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
    "gemini": {"key": "GEMINI_API_KEY", "model_env": "GEMINI_COUNCIL_MODEL", "model": "gemini-2.5-pro"},
    "perplexity": {"key": "PERPLEXITY_API_KEY", "model_env": "PERPLEXITY_COUNCIL_MODEL", "model": "sonar-pro"},
    "grok": {"key": "XAI_API_KEY", "model_env": "XAI_COUNCIL_MODEL", "model": "grok-4.6"},
}


def _post(url, body, headers):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _system_for(name):
    return f"{BASE_SYSTEM}\n\nSEAT-SPECIFIC FOCUS: {SEAT_FOCUS[name]}"


def _prompt(name, package):
    return f"{_system_for(name)}\n\nFROZEN REVIEW PACKAGE:\n{package}"


def _openai(name, package, key, model):
    d = _post(
        "https://api.openai.com/v1/responses",
        {"model": model, "input": _prompt(name, package), "store": False},
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
        {
            "model": model,
            "max_tokens": 2500,
            "system": _system_for(name),
            "messages": [{"role": "user", "content": package}],
        },
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    return "\n".join(x.get("text", "") for x in d.get("content", []) if x.get("type") == "text"), d.get("id")


def _gemini(name, package, key, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(key, safe='')}"
    d = _post(
        url,
        {
            "systemInstruction": {"parts": [{"text": _system_for(name)}]},
            "contents": [{"role": "user", "parts": [{"text": package}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        {},
    )
    texts = []
    for cand in d.get("candidates", []):
        texts += [p.get("text", "") for p in cand.get("content", {}).get("parts", []) if p.get("text")]
    return "\n".join(texts), d.get("responseId")


def _chat_compatible(name, url, package, key, model):
    d = _post(
        url,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _system_for(name)},
                {"role": "user", "content": package},
            ],
        },
        {"Authorization": f"Bearer {key}"},
    )
    return d["choices"][0]["message"]["content"], d.get("id")


def _perplexity(name, package, key, model):
    return _chat_compatible(name, "https://api.perplexity.ai/chat/completions", package, key, model)


def _grok(name, package, key, model):
    return _chat_compatible(name, "https://api.x.ai/v1/chat/completions", package, key, model)


ADAPTERS = {
    "openai": _openai,
    "anthropic": _anthropic,
    "gemini": _gemini,
    "perplexity": _perplexity,
    "grok": _grok,
}


def _parse(text):
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if s.startswith("json"):
            s = s[4:].lstrip()
    obj = json.loads(s)
    if obj.get("verdict") not in {"PASS_WITH_GATES", "HOLD", "REJECT"}:
        raise ValueError("invalid verdict")
    if not isinstance(obj.get("risks"), list) or not isinstance(obj.get("mitigations"), list):
        raise ValueError("risks and mitigations must be arrays")
    confidence = obj.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return obj


def _run_member(name, cfg, package, live):
    key = os.getenv(cfg["key"])
    model = os.getenv(cfg["model_env"], cfg["model"])
    base = {
        "provider": name,
        "model_requested": model,
        "seat_focus": SEAT_FOCUS[name],
        "participated": False,
    }
    if not key:
        return name, {**base, "status": "NOT_CONFIGURED"}
    if not live:
        return name, {**base, "status": "LIVE_CALL_NOT_AUTHORIZED"}
    try:
        text, request_id = ADAPTERS[name](name, package, key, model)
        analysis = _parse(text)
        return name, {
            **base,
            "status": "SUCCESS",
            "participated": True,
            "request_id": request_id,
            "received_at": int(time.time()),
            "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "analysis": analysis,
        }
    except Exception as e:
        return name, {
            **base,
            "status": "ERROR",
            "error_type": type(e).__name__,
            "error": str(e)[:500],
        }


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
    return {
        "decision_rule": "Any REJECT blocks; otherwise any HOLD blocks; PASS requires all configured council seats to return PASS_WITH_GATES.",
        "decision": decision,
        "verdict_counts": counts,
        "unanimous": bool(verdicts) and len(set(verdicts)) == 1,
        "all_five_participated": len(successful) == len(PROVIDERS),
    }


def run(package, out_path="product-discovery/run-output/council-latest.json", live=None):
    live = (os.getenv("COUNCIL_LIVE_CALLS") == "1") if live is None else live
    digest = hashlib.sha256(package.encode()).hexdigest()
    report = {
        "schema": "jakeai.council.v3",
        "created_at": int(time.time()),
        "advisory_only": True,
        "package_sha256": digest,
        "live_calls_authorized": bool(live),
        "independence_rule": "Each provider receives only the same frozen package plus its seat focus; no provider receives peer responses before voting.",
        "members": {},
    }

    # Parallel calls reduce anchoring-by-order and ensure all seats receive the
    # identical frozen package before any synthesis is performed.
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(PROVIDERS)) as pool:
        futures = [pool.submit(_run_member, name, cfg, package, live) for name, cfg in PROVIDERS.items()]
        for future in concurrent.futures.as_completed(futures):
            name, result = future.result()
            report["members"][name] = result

    # Stable member ordering for reproducible reports.
    report["members"] = {name: report["members"][name] for name in PROVIDERS}
    successful = [v for v in report["members"].values() if v.get("participated")]
    report["participating_count"] = len(successful)
    report["status"] = (
        "COUNCIL_COMPLETE"
        if len(successful) == len(PROVIDERS)
        else ("COUNCIL_PARTIAL" if successful else "HOLD_NO_VERIFIED_RESPONSES")
    )
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
