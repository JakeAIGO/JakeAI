"""Private persistence prototype for Customer Evidence Intake v1.

This module is intentionally local-only and dependency-free. It stores only
already-screened ACCEPTED packets. It is not a production storage system and
must not be used as a public endpoint without the release/security gates in
README.md.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_RAW_RETENTION_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceStore:
    def __init__(self, db_path: str | Path = ":memory:", *, raw_retention_days: int = DEFAULT_RAW_RETENTION_DAYS):
        if raw_retention_days < 1 or raw_retention_days > 90:
            raise ValueError("raw_retention_days must be between 1 and 90")
        self.raw_retention_days = raw_retention_days
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS evidence_packets (
              submission_id TEXT PRIMARY KEY,
              received_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              packet_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recurrence_signatures (
              recurrence_signature TEXT PRIMARY KEY,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              occurrence_count INTEGER NOT NULL CHECK (occurrence_count >= 1),
              software_or_ai TEXT NOT NULL,
              residual_human_intervention TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def save_accepted_packet(self, packet: dict[str, Any], *, now: datetime | None = None) -> None:
        required = {
            "submission_id", "received_at", "software_or_ai",
            "residual_human_intervention", "recurrence_signature",
            "product_factory_status", "safety_class",
        }
        if not isinstance(packet, dict) or not required.issubset(packet):
            raise ValueError("packet is missing required evidence fields")
        if packet.get("product_factory_status") != "EVIDENCE_PACKETED":
            raise ValueError("only screened evidence packets may be persisted")
        if packet.get("safety_class") != "LOW_CONSEQUENCE_CANDIDATE":
            raise ValueError("only low-consequence accepted packets may be persisted")

        now = now or _utcnow()
        expires = now + timedelta(days=self.raw_retention_days)
        payload = json.dumps(packet, separators=(",", ":"), sort_keys=True)

        with self.conn:
            self.conn.execute(
                "INSERT INTO evidence_packets(submission_id,received_at,expires_at,packet_json) VALUES(?,?,?,?)",
                (packet["submission_id"], packet["received_at"], expires.isoformat(), payload),
            )
            self.conn.execute(
                """
                INSERT INTO recurrence_signatures(
                  recurrence_signature, first_seen_at, last_seen_at,
                  occurrence_count, software_or_ai, residual_human_intervention
                ) VALUES(?,?,?,?,?,?)
                ON CONFLICT(recurrence_signature) DO UPDATE SET
                  last_seen_at=excluded.last_seen_at,
                  occurrence_count=recurrence_signatures.occurrence_count+1
                """,
                (
                    packet["recurrence_signature"], now.isoformat(), now.isoformat(), 1,
                    packet["software_or_ai"], packet["residual_human_intervention"],
                ),
            )

    def get_packet(self, submission_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT packet_json FROM evidence_packets WHERE submission_id=?", (submission_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def purge_expired_raw(self, *, now: datetime | None = None) -> int:
        now = now or _utcnow()
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM evidence_packets WHERE expires_at <= ?", (now.isoformat(),)
            )
        return cur.rowcount

    def recurrence_count(self, recurrence_signature: str) -> int:
        row = self.conn.execute(
            "SELECT occurrence_count FROM recurrence_signatures WHERE recurrence_signature=?",
            (recurrence_signature,),
        ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self.conn.close()
