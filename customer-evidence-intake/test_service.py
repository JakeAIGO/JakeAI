import unittest
from datetime import datetime, timedelta, timezone

from service import CustomerEvidenceService
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

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(":memory:", raw_retention_days=1)
        self.service = CustomerEvidenceService(self.store)

    def tearDown(self):
        self.store.close()

    def test_submit_screen_persist_count(self):
        r = self.service.submit(SAFE)
        self.assertEqual(r.status, "ACCEPTED")
        self.assertIsNotNone(r.submission_id)
        self.assertEqual(r.recurrence_count, 1)
        self.assertIsNotNone(self.store.get_packet(r.submission_id))

    def test_repeat_increments_recurrence(self):
        first = self.service.submit(SAFE)
        second = self.service.submit(SAFE)
        self.assertEqual(first.recurrence_count, 1)
        self.assertEqual(second.recurrence_count, 2)

    def test_secret_never_persists_or_echoes(self):
        secret = "password=UltraSecret123"
        x = dict(SAFE, evidence_used_by_human=secret)
        r = self.service.submit(x)
        self.assertEqual(r.status, "BLOCKED_SECRET_DETECTED")
        self.assertIsNone(r.submission_id)
        self.assertNotIn("UltraSecret123", r.message)
        rows = self.store.conn.execute("SELECT COUNT(*) FROM evidence_packets").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_sensitive_data_never_persists(self):
        x = dict(SAFE, evidence_used_by_human="4111 1111 1111 1111")
        r = self.service.submit(x)
        self.assertEqual(r.status, "BLOCKED_SENSITIVE_DATA")
        rows = self.store.conn.execute("SELECT COUNT(*) FROM evidence_packets").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_human_review_never_persists(self):
        x = dict(SAFE, normal_automation="Routes patient medical records")
        r = self.service.submit(x)
        self.assertEqual(r.status, "HUMAN_REVIEW")
        rows = self.store.conn.execute("SELECT COUNT(*) FROM evidence_packets").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_rejected_response_does_not_echo_raw_input(self):
        marker = "DO_NOT_ECHO_THIS_MARKER"
        x = dict(SAFE, normal_automation="")
        x["contact"] = marker
        r = self.service.submit(x)
        self.assertEqual(r.status, "REJECTED_INPUT")
        self.assertNotIn(marker, r.message)

    def test_purge_deletes_raw_but_keeps_recurrence(self):
        r = self.service.submit(SAFE)
        packet = self.store.get_packet(r.submission_id)
        sig = packet["recurrence_signature"]
        future = datetime.now(timezone.utc) + timedelta(days=2)
        self.assertEqual(self.service.purge(now=future), 1)
        self.assertIsNone(self.store.get_packet(r.submission_id))
        self.assertEqual(self.store.recurrence_count(sig), 1)

    def test_public_result_contains_no_packet(self):
        result = self.service.public_submit_result(SAFE)
        self.assertNotIn("packet", result)
        self.assertNotIn("evidence_used_by_human", result)
        self.assertEqual(result["status"], "ACCEPTED")

if __name__ == "__main__":
    unittest.main()
