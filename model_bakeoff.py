"""JakeAI provider bake-off harness.

Runs bounded, text-only evaluation tasks against explicitly configured model
providers. It never enables tools, deployment, publication, purchases, or any
other external action. Live calls require --live.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List

from model_router import ModelRouterError, execution_configured, run_text, selected_model

CASES: List[Dict[str, Any]] = [
    {
        "id": "exact",
        "instructions": "Follow the user instruction exactly.",
        "prompt": "Reply with exactly JAKEAI_ROUTER_OK",
        "check": "exact",
        "expected": "JAKEAI_ROUTER_OK",
    },
    {
        "id": "json",
        "instructions": "Return valid JSON only. No markdown fences.",
        "prompt": 'Return {"status":"ok","count":3} exactly as a JSON object.',
        "check": "json",
    },
    {
        "id": "direct_research",
        "instructions": "Produce a concise structured research brief. Clearly label unknowns. Do not invent sources.",
        "prompt": "A small manufacturer wants to reduce quoting time. Give three workflow stages, two measurable KPIs, and one risk.",
        "check": "nonempty",
    },
    {
        "id": "direct_site",
        "instructions": "Produce a staged website implementation brief. Do not claim deployment. Explicitly mark release as awaiting human approval.",
        "prompt": "Add a model-provider status panel showing provider, model, latency, and last health check.",
        "check": "approval",
    },
    {
        "id": "structured_plan",
        "instructions": "Return JSON only with keys steps (array) and stop_conditions (array). Do not call tools.",
        "prompt": "Plan a safe five-step code review workflow with a hard stop if repeated actions are detected.",
        "check": "json",
    },
]


def _evaluate(case: Dict[str, Any], text: str) -> bool:
    kind = case["check"]
    if kind == "exact":
        return text.strip() == case["expected"]
    if kind == "json":
        try:
            obj = json.loads(text)
            return isinstance(obj, dict)
        except Exception:
            return False
    if kind == "approval":
        lowered = text.lower()
        return bool(text.strip()) and "approval" in lowered
    return bool(text.strip())


def run_provider(provider: str, live: bool) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "provider": provider,
        "configured": execution_configured(provider),
        "model": None,
        "live": bool(live),
        "cases": [],
    }
    try:
        report["model"] = selected_model(provider)
    except Exception as exc:
        report["error"] = str(exc)
        return report

    if not live:
        report["status"] = "READY_NO_LIVE_CALLS" if report["configured"] else "NOT_CONFIGURED"
        return report
    if not report["configured"]:
        report["status"] = "NOT_CONFIGURED"
        return report

    for case in CASES:
        started = time.perf_counter()
        row = {"id": case["id"]}
        try:
            result = run_text(
                case["prompt"],
                case["instructions"],
                provider=provider,
                model=report["model"],
                max_output_tokens=1600,
            )
            row.update(
                {
                    "ok": _evaluate(case, result["text"]),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "response_id": result["response_id"],
                }
            )
        except ModelRouterError as exc:
            row.update({"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
        report["cases"].append(row)

    report["passed"] = sum(1 for row in report["cases"] if row.get("ok"))
    report["total"] = len(report["cases"])
    report["status"] = "COMPLETE" if report["passed"] == report["total"] else "PARTIAL"
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", default="openai,mimo", help="Comma-separated providers")
    parser.add_argument("--live", action="store_true", help="Authorize bounded provider API calls")
    parser.add_argument("--out", default="", help="Optional JSON output path")
    args = parser.parse_args()

    providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]
    report = {
        "schema": "jakeai.model-bakeoff.v1",
        "tool_execution": False,
        "external_actions": False,
        "providers": [run_provider(p, args.live) for p in providers],
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
