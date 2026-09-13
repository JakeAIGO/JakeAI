import unittest
from intake import screen_submission

SAFE = {
    "software_or_ai": "Example CRM",
    "normal_automation": "Copies lead status into a project board",
    "residual_human_intervention": "A coordinator compares failed sync rows and re-enters the missing status",
    "frequency": "about 12 times per week",
    "minutes_per_occurrence": "6",
    "consequence_if_unhandled": "The internal project board is stale until the next review",
    "evidence_used_by_human": "The CRM status and the integration error message",
}

class IntakeTests(unittest.TestCase):
    def test_safe_packet(self):
        r = screen_submission(SAFE)
        self.assertEqual(r.status, "ACCEPTED")
        self.assertEqual(r.packet["product_factory_status"], "EVIDENCE_PACKETED")
        self.assertNotIn("estimated savings", str(r.packet).lower())

    def test_password_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="password=DontStoreThis123")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_password_natural_language_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="password is DontStoreThis123")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_bearer_header_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_basic_auth_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="Authorization: Basic dXNlcjpwYXNz")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_stripe_secret_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="sk_live_1234567890ABCDEFGHIJ")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_stripe_restricted_key_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="rk_live_1234567890ABCDEFGHIJ")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_aws_key_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="AKIAIOSFODNN7EXAMPLE")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_private_key_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="-----BEGIN PRIVATE KEY----- abc")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_github_fine_grained_token_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="github_pat_11AAABBBCCCDDDEEEFFF_1234567890123456789012345678901234567890")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_jwt_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnopqrstuvwxyz123456")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SECRET_DETECTED")

    def test_ssn_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="123-45-6789")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SENSITIVE_DATA")

    def test_card_like_number_fails_closed(self):
        x = dict(SAFE, evidence_used_by_human="4111 1111 1111 1111")
        self.assertEqual(screen_submission(x).status, "BLOCKED_SENSITIVE_DATA")

    def test_medical_routes_human(self):
        x = dict(SAFE, normal_automation="Routes patient medical records")
        self.assertEqual(screen_submission(x).status, "HUMAN_REVIEW")

    def test_employment_routes_human(self):
        x = dict(SAFE, residual_human_intervention="Manager decides whether to fire employee")
        self.assertEqual(screen_submission(x).status, "HUMAN_REVIEW")

    def test_payroll_disbursement_routes_human(self):
        x = dict(SAFE, residual_human_intervention="Operator approves payroll disbursement")
        self.assertEqual(screen_submission(x).status, "HUMAN_REVIEW")

    def test_missing_required_rejected(self):
        x = dict(SAFE, frequency="")
        self.assertEqual(screen_submission(x).status, "REJECTED_INPUT")

    def test_bad_minutes_rejected(self):
        x = dict(SAFE, minutes_per_occurrence="six")
        self.assertEqual(screen_submission(x).status, "REJECTED_INPUT")

    def test_negative_minutes_rejected(self):
        x = dict(SAFE, minutes_per_occurrence="-1")
        self.assertEqual(screen_submission(x).status, "REJECTED_INPUT")

    def test_oversize_rejected(self):
        x = dict(SAFE, normal_automation="x" * 2001)
        self.assertEqual(screen_submission(x).status, "REJECTED_INPUT")

if __name__ == "__main__":
    unittest.main()
