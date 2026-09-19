"""Persistent idempotency storage for Move the Damn Data.

Reference implementation only. Uses an atomic JSON file to preserve processed-event
results across process restarts. No network calls or external side effects.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class JsonIdempotencyStore:
    """Small fail-closed file-backed processed-event store.

    The store persists only normalized RelayResult-compatible fields. Writes are atomic
    on the local filesystem via os.replace. Corrupt/unreadable state raises instead of
    silently treating events as unseen, because replaying an already-completed action is
    less safe than stopping for operator review.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write({})
        self._read_all()  # fail closed on corrupt initial state

    def get(self, event_id: str) -> Optional[Dict[str, Any]]:
        state = self._read_all()
        value = state.get(event_id)
        return dict(value) if isinstance(value, dict) else None

    def put(self, event_id: str, result: Mapping[str, Any]) -> None:
        state = self._read_all()
        if event_id in state:
            return
        state[event_id] = dict(result)
        self._atomic_write(state)

    def _read_all(self) -> Dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("idempotency state unavailable or corrupt") from exc
        if not isinstance(data, dict):
            raise RuntimeError("idempotency state must be an object")
        return data

    def _atomic_write(self, data: Mapping[str, Any]) -> None:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
        fd, tmp_name = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
