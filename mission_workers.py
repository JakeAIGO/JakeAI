from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

import mission_triage_worker
import mission_investigation_worker


def main() -> None:
    triage_count = mission_triage_worker.CONCURRENCY
    investigation_count = mission_investigation_worker.CONCURRENCY
    total = triage_count + investigation_count

    if not mission_triage_worker.WORKER_TOKEN or not mission_investigation_worker.WORKER_TOKEN:
        raise SystemExit("MISSION_WORKER_TOKEN is required")

    print(
        f"JakeAI mission worker pool starting: triage={triage_count} investigation={investigation_count} total={total}",
        flush=True,
    )

    if os.environ.get("MISSION_INVESTIGATION_STARTUP_TEST", "").strip().lower() in {"1","true","yes","on"}:
        synthetic = {
            "id": "JAI-DIAGNOSTIC-INVESTIGATION",
            "signal": "A bounded internal QA mission needs an investigation plan.",
            "outcome": "Confirm the JakeAI investigation runtime returns structured JSON without external action.",
            "boundaries": "Synthetic QA only. No outreach, publishing, purchasing, deployment, or external action.",
            "status": "investigating",
            "triage": {"category": "ai-operations", "completeness": "ready_for_triage", "missing": [], "priority": "normal"},
            "analysis": {"candidate_capability_matches": []},
        }
        try:
            diag = mission_investigation_worker.api(
                "/v1/missions/investigate",
                {"mission": synthetic},
                timeout=70,
            )
            report = diag.get("investigation") or {}
            print(
                "INVESTIGATION STARTUP DIAGNOSTIC PASSED "
                + f"route={report.get('recommended_route')} confidence={report.get('confidence')} "
                + f"model={(diag.get('runtime') or {}).get('model')}",
                flush=True,
            )
        except Exception as exc:
            print(f"INVESTIGATION STARTUP DIAGNOSTIC FAILED: {exc}", flush=True)

    with ThreadPoolExecutor(max_workers=total) as pool:
        for slot in range(triage_count):
            pool.submit(mission_triage_worker.worker_loop, slot + 1)
        for slot in range(investigation_count):
            pool.submit(mission_investigation_worker.worker_loop, slot + 1)

        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
