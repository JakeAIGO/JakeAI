import unittest

from engine import RelayEngine, RelayEvent


class RelayEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = RelayEngine()
        self.common = dict(
            required_fields={"name", "email"},
            destination="synthetic-crm",
            field_map={"name": "contact_name", "email": "email"},
            allowed_actions={"upsert_record", "send_external_message"},
        )

    def event(self, **overrides):
        data = dict(
            event_id="evt-1",
            source="synthetic-form",
            subject_id="lead-123",
            payload={"name": "Ada", "email": "ada@example.invalid"},
            requested_action="upsert_record",
            permissions={"action:upsert_record"},
        )
        data.update(overrides)
        return RelayEvent(**data)

    def test_happy_path_transforms_and_completes(self):
        result = self.engine.process(self.event(), **self.common)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.transformed["contact_name"], "Ada")
        self.assertEqual(result.destination, "synthetic-crm")
        self.assertTrue(result.audit_id)

    def test_duplicate_is_idempotent(self):
        first = self.engine.process(self.event(), **self.common)
        second = self.engine.process(self.event(), **self.common)
        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(len(self.engine.audit_log), 1)

    def test_missing_required_field_routes_to_human_review(self):
        result = self.engine.process(
            self.event(payload={"name": "Ada", "email": ""}), **self.common
        )
        self.assertEqual(result.status, "human_review")
        self.assertIn("email", result.reason)

    def test_action_without_permission_is_blocked(self):
        result = self.engine.process(self.event(permissions=set()), **self.common)
        self.assertEqual(result.status, "blocked")
        self.assertIn("permission", result.reason)

    def test_unapproved_external_message_waits_for_human(self):
        result = self.engine.process(
            self.event(
                requested_action="send_external_message",
                permissions={"action:send_external_message"},
            ),
            **self.common,
        )
        self.assertEqual(result.status, "awaiting_approval")

    def test_approved_external_message_is_only_prepared(self):
        result = self.engine.process(
            self.event(
                requested_action="send_external_message",
                permissions={"action:send_external_message"},
                approval_token="synthetic-human-approval",
            ),
            **self.common,
        )
        self.assertEqual(result.status, "prepared")
        self.assertEqual(result.action, "send_external_message")

    def test_disallowed_action_fails_closed(self):
        result = self.engine.process(
            self.event(
                requested_action="spend_money",
                permissions={"action:spend_money"},
                approval_token="synthetic-human-approval",
            ),
            **self.common,
        )
        self.assertEqual(result.status, "blocked")


if __name__ == "__main__":
    unittest.main()
