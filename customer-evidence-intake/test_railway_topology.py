import unittest

from railway_topology import RailwayTopology, expected_disabled_environment


class RailwayTopologyTests(unittest.TestCase):
    def base_env(self):
        return {
            "RAILWAY_SOURCE_REPO": "JakeAIGO/JakeAI",
            "RAILWAY_SOURCE_BRANCH": "main",
            "RAILWAY_SERVICE_NAME": "agent-commerce-network",
            "RAILWAY_START_COMMAND": "sh -c 'uvicorn commerce_guard:app --host 0.0.0.0 --port ${PORT}'",
            "RAILWAY_PUBLIC_DOMAIN": "agent-commerce-network-production-56e8.up.railway.app",
        }

    def test_default_is_disabled_and_safe(self):
        cfg = RailwayTopology.from_env(self.base_env())
        self.assertFalse(cfg.intake_enabled)
        self.assertTrue(cfg.deployment_safe)

    def test_enabled_without_store_fails_closed(self):
        env = self.base_env()
        env["JAKEAI_INTAKE_ENABLED"] = "true"
        with self.assertRaises(ValueError):
            RailwayTopology.from_env(env)

    def test_enabled_without_encryption_key_fails_closed(self):
        env = self.base_env()
        env.update({
            "JAKEAI_INTAKE_ENABLED": "true",
            "JAKEAI_INTAKE_EVIDENCE_STORE_URL": "postgresql://example.invalid/intake",
        })
        with self.assertRaises(ValueError):
            RailwayTopology.from_env(env)

    def test_enabled_requires_postgres_store(self):
        env = self.base_env()
        env.update({
            "JAKEAI_INTAKE_ENABLED": "true",
            "JAKEAI_INTAKE_EVIDENCE_STORE_URL": "sqlite:///tmp/intake.db",
            "JAKEAI_INTAKE_ENCRYPTION_KEY_ID": "kms-key-1",
        })
        with self.assertRaises(ValueError):
            RailwayTopology.from_env(env)

    def test_enabled_with_isolated_store_and_key_can_validate(self):
        env = self.base_env()
        env.update({
            "JAKEAI_INTAKE_ENABLED": "true",
            "JAKEAI_INTAKE_EVIDENCE_STORE_URL": "postgresql://example.invalid/intake",
            "JAKEAI_INTAKE_ENCRYPTION_KEY_ID": "kms-key-1",
        })
        cfg = RailwayTopology.from_env(env)
        self.assertTrue(cfg.intake_enabled)
        self.assertFalse(cfg.deployment_safe)

    def test_wrong_branch_rejected(self):
        env = self.base_env()
        env["RAILWAY_SOURCE_BRANCH"] = "feature/customer-evidence-intake-v1"
        with self.assertRaises(ValueError):
            RailwayTopology.from_env(env)

    def test_wrong_entrypoint_rejected(self):
        env = self.base_env()
        env["RAILWAY_START_COMMAND"] = "uvicorn customer_evidence:app"
        with self.assertRaises(ValueError):
            RailwayTopology.from_env(env)

    def test_expected_disabled_environment_contains_no_secrets(self):
        values = expected_disabled_environment()
        self.assertEqual(values["JAKEAI_INTAKE_ENABLED"], "false")
        self.assertEqual(values["JAKEAI_INTAKE_EVIDENCE_STORE_URL"], "")
        self.assertEqual(values["JAKEAI_INTAKE_ENCRYPTION_KEY_ID"], "")


if __name__ == "__main__":
    unittest.main()
