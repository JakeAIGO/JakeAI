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
POLL_SECONDS = max(4, min(60, int(os.environ.get("MISSION_BUILD_POLL_SECONDS", "8"))))
LEASE_SECONDS = max(180, min(900, int(os.environ.get("MISSION_BUILD_LEASE_SECONDS", "420"))))
HOST = socket.gethostname()


def api(path: str, payload: dict, timeout: int = 70) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-JakeAI-Worker-Token": WORKER_TOKEN,
            "User-Agent": "JakeAI-Mission-Builder/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def worker_loop(slot: int = 1) -> None:
    worker_id = f"build-{HOST}-{slot}"
    print(f"{worker_id} online", flush=True)
    while True:
        try:
            claim = api(
                "/v1/missions/claim",
                {
                    "worker_id": worker_id,
                    "statuses": ["building"],
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
                built = api("/v1/missions/build", {"mission": mission}, timeout=70)
                artifact = built.get("artifact") or {}
                build = built.get("build") or {}
                result = {
                    "build": {
                        "artifact_id": artifact.get("artifact_id"),
                        "artifact_type": artifact.get("artifact_type"),
                        "title": build.get("title"),
                        "summary": build.get("summary"),
                        "file_count": int(build.get("file_count") or 0),
                        "test_plan": build.get("test_plan") or [],
                        "limitations": build.get("limitations") or [],
                        "approval_requirements": build.get("approval_requirements") or [],
                        "next_step": build.get("next_step") or "",
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
                        "next_status": "testing",
                        "note": "Autonomous bounded prototype package created. No code executed or deployed; routing to static validation.",
                        "result": result,
                    },
                    timeout=25,
                )
                print(
                    f"{worker_id} built {mission['id']} -> testing artifact={artifact.get('artifact_id')}",
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
                            "note": "Autonomous build could not complete safely; routed to human review without deployment.",
                            "error": detail,
                            "result": {
                                "build": {
                                    "status": "runtime_error",
                                    "deployed": False,
                                    "external_actions_executed": False,
                                }
                            },
                        },
                        timeout=25,
                    )
                except Exception as release_exc:
                    print(f"{worker_id} release failure {mission.get('id')}: {release_exc}", flush=True)
                print(f"{worker_id} build error {mission.get('id')}: {detail}", flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                print(f"{worker_id} HTTP {exc.code}", flush=True)
            time.sleep(POLL_SECONDS)
        except Exception as exc:
            print(f"{worker_id} error: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
