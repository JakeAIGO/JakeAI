#!/usr/bin/env python3
"""Regression tests for JakeAI's provider-neutral continuity layer."""

from __future__ import annotations

import copy
import unittest

from router import validate_state, render_handoff


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


if __name__ == "__main__":
    unittest.main()
