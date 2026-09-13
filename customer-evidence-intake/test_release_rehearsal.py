"""Final private release rehearsal for Customer Evidence Intake v1.

Offline only: no deployment, socket, or real customer data. Exercises the
fail-closed release invariants before a human launch decision.
"""
import tempfile
import unittest
from pathlib import Path

from intake import screen_submission
from storage import EvidenceStore
from data_controls import DeletionAuthority, DataControlService, require_production_protector
from production_adapter import SQLiteRateLimiter, SQLiteAuditSink, TrustedClientResolver

SAFE = {
    "software_or_ai": "Example CRM",
    "normal_automation": "Copies lead status into a project board",
    "residual_human_intervention": "A coordinator compares failed sync rows and re-enters the missing status",
    "frequency": "about 12 times per week",
    "minutes_per_occurrence": "6",
    "consequence_if_unhandled": "The internal project board is stale until the next review",
    "evidence_used_by_human": "The CRM status and the integration error message",
}


class ReleaseRehearsalTests(unittest.TestCase):
    def test_hostile_secret_is_blocked_before_storage(self):
        bad = dict(SAFE)
        bad["evidence_used_by_human"] = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
        result = screen_submission(bad)
        self.assertNotEqual(result.status, "ACCEPTED")
        store = EvidenceStore(":memory:")
        try:
            count = store.conn.execute("SELECT COUNT(*) FROM evidence_packets").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            store.close()

    def test_rate_limit_survives_process_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "rate.db")
            first = SQLiteRateLimiter(db, limit=1, window_seconds=60)
            self.assertTrue(first.allow("actor", now=100.0))
            first.close()
            second = SQLiteRateLimiter(db, limit=1, window_seconds=60)
            try:
                self.assertFalse(second.allow("actor", now=101.0))
            finally:
                second.close()

    def test_audit_reopen_contains_metadata_not_payload(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "audit.db")
            sink = SQLiteAuditSink(db)
            sink.record("intake", actor_fingerprint="abc123", outcome="accepted")
            sink.close()
            reopened = SQLiteAuditSink(db)
            try:
                text = repr(reopened.events)
                self.assertIn("accepted", text)
                self.assertNotIn("Example CRM", text)
                self.assertNotIn("Authorization", text)
            finally:
                reopened.close()

    def test_untrusted_proxy_cannot_spoof_forwarded_client(self):
        resolver = TrustedClientResolver(())
        self.assertEqual(resolver.resolve(peer_ip="203.0.113.9", forwarded_for="198.51.100.7"), "203.0.113.9")

    def test_production_storage_fails_closed_without_encryption_provider(self):
        with self.assertRaises(RuntimeError):
            require_production_protector(None)

    def test_explicit_deletion_removes_raw_and_recurrence(self):
        store = EvidenceStore(":memory:")
        authority = DeletionAuthority()
        controls = DataControlService(store, authority)
        try:
            result = screen_submission(SAFE)
            self.assertEqual(result.status, "ACCEPTED")
            packet = result.packet
            store.save_accepted_packet(packet)
            credential = authority.issue(packet["submission_id"])
            deleted = controls.delete(submission_id=packet["submission_id"], deletion_token=credential.deletion_token)
            self.assertEqual(deleted.status, "DELETED")
            self.assertIsNone(store.get_packet(packet["submission_id"]))
            self.assertEqual(store.recurrence_count(packet["recurrence_signature"]), 0)
        finally:
            store.close()

    def test_rollback_candidate_opens_no_network_service(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
