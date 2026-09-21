from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE_URL = os.environ.get(
    "MISSION_DISPATCHER_URL",
    "https://agent-commerce-network-production.up.railway.app",
).rstrip("/")
WORKER_TOKEN = os.environ.get("MISSION_WORKER_TOKEN", "").strip()
CONCURRENCY = max(1, min(6, int(os.environ.get("MISSION_INVESTIGATION_CONCURRENCY", "2"))))
POLL_SECONDS = max(3, min(60, int(os.environ.get("MISSION_INVESTIGATION_POLL_SECONDS", "8"))))
LEASE_SECONDS = max(120, min(900, int(os.environ.get("MISSION_INVESTIGATION_LEASE_SECONDS", "300"))))
HOST = socket.gethostname()


def api(path: str, payload: dict, timeout: int = 70) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-JakeAI-Worker-Token": WORKER_TOKEN,
            "User-Agent": "JakeAI-Mission-Investigator/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_release(worker_id: str, mission: dict, lease: dict, *, next_status: str, note: str, result: dict | None = None, error: str = "") -> None:
    api(
        "/v1/missions/release",
        {
            "worker_id": worker_id,
            "mission_id": mission["id"],
            "lease_token": lease["token"],
            "lease_seconds": LEASE_SECONDS,
            "next_status": next_status,
            "note": note[:1200],
            "error": error[:1200],
            "result": result,
        },
        timeout=25,
    )


def investigate_one(worker_id: str, mission: dict, lease: dict) -> None:
    try:
        response = api(
            "/v1/missions/investigate",
            {"mission": mission},
            timeout=70,
        )
        report = response.get("investigation") or {}
        route = str(report.get("recommended_route") or "ready_for_review").strip()
        if route not in {"building", "needs_information", "ready_for_review"}:
            route = "ready_for_review"

        runtime = response.get("runtime") or {}
        result = {
            "investigation": report,
            "investigation_runtime": {
                "model": runtime.get("model"),
                "response_id": runtime.get("response_id"),
                "input_tokens": int(runtime.get("input_tokens") or 0),
                "output_tokens": int(runtime.get("output_tokens") or 0),
                "external_evidence_used": bool(runtime.get("external_evidence_used")),
                "evidence_adapter": runtime.get("evidence_adapter"),
                "search_result_count": int(runtime.get("search_result_count") or 0),
                "fetched_page_count": int(runtime.get("fetched_page_count") or 0),
            },
        }
        note = (
            "Autonomous investigation completed. "
            + str(report.get("route_reason") or report.get("summary") or "Human review gate remains active.")
        )
        safe_release(
            worker_id,
            mission,
            lease,
            next_status=route,
            note=note,
            result=result,
        )
        print(
            f"{worker_id} investigated {mission['id']} -> {route} "
            + f"evidence={bool(runtime.get('external_evidence_used'))} "
            + f"search={int(runtime.get('search_result_count') or 0)} "
            + f"fetch={int(runtime.get('fetched_page_count') or 0)}",
            flush=True,
        )
    except Exception as exc:
        detail = str(exc)[:900]
        try:
            safe_release(
                worker_id,
                mission,
                lease,
                next_status="ready_for_review",
                note="Autonomous investigation could not complete safely; routed to human review without external action.",
                result={
                    "investigation": {
                        "status": "runtime_error",
                        "recommended_route": "ready_for_review",
                        "route_reason": "Investigation runtime did not complete safely.",
                        "confidence": "low",
                    }
                },
                error=detail,
            )
        except Exception as release_exc:
            print(f"{worker_id} release failure {mission.get('id')}: {release_exc}", flush=True)
        print(f"{worker_id} investigation error {mission.get('id')}: {detail}", flush=True)


def worker_loop(slot: int) -> None:
    worker_id = f"investigate-{HOST}-{slot}"
    print(f"{worker_id} online", flush=True)
    while True:
        try:
            claim = api(
                "/v1/missions/claim",
                {
                    "worker_id": worker_id,
                    "statuses": ["investigating"],
                    "lease_seconds": LEASE_SECONDS,
                },
                timeout=25,
            )
            if not claim.get("claimed"):
                time.sleep(POLL_SECONDS)
                continue

            investigate_one(worker_id, claim["mission"], claim["lease"])
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                try:
                    body = exc.read().decode("utf-8")
                except Exception:
                    body = ""
                print(f"{worker_id} HTTP {exc.code}: {body[:700]}", flush=True)
            time.sleep(POLL_SECONDS)
        except Exception as exc:
            print(f"{worker_id} error: {exc}", flush=True)
            time.sleep(POLL_SECONDS)


def main() -> None:
    if not WORKER_TOKEN:
        raise SystemExit("MISSION_WORKER_TOKEN is required")
    print(
        f"JakeAI autonomous investigation worker starting: concurrency={CONCURRENCY} base={BASE_URL}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for slot in range(CONCURRENCY):
            pool.submit(worker_loop, slot + 1)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
