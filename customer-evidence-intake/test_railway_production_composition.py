import unittest

from railway_production_composition import RailwayProductionComposition


class RailwayProductionCompositionTests(unittest.TestCase):
    def base_env(self):
        return {
            "RAILWAY_SOURCE_REPO": "JakeAIGO/JakeAI",
            "RAILWAY_SOURCE_BRANCH": "main",
            "RAILWAY_SERVICE_NAME": "agent-commerce-network",
            "RAILWAY_START_COMMAND": "sh -c 'uvicorn commerce_guard:app --host 0.0.0.0 --port ${PORT}'",
            "RAILWAY_PUBLIC_DOMAIN": "agent-commerce-network-production-56e8.up.railway.app",
        }

    def enabled_env(self):
        env = self.base_env()
        env.update({
            "JAKEAI_INTAKE_ENABLED": "true",
            "JAKEAI_INTAKE_EVIDENCE_STORE_URL": "postgresql://intake.internal/jakeai_evidence",
            "JAKEAI_INTAKE_ENCRYPTION_KEY_ID": "evidence-key-v1",
            "JAKEAI_INTAKE_API_KEY": "A" * 32,
            "JAKEAI_INTAKE_DELETION_PEPPER": "P" * 32,
            "JAKEAI_INTAKE_DELETION_PEPPER_ID": "pepper-v1",
        })
        return env

    def test_disabled_by_default_and_mount_forbidden(self):
        cfg = RailwayProductionComposition.from_env(self.base_env())
        self.assertFalse(cfg.public_routes_may_mount)
        self.assertIsNone(cfg.storage)
        self.assertFalse(cfg.api_key_present)
        self.assertFalse(cfg.deletion_pepper_present)

    def test_disabled_does_not_consume_accidental_credentials(self):
        env = self.base_env()
        env["JAKEAI_INTAKE_API_KEY"] = "A" * 32
        env["JAKEAI_INTAKE_DELETION_PEPPER"] = "P" * 32
        cfg = RailwayProductionComposition.from_env(env)
        self.assertFalse(cfg.public_routes_may_mount)
        self.assertFalse(cfg.api_key_present)
        self.assertFalse(cfg.deletion_pepper_present)

    def test_enabled_complete_contract_can_compose_but_is_not_release_approval(self):
        cfg = RailwayProductionComposition.from_env(self.enabled_env())
        self.assertTrue(cfg.public_routes_may_mount)
        self.assertEqual(cfg.storage.encryption_key_id, "evidence-key-v1")

    def test_enabled_missing_api_key_fails_closed(self):
        env = self.enabled_env(); env.pop("JAKEAI_INTAKE_API_KEY")
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)

    def test_enabled_weak_api_key_fails_closed(self):
        env = self.enabled_env(); env["JAKEAI_INTAKE_API_KEY"] = "weak"
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)

    def test_enabled_missing_deletion_pepper_fails_closed(self):
        env = self.enabled_env(); env.pop("JAKEAI_INTAKE_DELETION_PEPPER")
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)

    def test_enabled_missing_pepper_id_fails_closed(self):
        env = self.enabled_env(); env.pop("JAKEAI_INTAKE_DELETION_PEPPER_ID")
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)

    def test_enabled_missing_database_fails_before_composition(self):
        env = self.enabled_env(); env["JAKEAI_INTAKE_EVIDENCE_STORE_URL"] = ""
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)

    def test_enabled_missing_encryption_key_fails_before_composition(self):
        env = self.enabled_env(); env["JAKEAI_INTAKE_ENCRYPTION_KEY_ID"] = ""
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)

    def test_feature_branch_cannot_be_composed_as_production(self):
        env = self.enabled_env(); env["RAILWAY_SOURCE_BRANCH"] = "feature/customer-evidence-intake-v1"
        with self.assertRaises(ValueError): RailwayProductionComposition.from_env(env)


if __name__ == "__main__":
    unittest.main()
