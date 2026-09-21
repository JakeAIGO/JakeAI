import unittest

from council_accounting import Usage, normalize_usage, provider_health, summarize_health, usage_cost_usd


class CouncilAccountingTests(unittest.TestCase):
    def test_normalize_openai_usage(self):
        u = normalize_usage("openai", {"usage": {"input_tokens": 100, "output_tokens": 25}})
        self.assertEqual(u, Usage(100, 25, 125))

    def test_normalize_anthropic_usage(self):
        u = normalize_usage("anthropic", {"usage": {"input_tokens": 200, "output_tokens": 50}})
        self.assertEqual(u, Usage(200, 50, 250))

    def test_normalize_gemini_usage(self):
        u = normalize_usage("gemini", {"usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 10, "totalTokenCount": 50}})
        self.assertEqual(u, Usage(40, 10, 50))

    def test_normalize_chat_compatible_usage(self):
        u = normalize_usage("grok", {"usage": {"prompt_tokens": 70, "completion_tokens": 30, "total_tokens": 100}})
        self.assertEqual(u, Usage(70, 30, 100))

    def test_missing_rates_never_invent_cost(self):
        result = usage_cost_usd(Usage(1000, 500, 1500), None, None)
        self.assertEqual(result["status"], "UNPRICED")
        self.assertIsNone(result["usd"])

    def test_missing_usage_never_invent_cost(self):
        result = usage_cost_usd(Usage(None, None, None), "1", "2")
        self.assertEqual(result["status"], "USAGE_UNAVAILABLE")
        self.assertIsNone(result["usd"])

    def test_configured_rates_price_exact_usage(self):
        result = usage_cost_usd(Usage(1_000_000, 500_000, 1_500_000), "2", "4")
        self.assertEqual(result["status"], "PRICED")
        self.assertEqual(result["usd"], 4.0)

    def test_account_exhaustion_is_not_mislabeled_transient(self):
        member = {"status": "ERROR", "error_type": "ProviderHTTPError", "error": "HTTP 429: code=insufficient_quota; message=credit_balance_exhausted"}
        self.assertEqual(provider_health(member), "ACCOUNT_BLOCKED")

    def test_503_is_transient_provider_failure(self):
        member = {"status": "ERROR", "error_type": "ProviderHTTPError", "error": "HTTP 503: status=UNAVAILABLE"}
        self.assertEqual(provider_health(member), "TRANSIENT_PROVIDER_FAILURE")

    def test_malformed_json_has_distinct_health_state(self):
        member = {"status": "ERROR", "error_type": "JSONDecodeError", "error": "Unterminated string"}
        self.assertEqual(provider_health(member), "RESPONSE_FORMAT_FAILURE")

    def test_summary_requires_every_provider_healthy(self):
        members = {
            "a": {"status": "SUCCESS", "participated": True},
            "b": {"status": "ERROR", "error": "HTTP 503"},
        }
        summary = summarize_health(members)
        self.assertEqual(summary["healthy_count"], 1)
        self.assertFalse(summary["all_healthy"])


if __name__ == "__main__":
    unittest.main()
