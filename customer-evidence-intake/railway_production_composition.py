"""Unreleased Railway production composition gate for Customer Evidence Intake.

This composes configuration only. It opens no database connection, creates no
Railway resource, starts no HTTP route, and keeps intake disabled by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from railway_topology import RailwayTopology
from railway_storage_contract import RailwayEvidenceStorageContract


@dataclass(frozen=True)
class RailwayProductionComposition:
    topology: RailwayTopology
    storage: RailwayEvidenceStorageContract | None
    api_key_present: bool
    deletion_pepper_present: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "RailwayProductionComposition":
        topology = RailwayTopology.from_env(env)
        enabled = topology.intake_enabled
        api_key = env.get("JAKEAI_INTAKE_API_KEY", "")
        pepper = env.get("JAKEAI_INTAKE_DELETION_PEPPER", "")
        pepper_id = env.get("JAKEAI_INTAKE_DELETION_PEPPER_ID", "").strip()

        if not enabled:
            # Disabled composition deliberately does not require or consume
            # production credentials. This is the safe default release state.
            return cls(topology=topology, storage=None, api_key_present=False, deletion_pepper_present=False)

        if len(api_key) < 32:
            raise ValueError("enabled intake requires a strong production API key")
        if len(pepper.encode("utf-8")) < 32:
            raise ValueError("enabled intake requires a strong deletion-token pepper")
        if not pepper_id:
            raise ValueError("enabled intake requires deletion-token pepper id")

        storage = RailwayEvidenceStorageContract(
            database_url=topology.evidence_store_url,
            encryption_key_id=topology.encryption_key_id,
            deletion_pepper_id=pepper_id,
        )
        storage.validate()
        return cls(topology=topology, storage=storage, api_key_present=True, deletion_pepper_present=True)

    @property
    def public_routes_may_mount(self) -> bool:
        """Composition readiness only; never constitutes release approval."""
        return bool(
            self.topology.intake_enabled
            and self.storage is not None
            and self.api_key_present
            and self.deletion_pepper_present
        )
