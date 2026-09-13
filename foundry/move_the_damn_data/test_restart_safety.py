from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import RelayEngine, RelayEvent
from idempotency_store import JsonIdempotencyStore


def event(event_id: str = "evt-restart") -> RelayEvent:
    return RelayEvent(
        event_id=event_id,
        source="synthetic_form",
        subject_id="lead-restart",
        payload={"name": "Ada", "email": "ada@example.invalid"},
        requested_action="create_record",
        permissions={"action:create_record"},
    )


def process(engine: RelayEngine, e: RelayEvent):
    return engine.process(
        e,
        required_fields={"name", "email"},
        destination="synthetic_crm",
        field_map={"name": "contact_name", "email": "contact_email"},
        allowed_actions={"create_record"},
    )


def test_completed_event_remains_duplicate_after_engine_restart(tmp_path: Path):
    state = tmp_path / "idempotency.json"
    first_engine = RelayEngine(idempotency_store=JsonIdempotencyStore(state))
    first = process(first_engine, event())
    assert first.status == "completed"

    restarted_engine = RelayEngine(idempotency_store=JsonIdempotencyStore(state))
    replay = process(restarted_engine, event())
    assert replay.status == "duplicate"
    assert replay.audit_id == first.audit_id
    assert replay.transformed == first.transformed
    assert len(restarted_engine.audit_log) == 0


def test_two_fresh_engine_instances_share_processed_state(tmp_path: Path):
    state = tmp_path / "shared.json"
    one = RelayEngine(idempotency_store=JsonIdempotencyStore(state))
    two = RelayEngine(idempotency_store=JsonIdempotencyStore(state))

    assert process(one, event("evt-shared")).status == "completed"
    assert process(two, event("evt-shared")).status == "duplicate"


def test_corrupt_persistent_state_fails_closed(tmp_path: Path):
    state = tmp_path / "bad.json"
    state.write_text("{not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unavailable or corrupt"):
        JsonIdempotencyStore(state)


def test_invalid_persisted_result_fails_closed(tmp_path: Path):
    state = tmp_path / "invalid.json"
    state.write_text(json.dumps({"evt-bad": {"unexpected": "shape"}}), encoding="utf-8")
    engine = RelayEngine(idempotency_store=JsonIdempotencyStore(state))
    with pytest.raises(RuntimeError, match="persisted idempotency record is invalid"):
        process(engine, event("evt-bad"))


def test_store_does_not_overwrite_first_result(tmp_path: Path):
    state = tmp_path / "first-write-wins.json"
    store = JsonIdempotencyStore(state)
    store.put("evt-1", {"status": "completed", "event_id": "evt-1"})
    store.put("evt-1", {"status": "prepared", "event_id": "evt-1"})
    assert store.get("evt-1")["status"] == "completed"
