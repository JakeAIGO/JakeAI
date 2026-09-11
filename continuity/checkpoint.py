#!/usr/bin/env python3
"""Advance JakeAI-owned continuity state after a completed work unit.

This tool is provider-neutral and standard-library only. It updates only the
portable continuity state; it does not call external AI providers or bypass
provider usage limits.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from router import DEFAULT_STATE, validate_state


def checkpoint_state(path: Path, source: str, next_action: str | None = None) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)

    validate_state(state)

    checkpoint = state.setdefault("checkpoint", {})
    checkpoint["version"] = int(checkpoint.get("version", 0)) + 1
    checkpoint["created_at"] = datetime.now(timezone.utc).isoformat()
    checkpoint["source"] = source

    if next_action is not None:
        cleaned = next_action.strip()
        if not cleaned:
            raise ValueError("next_action cannot be blank")
        state["next_action"] = cleaned

    validate_state(state)
    return state


def atomic_write(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance JakeAI continuity checkpoint")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--source", required=True, help="Verified source/reason for this checkpoint")
    parser.add_argument("--next-action", help="Replacement next action after completed work")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print without writing")
    args = parser.parse_args()

    state = checkpoint_state(args.state, args.source, args.next_action)
    if args.dry_run:
        print(json.dumps(state, indent=2))
        return 0

    atomic_write(args.state, state)
    print(f"Checkpoint v{state['checkpoint']['version']} written: {args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
