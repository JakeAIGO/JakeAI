import unittest
from datetime import datetime, timedelta, timezone

from intake import screen_submission
from storage import EvidenceStore

SAFE = {
    "software_or_ai": "Example CRM",
    "normal_automation": "Copies lead status into a project board",
    "residual_human_intervention": "A coordinator compares failed sync rows and re-enters the missing status",
    "frequency": "about 12 times per week",
    "minutes_per_occurrence": "6",
    "consequence_if_unhandled": "The internal project board is stale until the next review",
    "evidence_used_by_human": "The CRM status and the integration error message",
}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(":memory:", raw_retention_days=30)

    def tearDown(self):
        self.store.close()

    def _packet(self):
        result = screen_submission(SAFE)
        self.assertEqual(result.status, "ACCEPTED")
        return result.packet

    def test_store_and_read_accepted_packet(self):
        packet = self._packet()
        self.store.save_accepted_packet(packet)
        loaded = self.store.get_packet(packet["submission_id"])
        self.assertEqual(loaded["submission_id"], packet["submission_id"])

    def test_recurrence_count_increments_without_copying_raw_row(self):
        first = self._packet()
        second = self._packet()
        self.store.save_accepted_packet(first)
        self.store.save_accepted_packet(second)
        self.assertEqual(self.store.recurrence_count(first["recurrence_signature"]), 2)

    def test_expired_raw_is_deleted_but_recurrence_remains(self):
        packet = self._packet()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.store.save_accepted_packet(packet, now=t0)
        deleted = self.store.purge_expired_raw(now=t0 + timedelta(days=31))
        self.assertEqual(deleted, 1)
        self.assertIsNone(self.store.get_packet(packet["submission_id"]))
        self.assertEqual(self.store.recurrence_count(packet["recurrence_signature"]), 1)

    def test_raw_not_deleted_before_expiration(self):
        packet = self._packet()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.store.save_accepted_packet(packet, now=t0)
        deleted = self.store.purge_expired_raw(now=t0 + timedelta(days=29))
        self.assertEqual(deleted, 0)
        self.assertIsNotNone(self.store.get_packet(packet["submission_id"]))

    def test_rejects_unscreened_packet(self):
        with self.assertRaises(ValueError):
            self.store.save_accepted_packet({"submission_id": "x"})

    def test_rejects_high_consequence_storage(self):
        packet = self._packet()
        packet["safety_class"] = "HIGH_CONSEQUENCE"
        with self.assertRaises(ValueError):
            self.store.save_accepted_packet(packet)

    def test_retention_bounds(self):
        with self.assertRaises(ValueError):
            EvidenceStore(":memory:", raw_retention_days=0)
        with self.assertRaises(ValueError):
            EvidenceStore(":memory:", raw_retention_days=91)


if __name__ == "__main__":
    unittest.main()
