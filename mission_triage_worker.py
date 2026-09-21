from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_URL = os.environ.get(
    "MISSION_DISPATCHER_URL",
    "https://agent-commerce-network-production.up.railway.app",
).rstrip("/")
WORKER_TOKEN = os.environ.get("MISSION_WORKER_TOKEN", "").strip()
CONCURRENCY = max(1, min(8, int(os.environ.get("MISSION_WORKER_CONCURRENCY", "4"))))
POLL_SECONDS = max(2, min(60, int(os.environ.get("MISSION_WORKER_POLL_SECONDS", "5"))))
LEASE_SECONDS = max(60, min(900, int(os.environ.get("MISSION_WORKER_LEASE_SECONDS", "180"))))
HOST = socket.gethostname()

STOP = {
    "a","an","and","are","as","at","be","been","being","but","by","can","could","do","does","for","from",
    "get","gets","has","have","how","i","if","in","into","is","it","its","me","my","of","on","or","our",
    "please","should","that","the","their","them","there","this","to","us","want","we","what","when","where",
    "which","who","why","will","with","would","you","your",
}


def words(value: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(w) >= 3 and w not in STOP
    }


def load_capabilities() -> list[dict]:
    root = Path(__file__).resolve().parent
    capabilities = []
    seen = set()

    catalog = root / "catalog.json"
    if catalog.exists():
        try:
            data = json.loads(catalog.read_text(encoding="utf-8"))
            for c in data.get("capabilities", []):
                cid = c.get("id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                capabilities.append(
                    {
                        "id": cid,
                        "name": c.get("name", ""),
                        "category": " ".join(c.get("category", []) or []),
                        "status": c.get("lifecycle_status", ""),
                        "publication": c.get("publication_status", ""),
                        "summary": c.get("summary", ""),
                        "signals": " ".join(c.get("problem_signals", []) or []),
                        "human_url": c.get("human_url"),
                    }
                )
        except Exception as exc:
            print(f"catalog load warning: {exc}", flush=True)

    registry = root / "workflow-registry.json"
    if registry.exists():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            for c in data.get("entries", []):
                cid = c.get("id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                capabilities.append(
                    {
                        "id": cid,
                        "name": c.get("canonical_name", ""),
                        "category": c.get("category", ""),
                        "status": c.get("status", ""),
                        "publication": c.get("website_publication_status", ""),
                        "summary": c.get("distinct_key", "").replace("-", " "),
                        "signals": "",
                        "human_url": None,
                    }
                )
        except Exception as exc:
            print(f"registry load warning: {exc}", flush=True)

    return capabilities


CAPABILITIES = load_capabilities()


def api(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-JakeAI-Worker-Token": WORKER_TOKEN,
            "User-Agent": "JakeAI-Mission-Triage/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def score_capabilities(mission: dict) -> list[dict]:
    signal = mission.get("signal", "")
    outcome = mission.get("outcome", "")
    boundaries = mission.get("boundaries", "")
    triage = mission.get("triage") or {}
    mission_words = words(" ".join((signal, outcome, boundaries)))
    category = str(triage.get("category") or "").lower()

    matches = []
    for cap in CAPABILITIES:
        name_words = words(cap["name"])
        category_words = words(cap["category"])
        signal_words = words(cap["signals"])
        summary_words = words(cap["summary"])

        exact_signal_overlap = len(mission_words & signal_words)
        name_overlap = len(mission_words & name_words)
        category_overlap = len(mission_words & category_words)
        summary_overlap = len(mission_words & summary_words)

        score = (
            exact_signal_overlap * 4
            + name_overlap * 3
            + category_overlap * 2
            + summary_overlap
        )
        if category and category != "general" and category in (cap["category"] or "").lower():
            score += 3
        if cap["status"] in {"production", "working"}:
            score += 1 if score else 0

        if score:
            matches.append(
                {
                    "id": cap["id"],
                    "name": cap["name"],
                    "category": cap["category"],
                    "lifecycle": cap["status"],
                    "publication": cap["publication"],
                    "score": score,
                    "human_url": cap["human_url"],
                }
            )

    matches.sort(key=lambda x: (-x["score"], x["id"]))
    return matches[:5]


def triage_mission(mission: dict) -> tuple[str, dict, str]:
    triage = mission.get("triage") or {}
    missing = list(triage.get("missing") or [])
    signal = str(mission.get("signal") or "").strip()
    outcome = str(mission.get("outcome") or "").strip()
    boundaries = str(mission.get("boundaries") or "").strip()

    if len(signal) < 20 and "problem_detail" not in missing:
        missing.append("problem_detail")
    if len(outcome) < 10 and "desired_outcome" not in missing:
        missing.append("desired_outcome")

    matches = score_capabilities(mission)
    top_score = matches[0]["score"] if matches else 0
    strong_reusable = bool(
        matches
        and top_score >= 10
        and matches[0]["lifecycle"] in {"production", "working"}
    )

    result = {
        "worker": "autonomous-triage-v1",
        "category": triage.get("category") or "general",
        "completeness": "needs_detail" if missing else "ready_for_triage",
        "missing": missing,
        "candidate_capability_matches": matches,
        "strong_existing_capability_candidate": strong_reusable,
        "recommendation": (
            "request_more_information"
            if missing
            else "human_review_existing_capability"
            if strong_reusable
            else "continue_investigation"
        ),
        "guardrails": {
            "outbound_contact": "blocked",
            "public_release": "blocked",
            "purchases": "blocked",
            "human_release_gate": True,
        },
    }

    if missing:
        return (
            "needs_information",
            result,
            "Autonomous triage completed. Mission needs more customer detail before investigation.",
        )
    if strong_reusable:
        top = matches[0]
        return (
            "ready_for_review",
            result,
            f"Autonomous triage found a strong existing capability candidate: {top['id']} {top['name']}. Human review required before any action.",
        )
    return (
        "investigating",
        result,
        "Autonomous triage completed. Mission is sufficiently defined and routed to investigation.",
    )


def worker_loop(slot: int) -> None:
    worker_id = f"triage-{HOST}-{slot}"
    print(f"{worker_id} online; {len(CAPABILITIES)} capabilities loaded", flush=True)

    while True:
        try:
            claim = api(
                "/v1/missions/claim",
                {
                    "worker_id": worker_id,
                    "statuses": ["received"],
                    "lease_seconds": LEASE_SECONDS,
                },
            )
            if not claim.get("claimed"):
                time.sleep(POLL_SECONDS)
                continue

            mission = claim["mission"]
            lease = claim["lease"]
            next_status, result, note = triage_mission(mission)

            released = api(
                "/v1/missions/release",
                {
                    "worker_id": worker_id,
                    "mission_id": mission["id"],
                    "lease_token": lease["token"],
                    "lease_seconds": LEASE_SECONDS,
                    "next_status": next_status,
                    "note": note,
                    "result": result,
                },
            )
            print(
                f"{worker_id} triaged {mission['id']} -> {released['mission']['status']}",
                flush=True,
            )
        except urllib.error.HTTPError as exc:
            if exc.code not in {409}:
                try:
                    body = exc.read().decode("utf-8")
                except Exception:
                    body = ""
                print(f"{worker_id} HTTP {exc.code}: {body[:500]}", flush=True)
            time.sleep(POLL_SECONDS)
        except Exception as exc:
            print(f"{worker_id} error: {exc}", flush=True)
            time.sleep(POLL_SECONDS)


def main() -> None:
    if not WORKER_TOKEN:
        raise SystemExit("MISSION_WORKER_TOKEN is required")
    if not CAPABILITIES:
        print("warning: no capability records loaded; triage will still route complete missions to investigation", flush=True)

    print(
        f"JakeAI autonomous triage worker starting: concurrency={CONCURRENCY} base={BASE_URL}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for slot in range(CONCURRENCY):
            pool.submit(worker_loop, slot + 1)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
