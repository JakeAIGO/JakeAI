"""Durable fail-closed state for approvals and uncertain external actions.

Private reference implementation only. No network calls or external execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class DurableStateError(RuntimeError):
    pass


class DurableState:
    """Atomic JSON state store for consumed approvals and recovery records."""

    VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data = self._load()

    def _empty(self) -> dict[str, Any]:
        return {"version": self.VERSION, "consumed_approvals": [], "recoveries": {}}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DurableStateError("durable state unreadable; fail closed") from exc
        if not isinstance(data, dict) or data.get("version") != self.VERSION:
            raise DurableStateError("durable state schema invalid; fail closed")
        if not isinstance(data.get("consumed_approvals"), list) or not isinstance(data.get("recoveries"), dict):
            raise DurableStateError("durable state content invalid; fail closed")
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(self._data, sort_keys=True, separators=(",", ":"))
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            finally:
                raise DurableStateError("durable state write failed; fail closed") from exc

    @staticmethod
    def approval_key(grant_id: str, nonce: str) -> str:
        if not grant_id or not nonce:
            raise DurableStateError("approval identity missing")
        return f"{grant_id}:{nonce}"

    def approval_consumed(self, grant_id: str, nonce: str) -> bool:
        return self.approval_key(grant_id, nonce) in self._data["consumed_approvals"]

    def consume_approval(self, grant_id: str, nonce: str) -> bool:
        key = self.approval_key(grant_id, nonce)
        if key in self._data["consumed_approvals"]:
            return False
        self._data["consumed_approvals"].append(key)
        self._save()
        return True

    def recovery(self, event_id: str) -> dict[str, Any] | None:
        value = self._data["recoveries"].get(event_id)
        return dict(value) if isinstance(value, dict) else None

    def put_recovery(self, event_id: str, record: dict[str, Any]) -> None:
        if not event_id or not isinstance(record, dict):
            raise DurableStateError("recovery record invalid")
        self._data["recoveries"][event_id] = dict(record)
        self._save()
