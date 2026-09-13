import os
import tempfile
import unittest
from pathlib import Path

from production_adapter import (
    ProductionConfig,
    SQLiteAuditSink,
    SQLiteRateLimiter,
    TrustedClientResolver,
)


class ProductionAdapterTests(unittest.TestCase):
    def test_env_requires_strong_secret(self):
        env = {
            "JAKEAI_INTAKE_API_KEY": "short",
            "JAKEAI_INTAKE_ALLOWED_ORIGINS": "https://example.com",
            "JAKEAI_INTAKE_RATE_LIMIT_DB": "/tmp/rate.db",
            "JAKEAI_INTAKE_AUDIT_DB": "/tmp/audit.db",
        }
        with self.assertRaises(ValueError):
            ProductionConfig.from_env(env)

    def test_http_origin_rejected(self):
        env = {
            "JAKEAI_INTAKE_API_KEY": "x" * 32,
            "JAKEAI_INTAKE_ALLOWED_ORIGINS": "http://example.com",
            "JAKEAI_INTAKE_RATE_LIMIT_DB": "/tmp/rate.db",
            "JAKEAI_INTAKE_AUDIT_DB": "/tmp/audit.db",
        }
        with self.assertRaises(ValueError):
            ProductionConfig.from_env(env)

    def test_wildcard_origin_rejected(self):
        env = {
            "JAKEAI_INTAKE_API_KEY": "x" * 32,
            "JAKEAI_INTAKE_ALLOWED_ORIGINS": "*",
            "JAKEAI_INTAKE_RATE_LIMIT_DB": "/tmp/rate.db",
            "JAKEAI_INTAKE_AUDIT_DB": "/tmp/audit.db",
        }
        with self.assertRaises(ValueError):
            ProductionConfig.from_env(env)

    def test_memory_databases_rejected_for_production(self):
        env = {
            "JAKEAI_INTAKE_API_KEY": "x" * 32,
            "JAKEAI_INTAKE_ALLOWED_ORIGINS": "https://example.com",
            "JAKEAI_INTAKE_RATE_LIMIT_DB": ":memory:",
            "JAKEAI_INTAKE_AUDIT_DB": ":memory:",
        }
        with self.assertRaises(ValueError):
            ProductionConfig.from_env(env)

    def test_trusted_proxy_may_supply_forwarded_client(self):
        cfg = ProductionConfig.from_env({
            "JAKEAI_INTAKE_API_KEY": "x" * 32,
            "JAKEAI_INTAKE_ALLOWED_ORIGINS": "https://example.com",
            "JAKEAI_INTAKE_TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
            "JAKEAI_INTAKE_RATE_LIMIT_DB": "/tmp/rate.db",
            "JAKEAI_INTAKE_AUDIT_DB": "/tmp/audit.db",
        })
        resolver = TrustedClientResolver(cfg.trusted_proxy_cidrs)
        self.assertEqual(
            resolver.resolve(peer_ip="10.1.2.3", forwarded_for="203.0.113.9, 10.1.2.3"),
            "203.0.113.9",
        )

    def test_untrusted_peer_cannot_spoof_forwarded_client(self):
        cfg = ProductionConfig.from_env({
            "JAKEAI_INTAKE_API_KEY": "x" * 32,
            "JAKEAI_INTAKE_ALLOWED_ORIGINS": "https://example.com",
            "JAKEAI_INTAKE_TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
            "JAKEAI_INTAKE_RATE_LIMIT_DB": "/tmp/rate.db",
            "JAKEAI_INTAKE_AUDIT_DB": "/tmp/audit.db",
        })
        resolver = TrustedClientResolver(cfg.trusted_proxy_cidrs)
        self.assertEqual(
            resolver.resolve(peer_ip="198.51.100.7", forwarded_for="203.0.113.9"),
            "198.51.100.7",
        )

    def test_rate_limit_survives_new_instance(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "rate.db")
            first = SQLiteRateLimiter(db, limit=2, window_seconds=60)
            self.assertTrue(first.allow("actor", now=100.0))
            self.assertTrue(first.allow("actor", now=101.0))
            first.close()
            second = SQLiteRateLimiter(db, limit=2, window_seconds=60)
            self.assertFalse(second.allow("actor", now=102.0))
            second.close()

    def test_rate_db_does_not_store_plain_actor(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "rate.db")
            limiter = SQLiteRateLimiter(db)
            limiter.allow("private-client-id", now=100.0)
            raw = limiter.conn.execute("SELECT actor FROM rate_events").fetchone()[0]
            self.assertNotEqual(raw, "private-client-id")
            self.assertEqual(len(raw), 64)
            limiter.close()

    def test_audit_sink_stores_metadata_only(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "audit.db")
            sink = SQLiteAuditSink(db)
            sink.record("intake_submit", actor_fingerprint="abc123", outcome="ACCEPTED")
            events = sink.events
            self.assertEqual(events[0]["event"], "intake_submit")
            self.assertNotIn("body", events[0])
            self.assertNotIn("authorization", events[0])
            self.assertNotIn("contact", events[0])
            sink.close()

    def test_config_parses_multiple_https_origins(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = ProductionConfig.from_env({
                "JAKEAI_INTAKE_API_KEY": "x" * 32,
                "JAKEAI_INTAKE_ALLOWED_ORIGINS": "https://a.example.com,https://b.example.com",
                "JAKEAI_INTAKE_RATE_LIMIT_DB": str(Path(td) / "rate.db"),
                "JAKEAI_INTAKE_AUDIT_DB": str(Path(td) / "audit.db"),
            })
            self.assertEqual(len(cfg.allowed_origins), 2)


if __name__ == "__main__":
    unittest.main()
