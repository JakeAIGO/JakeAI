#!/usr/bin/env python3
"""Regression tests for JakeAI's provider-neutral continuity layer."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from router import load_capacity, load_recent_events, render_handoff, validate_state


BASE_STATE = {
    "project": "JakeAI",
    "checkpoint": {"created_at": "2026-09-11T00:00:00Z", "source": "test", "version": 1},
    "status_legend": {},
    "verified_facts": [
        {"id": "repo", "summary": "Repository verified.", "status": "verified_live", "evidence": ["test"]}
    ],
    "active_work": [
        {"id": "continuity", "summary": "Continuity layer staged.", "status": "verified_staged"}
    ],
    "next_action": "Continue testing.",
    "constraints": ["Do not expose secrets."],
}


class ContinuityRouterTests(unittest.TestCase):
    def test_valid_state_passes(self) -> None:
        validate_state(copy.deepcopy(BASE_STATE))

    def test_invalid_status_is_rejected(self) -> None:
        state = copy.deepcopy(BASE_STATE)
        state["active_work"][0]["status"] = "live-ish"
        with self.assertRaises(ValueError):
            validate_state(state)

    def test_missing_required_key_is_rejected(self) -> None:
        state = copy.deepcopy(BASE_STATE)
        del state["next_action"]
        with self.assertRaises(ValueError):
            validate_state(state)

    def test_handoff_preserves_status_and_next_action(self) -> None:
        handoff = render_handoff(copy.deepcopy(BASE_STATE))
        self.assertIn("[verified_live] **repo**", handoff)
        self.assertIn("[verified_staged] **continuity**", handoff)
        self.assertIn("Continue testing.", handoff)
        self.assertIn("models are interchangeable compute", handoff)

    def test_recent_events_are_limited_to_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            events = [
                {"timestamp": f"t{i}", "event_type": "work", "summary": f"event-{i}", "status": "verified_staged", "evidence": [], "worker": "test"}
                for i in range(5)
            ]
            path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
            recent = load_recent_events(path, limit=2)
            self.assertEqual([e["summary"] for e in recent], ["event-3", "event-4"])

    def test_invalid_journal_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(json.dumps({"status": "sort-of-live", "summary": "bad"}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_recent_events(path)

    def test_capacity_and_events_render_in_handoff(self) -> None:
        events = [{
            "timestamp": "2026-09-11T12:00:00Z",
            "event_type": "deploy",
            "summary": "Continuity change staged.",
            "status": "verified_staged",
            "evidence": ["PR #9"],
            "worker": "test",
        }]
        capacity = {
            "policy": "free-first",
            "paid_capacity_requires_explicit_approval": True,
            "circumvention_prohibited": True,
            "signals": {"model_availability": "unknown"},
        }
        handoff = render_handoff(copy.deepcopy(BASE_STATE), events, capacity)
        self.assertIn("## Recent continuity events", handoff)
        self.assertIn("Continuity change staged.", handoff)
        self.assertIn("## Capacity status", handoff)
        self.assertIn("Policy: free-first", handoff)
        self.assertIn("Paid capacity requires explicit approval: True", handoff)
        self.assertIn("Circumvention prohibited: True", handoff)

    def test_capacity_loader_requires_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capacity.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_capacity(path)


if __name__ == "__main__":
    unittest.main()
