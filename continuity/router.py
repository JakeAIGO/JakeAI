#!/usr/bin/env python3
"""JakeAI model-continuity handoff generator.

Standard-library only. This does not call any model provider and does not bypass
provider usage limits. It turns JakeAI-owned state, recent journal events, and
capacity status into a portable handoff.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / "current_state.json"
DEFAULT_JOURNAL = ROOT / "events.jsonl"
DEFAULT_CAPACITY = ROOT / "capacity.json"
OUT_DIR = ROOT / "out"
ALLOWED_STATUSES = {
    "verified_live",
    "verified_staged",
    "pending",
    "blocked",
    "proposed",
}
REQUIRED_TOP_LEVEL = {
    "project",
    "checkpoint",
    "status_legend",
    "verified_facts",
    "active_work",
    "next_action",
    "constraints",
}


def load_state(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    validate_state(state)
    return state


def validate_state(state: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL - state.keys()
    if missing:
        raise ValueError(f"Missing required keys: {', '.join(sorted(missing))}")

    for collection_name in ("verified_facts", "active_work"):
        collection = state.get(collection_name)
        if not isinstance(collection, list):
            raise ValueError(f"{collection_name} must be a list")
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                raise ValueError(f"{collection_name}[{index}] must be an object")
            for key in ("id", "summary", "status"):
                if not item.get(key):
                    raise ValueError(f"{collection_name}[{index}] missing {key}")
            if item["status"] not in ALLOWED_STATUSES:
                raise ValueError(
                    f"{collection_name}[{index}] has invalid status: {item['status']}"
                )

    if not isinstance(state.get("constraints"), list):
        raise ValueError("constraints must be a list")


def load_recent_events(path: Path, limit: int = 12) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid journal JSON on line {line_number}") from exc
            if event.get("status") not in ALLOWED_STATUSES:
                raise ValueError(f"Invalid journal status on line {line_number}: {event.get('status')}")
            events.append(event)
    return events[-max(0, limit):]


def load_capacity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("capacity file must contain a JSON object")
    return data


def item_lines(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(f"- [{item['status']}] **{item['id']}** — {item['summary']}")
        for evidence in item.get("evidence", []):
            lines.append(f"  - Evidence: {evidence}")
    return lines or ["- None recorded."]


def event_lines(events: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for event in events:
        stamp = event.get("timestamp", "unknown-time")
        status = event.get("status", "unknown")
        kind = event.get("event_type", "event")
        summary = event.get("summary", "No summary")
        lines.append(f"- {stamp} [{status}] **{kind}** — {summary}")
        for evidence in event.get("evidence", []):
            lines.append(f"  - Evidence: {evidence}")
    return lines or ["- No recent events recorded."]


def capacity_lines(capacity: dict[str, Any]) -> list[str]:
    if not capacity:
        return ["- Capacity registry unavailable."]
    lines = [f"- Policy: {capacity.get('policy', 'unknown')}"]
    lines.append(
        f"- Paid capacity requires explicit approval: {capacity.get('paid_capacity_requires_explicit_approval', 'unknown')}"
    )
    lines.append(f"- Circumvention prohibited: {capacity.get('circumvention_prohibited', 'unknown')}")
    signals = capacity.get("signals", {})
    if isinstance(signals, dict):
        for key, value in signals.items():
            lines.append(f"- {key}: {value}")
    return lines


def render_handoff(
    state: dict[str, Any],
    recent_events: list[dict[str, Any]] | None = None,
    capacity: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    checkpoint = state.get("checkpoint", {})
    notes = state.get("handoff_notes", [])
    recent_events = recent_events or []
    capacity = capacity or {}

    sections = [
        "# JakeAI Portable Model Handoff",
        "",
        f"Generated: {now}",
        f"Project: {state['project']}",
        f"State version: {checkpoint.get('version', 'unknown')}",
        f"State source: {checkpoint.get('source', 'unknown')}",
        "",
        "## Resume instruction",
        "Treat this file as a continuation checkpoint, not as proof that every referenced system is live. "
        "Preserve status labels exactly. Verify external reality before consequential writes or public claims.",
        "",
        "## Core operating principle",
        "**The model is not the memory. The model is not the project. JakeAI owns the project state; models are interchangeable compute.**",
        "",
        "## Verified facts",
        *item_lines(state["verified_facts"]),
        "",
        "## Active work",
        *item_lines(state["active_work"]),
        "",
        "## Recent continuity events",
        *event_lines(recent_events),
        "",
        "## Capacity status",
        *capacity_lines(capacity),
        "",
        "## Next action",
        state["next_action"],
        "",
        "## Constraints / guardrails",
        *[f"- {constraint}" for constraint in state["constraints"]],
        "",
        "## Additional handoff notes",
        *([f"- {note}" for note in notes] if notes else ["- None."]),
        "",
        "## Next worker response contract",
        "1. Read this handoff before proposing changes.",
        "2. Start at `Next action` unless newer verified evidence supersedes it.",
        "3. Never upgrade a status without evidence.",
        "4. Keep secrets and proprietary internals out of portable summaries.",
        "5. Record completed work back into JakeAI-owned state and journal before another model/session switch.",
        "6. Respect capacity policy; do not evade limits or authorize paid capacity without explicit owner approval.",
        "",
    ]
    return "\n".join(sections)


def write_handoff(
    state: dict[str, Any],
    output: Path | None = None,
    recent_events: list[dict[str, Any]] | None = None,
    capacity: dict[str, Any] | None = None,
) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = OUT_DIR / f"handoff-{stamp}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_handoff(state, recent_events, capacity), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="JakeAI model continuity router")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate continuity state")
    validate_parser.add_argument("--state", type=Path, default=DEFAULT_STATE)

    handoff_parser = subparsers.add_parser("handoff", help="Generate portable handoff Markdown")
    handoff_parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    handoff_parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    handoff_parser.add_argument("--capacity", type=Path, default=DEFAULT_CAPACITY)
    handoff_parser.add_argument("--recent-events", type=int, default=12)
    handoff_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    state = load_state(args.state)

    if args.command == "validate":
        print(f"OK: {args.state}")
        return 0

    recent_events = load_recent_events(args.journal, args.recent_events)
    capacity = load_capacity(args.capacity)
    output = write_handoff(state, args.output, recent_events, capacity)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
