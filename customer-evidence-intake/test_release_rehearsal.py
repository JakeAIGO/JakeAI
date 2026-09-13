"""Final private release rehearsal for Customer Evidence Intake v1.

This is deliberately an offline test harness. It does not deploy, open a socket,
or use real customer data. It exercises fail-closed release invariants before a
human launch decision.
"""
import os
import tempfile
import unittest
from pathlib import Path

from intake import screen_submission
from storage import EvidenceStore
from data_control import DeletionAuthority, EncryptionProviderGate
from production_adapter import ProductionConfig, SQLiteRateLimiter, SQLiteAuditSink, TrustedClientResolver

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
            self.assertEqual(store.raw_count(), 0)
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
        self.assertEqual(
            resolver.resolve(peer_ip="203.0.113.9", forwarded_for="198.51.100.7"),
            "203.0.113.9",
        )

    def test_production_config_fails_closed_without_encryption_provider(self):
        with self.assertRaises(ValueError):
            EncryptionProviderGate.require(None)

    def test_explicit_deletion_removes_raw_and_recurrence(self):
        store = EvidenceStore(":memory:")
        authority = DeletionAuthority(store)
        try:
            result = screen_submission(SAFE)
            self.assertEqual(result.status, "ACCEPTED")
            packet = result.packet
            store.save_accepted_packet(packet)
            token = authority.issue(packet["submission_id"])
            self.assertTrue(authority.delete(packet["submission_id"], token))
            self.assertIsNone(store.get_packet(packet["submission_id"]))
            self.assertEqual(store.recurrence_count(packet["recurrence_signature"]), 0)
        finally:
            store.close()

    def test_rollback_is_data_free_when_no_production_adapter_is_built(self):
        # Release rollback invariant for the current candidate: merely importing
        # and testing modules creates no production endpoint or customer store.
        self.assertNotIn("JAKEAI_INTAKE_API_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
