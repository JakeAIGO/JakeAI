#!/usr/bin/env python3
"""Append verified work events to JakeAI's continuity journal.

Provider-neutral, standard-library only. The journal is append-only JSONL and is
intended to keep continuity nearly current during long working sessions.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_JOURNAL = ROOT / "events.jsonl"
ALLOWED_STATUSES = {"verified_live", "verified_staged", "pending", "blocked", "proposed"}


def build_event(event_type: str, summary: str, status: str, evidence: list[str], worker: str) -> dict:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    if not summary.strip():
        raise ValueError("summary cannot be blank")
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type.strip(),
        "summary": summary.strip(),
        "status": status,
        "evidence": [item.strip() for item in evidence if item.strip()],
        "worker": worker.strip() or "unknown",
    }


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a JakeAI continuity event")
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--type", required=True, dest="event_type")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUSES))
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--worker", default="unknown")
    args = parser.parse_args()

    event = build_event(args.event_type, args.summary, args.status, args.evidence, args.worker)
    append_event(args.journal, event)
    print(json.dumps(event, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
