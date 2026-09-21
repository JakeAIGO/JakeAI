from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get(
    "MISSION_DISPATCHER_URL",
    "https://agent-commerce-network-production.up.railway.app",
).rstrip("/")
WORKER_TOKEN = os.environ.get("MISSION_WORKER_TOKEN", "").strip()
POLL_SECONDS = max(4, min(60, int(os.environ.get("MISSION_TEST_POLL_SECONDS", "8"))))
LEASE_SECONDS = max(120, min(900, int(os.environ.get("MISSION_TEST_LEASE_SECONDS", "240"))))
HOST = socket.gethostname()


def api(path: str, payload: dict, timeout: int = 45) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-JakeAI-Worker-Token": WORKER_TOKEN,
            "User-Agent": "JakeAI-Mission-Static-Validator/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def worker_loop(slot: int = 1) -> None:
    worker_id = f"test-{HOST}-{slot}"
    print(f"{worker_id} online", flush=True)
    while True:
        try:
            claim = api(
                "/v1/missions/claim",
                {
                    "worker_id": worker_id,
                    "statuses": ["testing"],
                    "lease_seconds": LEASE_SECONDS,
                },
                timeout=25,
            )
            if not claim.get("claimed"):
                time.sleep(POLL_SECONDS)
                continue

            mission = claim["mission"]
            lease = claim["lease"]
            try:
                tested = api("/v1/missions/test-build", {"mission": mission}, timeout=45)
                artifact = tested.get("artifact") or {}
                validation = artifact.get("validation") or {}
                result = {
                    "build_validation": {
                        "artifact_id": artifact.get("artifact_id"),
                        "status": validation.get("status") or "needs_human_review",
                        "errors": validation.get("errors") or [],
                        "warnings": validation.get("warnings") or [],
                        "file_count": int(validation.get("file_count") or 0),
                        "total_chars": int(validation.get("total_chars") or 0),
                        "checks": validation.get("checks") or [],
                        "executed_code": False,
                        "external_actions_executed": False,
                        "deployed": False,
                    }
                }
                api(
                    "/v1/missions/release",
                    {
                        "worker_id": worker_id,
                        "mission_id": mission["id"],
                        "lease_token": lease["token"],
                        "lease_seconds": LEASE_SECONDS,
                        "next_status": "ready_for_review",
                        "note": "Static artifact validation completed. Prototype remains undeployed and requires human review.",
                        "result": result,
                    },
                    timeout=25,
                )
                print(
                    f"{worker_id} validated {mission['id']} -> ready_for_review "
                    + f"status={validation.get('status')} errors={len(validation.get('errors') or [])} "
                    + f"warnings={len(validation.get('warnings') or [])}",
                    flush=True,
                )
            except Exception as exc:
                detail = str(exc)[:900]
                try:
                    api(
                        "/v1/missions/release",
                        {
                            "worker_id": worker_id,
                            "mission_id": mission["id"],
                            "lease_token": lease["token"],
                            "lease_seconds": LEASE_SECONDS,
                            "next_status": "ready_for_review",
                            "note": "Static validation could not complete safely; routed to human review without executing or deploying the artifact.",
                            "error": detail,
                            "result": {
                                "build_validation": {
                                    "status": "runtime_error",
                                    "executed_code": False,
                                    "external_actions_executed": False,
                                    "deployed": False,
                                }
                            },
                        },
                        timeout=25,
                    )
                except Exception as release_exc:
                    print(f"{worker_id} release failure {mission.get('id')}: {release_exc}", flush=True)
                print(f"{worker_id} validation error {mission.get('id')}: {detail}", flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                print(f"{worker_id} HTTP {exc.code}", flush=True)
            time.sleep(POLL_SECONDS)
        except Exception as exc:
            print(f"{worker_id} error: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
