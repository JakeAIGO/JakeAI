import unittest

from data_controls import DataControlService, DeletionAuthority, require_production_protector
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


class FakeProtector:
    key_id = "test-key-v1"

    def seal(self, plaintext: bytes, *, context: bytes) -> bytes:
        return b"sealed:" + context + b":" + plaintext

    def open(self, ciphertext: bytes, *, context: bytes) -> bytes:
        prefix = b"sealed:" + context + b":"
        if not ciphertext.startswith(prefix):
            raise ValueError("bad context")
        return ciphertext[len(prefix):]


class DataControlTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(":memory:")
        self.authority = DeletionAuthority()
        self.service = DataControlService(self.store, self.authority)

    def tearDown(self):
        self.store.close()

    def _packet(self):
        result = screen_submission(SAFE)
        self.assertEqual(result.status, "ACCEPTED")
        return result.packet

    def test_deletion_removes_raw_and_recurrence_contribution(self):
        packet = self._packet()
        self.store.save_accepted_packet(packet)
        credential = self.authority.issue(packet["submission_id"])
        result = self.service.delete(
            submission_id=credential.submission_id,
            deletion_token=credential.deletion_token,
        )
        self.assertEqual(result.status, "DELETED")
        self.assertIsNone(self.store.get_packet(packet["submission_id"]))
        self.assertEqual(self.store.recurrence_count(packet["recurrence_signature"]), 0)

    def test_deletion_of_one_of_two_decrements_only_one(self):
        first = self._packet()
        second = self._packet()
        self.store.save_accepted_packet(first)
        self.store.save_accepted_packet(second)
        credential = self.authority.issue(first["submission_id"])
        self.service.delete(submission_id=first["submission_id"], deletion_token=credential.deletion_token)
        self.assertEqual(self.store.recurrence_count(first["recurrence_signature"]), 1)
        self.assertIsNotNone(self.store.get_packet(second["submission_id"]))

    def test_wrong_token_fails_closed(self):
        packet = self._packet()
        self.store.save_accepted_packet(packet)
        self.authority.issue(packet["submission_id"])
        result = self.service.delete(submission_id=packet["submission_id"], deletion_token="wrong")
        self.assertEqual(result.status, "AUTH_REJECTED")
        self.assertIsNotNone(self.store.get_packet(packet["submission_id"]))
        self.assertEqual(self.store.recurrence_count(packet["recurrence_signature"]), 1)

    def test_token_is_one_time(self):
        packet = self._packet()
        self.store.save_accepted_packet(packet)
        credential = self.authority.issue(packet["submission_id"])
        first = self.service.delete(submission_id=packet["submission_id"], deletion_token=credential.deletion_token)
        second = self.service.delete(submission_id=packet["submission_id"], deletion_token=credential.deletion_token)
        self.assertEqual(first.status, "DELETED")
        self.assertEqual(second.status, "AUTH_REJECTED")

    def test_retention_purge_does_not_prevent_later_contribution_deletion(self):
        packet = self._packet()
        self.store.save_accepted_packet(packet)
        credential = self.authority.issue(packet["submission_id"])
        self.store.conn.execute("DELETE FROM evidence_packets WHERE submission_id=?", (packet["submission_id"],))
        self.store.conn.commit()
        result = self.service.delete(submission_id=packet["submission_id"], deletion_token=credential.deletion_token)
        self.assertEqual(result.status, "DELETED")
        self.assertEqual(self.store.recurrence_count(packet["recurrence_signature"]), 0)

    def test_production_storage_fails_closed_without_protector(self):
        with self.assertRaises(RuntimeError):
            require_production_protector(None)

    def test_production_storage_accepts_explicit_protector_interface(self):
        protector = FakeProtector()
        self.assertIs(require_production_protector(protector), protector)

    def test_invalid_protector_rejected(self):
        class Bad:
            key_id = ""
        with self.assertRaises(RuntimeError):
            require_production_protector(Bad())


if __name__ == "__main__":
    unittest.main()
