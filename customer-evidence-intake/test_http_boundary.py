import json
import unittest

from http_boundary import AuditSink, IntakeHttpBoundary, SlidingWindowRateLimiter
from service import CustomerEvidenceService
from storage import EvidenceStore

API_KEY = "test_only_super_long_api_key_1234567890"
ORIGIN = "https://intake.example.test"

SAFE = {
    "software_or_ai": "Example CRM",
    "normal_automation": "Copies lead status into a project board",
    "residual_human_intervention": "A coordinator compares failed sync rows and re-enters the missing status",
    "frequency": "about 12 times per week",
    "minutes_per_occurrence": "6",
    "consequence_if_unhandled": "The internal project board is stale until the next review",
    "evidence_used_by_human": "The CRM status and the integration error message",
    "consent_to_process_for_intake": True,
    "acknowledge_no_secrets_or_sensitive_data": True,
}

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(":memory:")
        self.service = CustomerEvidenceService(self.store)
        self.audit = AuditSink()
        self.boundary = IntakeHttpBoundary(
            self.service,
            api_key=API_KEY,
            allowed_origins={ORIGIN},
            audit_sink=self.audit,
            rate_limiter=SlidingWindowRateLimiter(limit=2, window_seconds=60),
            clock=lambda: 1000.0,
        )

    def tearDown(self):
        self.store.close()

    def call(self, payload=SAFE, **kwargs):
        args = dict(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            origin=ORIGIN,
            authorization=f"Bearer {API_KEY}",
            client_id="client-1",
        )
        args.update(kwargs)
        return self.boundary.handle_submit(**args)

    def test_accepts_safe_authenticated_submission(self):
        r = self.call()
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.body["status"], "ACCEPTED")
        self.assertNotIn("packet", r.body)

    def test_bad_origin_rejected(self):
        r = self.call(origin="https://evil.test")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.store.conn.execute("select count(*) from evidence_packets").fetchone()[0], 0)

    def test_missing_auth_rejected(self):
        r = self.call(authorization="")
        self.assertEqual(r.status_code, 401)

    def test_wrong_auth_rejected(self):
        r = self.call(authorization="Bearer wrong")
        self.assertEqual(r.status_code, 401)

    def test_non_json_rejected(self):
        r = self.call(content_type="text/plain")
        self.assertEqual(r.status_code, 415)

    def test_invalid_json_rejected(self):
        r = self.call(body=b"{not json")
        self.assertEqual(r.status_code, 400)

    def test_array_json_rejected(self):
        r = self.call(body=b"[]")
        self.assertEqual(r.status_code, 400)

    def test_oversize_rejected_before_json_parse(self):
        r = self.call(body=b"x" * 12001)
        self.assertEqual(r.status_code, 413)

    def test_consent_required(self):
        x = dict(SAFE)
        x.pop("consent_to_process_for_intake")
        r = self.call(x)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.store.conn.execute("select count(*) from evidence_packets").fetchone()[0], 0)

    def test_safety_ack_required(self):
        x = dict(SAFE)
        x.pop("acknowledge_no_secrets_or_sensitive_data")
        r = self.call(x)
        self.assertEqual(r.status_code, 400)

    def test_rate_limit_rejects_third_request(self):
        self.assertEqual(self.call().status_code, 202)
        self.assertEqual(self.call().status_code, 202)
        self.assertEqual(self.call().status_code, 429)

    def test_secret_blocked_and_not_echoed(self):
        x = dict(SAFE, evidence_used_by_human="password is SuperSecretThing123")
        r = self.call(x)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.body["status"], "BLOCKED_SECRET_DETECTED")
        self.assertNotIn("SuperSecretThing123", json.dumps(r.body))

    def test_audit_contains_no_body_or_authorization(self):
        self.call()
        serialized = json.dumps(self.audit.events)
        self.assertNotIn("Example CRM", serialized)
        self.assertNotIn(API_KEY, serialized)
        self.assertNotIn("Bearer", serialized)

    def test_wildcard_origin_forbidden_at_configuration(self):
        with self.assertRaises(ValueError):
            IntakeHttpBoundary(self.service, api_key=API_KEY, allowed_origins={"*"})

    def test_short_api_key_forbidden_at_configuration(self):
        with self.assertRaises(ValueError):
            IntakeHttpBoundary(self.service, api_key="short", allowed_origins={ORIGIN})

if __name__ == "__main__":
    unittest.main()
