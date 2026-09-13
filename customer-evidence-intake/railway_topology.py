"""Unreleased Railway topology adapter for Customer Evidence Intake v1.

This module models the verified production topology without deploying or
changing Railway. Public intake is disabled by default and construction fails
closed unless the operator explicitly enables the feature *and* supplies the
separate evidence-store/encryption configuration required by the release gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RailwayTopology:
    repo: str
    branch: str
    service_name: str
    start_command: str
    https_domain: str
    intake_enabled: bool
    evidence_store_url: str
    encryption_key_id: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "RailwayTopology":
        enabled = env.get("JAKEAI_INTAKE_ENABLED", "false").strip().lower() == "true"
        store = env.get("JAKEAI_INTAKE_EVIDENCE_STORE_URL", "").strip()
        key_id = env.get("JAKEAI_INTAKE_ENCRYPTION_KEY_ID", "").strip()

        topology = cls(
            repo=env.get("RAILWAY_SOURCE_REPO", "JakeAIGO/JakeAI").strip(),
            branch=env.get("RAILWAY_SOURCE_BRANCH", "main").strip(),
            service_name=env.get("RAILWAY_SERVICE_NAME", "agent-commerce-network").strip(),
            start_command=env.get(
                "RAILWAY_START_COMMAND",
                "sh -c 'uvicorn commerce_guard:app --host 0.0.0.0 --port ${PORT}'",
            ).strip(),
            https_domain=env.get(
                "RAILWAY_PUBLIC_DOMAIN",
                "agent-commerce-network-production-56e8.up.railway.app",
            ).strip(),
            intake_enabled=enabled,
            evidence_store_url=store,
            encryption_key_id=key_id,
        )
        topology.validate()
        return topology

    def validate(self) -> None:
        if self.repo != "JakeAIGO/JakeAI":
            raise ValueError("unexpected Railway source repository")
        if self.branch != "main":
            raise ValueError("production Railway service must remain pinned to main")
        if self.service_name != "agent-commerce-network":
            raise ValueError("unexpected Railway production service")
        if "commerce_guard:app" not in self.start_command:
            raise ValueError("unexpected Railway production entrypoint")
        if not self.https_domain.endswith(".up.railway.app"):
            raise ValueError("expected Railway HTTPS domain")

        # Release gate: enabling intake without separate protected evidence
        # storage is forbidden. This keeps "Go" from becoming deployment.
        if self.intake_enabled:
            if not self.evidence_store_url:
                raise ValueError("enabled intake requires isolated evidence store")
            if not self.evidence_store_url.startswith(("postgres://", "postgresql://")):
                raise ValueError("evidence store must use a dedicated PostgreSQL URL")
            if not self.encryption_key_id:
                raise ValueError("enabled intake requires an encryption key id")

    @property
    def deployment_safe(self) -> bool:
        """True only when intake remains disabled in this unreleased adapter."""
        return not self.intake_enabled


def expected_disabled_environment() -> dict[str, str]:
    """Return names/defaults only; contains no secret values and performs no write."""
    return {
        "JAKEAI_INTAKE_ENABLED": "false",
        "JAKEAI_INTAKE_EVIDENCE_STORE_URL": "",
        "JAKEAI_INTAKE_ENCRYPTION_KEY_ID": "",
    }
