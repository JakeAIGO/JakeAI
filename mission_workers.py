from __future__ import annotations

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

    with ThreadPoolExecutor(max_workers=total) as pool:
        for slot in range(triage_count):
            pool.submit(mission_triage_worker.worker_loop, slot + 1)
        for slot in range(investigation_count):
            pool.submit(mission_investigation_worker.worker_loop, slot + 1)

        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
