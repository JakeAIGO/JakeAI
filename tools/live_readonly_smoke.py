"""Read-only production smoke checks for JakeAIOfficial.com.

No POST requests, no checkout creation, no deployment writes, and no secrets.
This script only verifies public GET surfaces and status semantics.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "https://www.jakeaiofficial.com"
CHECKS = [
    ("/", {200}),
    ("/health", {200}),
    ("/llms.txt", {200}),
    ("/.well-known/agent.json", {200}),
    ("/docs", {200}),
    ("/openapi.json", {200}),
    ("/terms.html", {200}),
    ("/privacy.html", {200}),
    ("/refunds.html", {200}),
]


def get(path: str):
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": "JakeAI-Baseline-Smoke/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.headers.get("content-type", ""), resp.read(200_000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", ""), exc.read(200_000)


def main() -> int:
    failures: list[str] = []
    bodies: dict[str, bytes] = {}
    for path, allowed in CHECKS:
        try:
            status, content_type, body = get(path)
            bodies[path] = body
            print(f"{path}: {status} {content_type}")
            if status not in allowed:
                failures.append(f"{path}: expected {sorted(allowed)}, got {status}")
        except Exception as exc:  # network/DNS/TLS failure is evidence, not a false pass
            failures.append(f"{path}: request failed: {exc}")

    # Machine-readable sanity checks if reachable.
    if "/health" in bodies:
        try:
            health = json.loads(bodies["/health"].decode("utf-8"))
            if health.get("status") != "healthy":
                failures.append("/health: status field is not 'healthy'")
        except Exception as exc:
            failures.append(f"/health: invalid JSON: {exc}")

    if "/.well-known/agent.json" in bodies:
        try:
            card = json.loads(bodies["/.well-known/agent.json"].decode("utf-8"))
            if not card.get("name"):
                failures.append("agent card: missing name")
            if "active_catalog" not in card:
                failures.append("agent card: missing active_catalog")
        except Exception as exc:
            failures.append(f"agent card: invalid JSON: {exc}")

    if "/llms.txt" in bodies:
        text = bodies["/llms.txt"].decode("utf-8", errors="replace")
        if "JakeAI" not in text:
            failures.append("llms.txt: missing JakeAI identifier")
        if "Product ID:" not in text:
            failures.append("llms.txt: missing product catalog entries")

    if failures:
        print("LIVE READ-ONLY SMOKE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("LIVE READ-ONLY SMOKE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
