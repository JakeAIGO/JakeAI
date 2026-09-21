import unittest
from datetime import datetime, timezone

from railway_storage_contract import (
    DeletionCredentialRecord,
    DeletionTokenDigester,
    POSTGRES_SCHEMA_V1,
    RailwayEvidenceStorageContract,
    assert_deletion_record_usable,
)


class RailwayStorageContractTests(unittest.TestCase):
    def test_valid_postgres_contract(self):
        cfg = RailwayEvidenceStorageContract(
            database_url="postgresql://user:pass@example.invalid/jakeai_evidence",
            encryption_key_id="key-v1",
            deletion_pepper_id="pepper-v1",
        )
        cfg.validate()

    def test_non_postgres_rejected(self):
        cfg = RailwayEvidenceStorageContract(
            database_url="sqlite:///tmp/evidence.db",
            encryption_key_id="key-v1",
            deletion_pepper_id="pepper-v1",
        )
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_localhost_rejected(self):
        cfg = RailwayEvidenceStorageContract(
            database_url="postgresql://user:pass@localhost/jakeai_evidence",
            encryption_key_id="key-v1",
            deletion_pepper_id="pepper-v1",
        )
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_database_name_required(self):
        cfg = RailwayEvidenceStorageContract(
            database_url="postgresql://user:pass@example.invalid/",
            encryption_key_id="key-v1",
            deletion_pepper_id="pepper-v1",
        )
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_encryption_key_required(self):
        cfg = RailwayEvidenceStorageContract(
            database_url="postgresql://user:pass@example.invalid/jakeai_evidence",
            encryption_key_id="",
            deletion_pepper_id="pepper-v1",
        )
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_pepper_id_required(self):
        cfg = RailwayEvidenceStorageContract(
            database_url="postgresql://user:pass@example.invalid/jakeai_evidence",
            encryption_key_id="key-v1",
            deletion_pepper_id="",
        )
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_schema_never_stores_plain_deletion_token(self):
        schema = POSTGRES_SCHEMA_V1.lower()
        self.assertIn("token_digest", schema)
        self.assertNotIn("deletion_token", schema)
        self.assertIn("ciphertext bytea", schema)

    def test_short_pepper_rejected(self):
        with self.assertRaises(ValueError):
            DeletionTokenDigester(pepper=b"too-short", pepper_id="pepper-v1")

    def test_digest_is_deterministic_and_not_plaintext(self):
        d = DeletionTokenDigester(pepper=b"x" * 32, pepper_id="pepper-v1")
        token = "customer-deletion-token"
        digest = d.digest(token)
        self.assertEqual(digest, d.digest(token))
        self.assertNotEqual(digest, token)
        self.assertTrue(d.verify(token, digest))
        self.assertFalse(d.verify("wrong-token", digest))

    def test_record_contains_only_digest_and_pepper_id(self):
        d = DeletionTokenDigester(pepper=b"y" * 32, pepper_id="pepper-v2")
        record = d.record(
            submission_id="sub_123",
            token="one-time-secret-token",
            issued_at=datetime(2026, 9, 13, tzinfo=timezone.utc),
        )
        text = repr(record)
        self.assertNotIn("one-time-secret-token", text)
        self.assertEqual(record.pepper_id, "pepper-v2")
        self.assertIsNone(record.consumed_at)

    def test_missing_consumed_and_wrong_pepper_fail_closed(self):
        with self.assertRaises(PermissionError):
            assert_deletion_record_usable(None, pepper_id="pepper-v1")

        consumed = DeletionCredentialRecord("s", "d", "pepper-v1", "now", "later")
        with self.assertRaises(PermissionError):
            assert_deletion_record_usable(consumed, pepper_id="pepper-v1")

        wrong = DeletionCredentialRecord("s", "d", "pepper-old", "now")
        with self.assertRaises(PermissionError):
            assert_deletion_record_usable(wrong, pepper_id="pepper-v1")

    def test_matching_unconsumed_record_is_usable(self):
        record = DeletionCredentialRecord("s", "d", "pepper-v1", "now")
        self.assertIs(assert_deletion_record_usable(record, pepper_id="pepper-v1"), record)


if __name__ == "__main__":
    unittest.main()
