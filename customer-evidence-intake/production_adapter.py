"""Private production-adapter building blocks for Customer Evidence Intake v1.

NOT DEPLOYED. No server is opened. This module turns deploy-time environment
configuration into the existing fail-closed HTTP boundary and provides durable
SQLite-backed rate limiting / audit metadata plus conservative trusted-client
resolution. It deliberately does not implement encryption-at-rest or a public
web route; those remain release blockers.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from http_boundary import AuditSink, IntakeHttpBoundary
from service import CustomerEvidenceService


@dataclass(frozen=True)
class ProductionConfig:
    api_key: str
    allowed_origins: frozenset[str]
    trusted_proxy_cidrs: tuple[ipaddress._BaseNetwork, ...]
    rate_limit_db: str
    audit_db: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ProductionConfig":
        env = os.environ if env is None else env
        api_key = env.get("JAKEAI_INTAKE_API_KEY", "")
        if len(api_key) < 32:
            raise ValueError("JAKEAI_INTAKE_API_KEY must be at least 32 characters")

        raw_origins = [x.strip() for x in env.get("JAKEAI_INTAKE_ALLOWED_ORIGINS", "").split(",") if x.strip()]
        if not raw_origins:
            raise ValueError("JAKEAI_INTAKE_ALLOWED_ORIGINS is required")
        for origin in raw_origins:
            parsed = urlparse(origin)
            if origin == "*" or parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
                raise ValueError("allowed origins must be explicit HTTPS origins")

        raw_proxies = [x.strip() for x in env.get("JAKEAI_INTAKE_TRUSTED_PROXY_CIDRS", "").split(",") if x.strip()]
        proxies = tuple(ipaddress.ip_network(x, strict=False) for x in raw_proxies)

        rate_db = env.get("JAKEAI_INTAKE_RATE_LIMIT_DB", "")
        audit_db = env.get("JAKEAI_INTAKE_AUDIT_DB", "")
        if not rate_db or not audit_db:
            raise ValueError("durable rate-limit and audit DB paths are required")
        if rate_db == ":memory:" or audit_db == ":memory:":
            raise ValueError("production adapter requires durable DB paths")

        return cls(api_key, frozenset(raw_origins), proxies, rate_db, audit_db)


class TrustedClientResolver:
    """Use X-Forwarded-For only when the immediate peer is explicitly trusted."""

    def __init__(self, trusted_proxy_cidrs: tuple[ipaddress._BaseNetwork, ...]):
        self.trusted_proxy_cidrs = trusted_proxy_cidrs

    def resolve(self, *, peer_ip: str, forwarded_for: str | None = None) -> str:
        peer = ipaddress.ip_address(peer_ip)
        trusted = any(peer in network for network in self.trusted_proxy_cidrs)
        if not trusted or not forwarded_for:
            return str(peer)

        # Take the left-most syntactically valid client address only after the
        # immediate peer has been positively identified as a trusted proxy.
        candidate = forwarded_for.split(",", 1)[0].strip()
        return str(ipaddress.ip_address(candidate))


class SQLiteRateLimiter:
    """Durable fixed-window limiter; stores only hashed actor IDs and timestamps."""

    def __init__(self, db_path: str | Path, *, limit: int = 10, window_seconds: int = 60):
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate limit and window must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS rate_events(actor TEXT NOT NULL, ts REAL NOT NULL)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_actor_ts ON rate_events(actor, ts)")
        self.conn.commit()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds
        actor = hashlib.sha256(key.encode()).hexdigest()
        with self.conn:
            self.conn.execute("DELETE FROM rate_events WHERE ts <= ?", (cutoff,))
            count = self.conn.execute(
                "SELECT COUNT(*) FROM rate_events WHERE actor=? AND ts>?", (actor, cutoff)
            ).fetchone()[0]
            if count >= self.limit:
                return False
            self.conn.execute("INSERT INTO rate_events(actor,ts) VALUES(?,?)", (actor, now))
        return True

    def close(self) -> None:
        self.conn.close()


class SQLiteAuditSink(AuditSink):
    """Durable audit metadata with no body, auth header, contact text, or evidence payload."""

    def __init__(self, db_path: str | Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_events(ts REAL NOT NULL, event TEXT NOT NULL, actor_fingerprint TEXT NOT NULL, outcome TEXT NOT NULL)"
        )
        self.conn.commit()

    @property
    def events(self):
        rows = self.conn.execute(
            "SELECT event, actor_fingerprint, outcome FROM audit_events ORDER BY rowid"
        ).fetchall()
        return [
            {"event": r[0], "actor_fingerprint": r[1], "outcome": r[2]}
            for r in rows
        ]

    def record(self, event: str, *, actor_fingerprint: str, outcome: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO audit_events(ts,event,actor_fingerprint,outcome) VALUES(?,?,?,?)",
                (time.time(), event, actor_fingerprint, outcome),
            )

    def close(self) -> None:
        self.conn.close()


def build_production_boundary(service: CustomerEvidenceService, config: ProductionConfig) -> IntakeHttpBoundary:
    """Construct the boundary without deploying it or opening a network socket."""
    return IntakeHttpBoundary(
        service,
        api_key=config.api_key,
        allowed_origins=set(config.allowed_origins),
        rate_limiter=SQLiteRateLimiter(config.rate_limit_db),
        audit_sink=SQLiteAuditSink(config.audit_db),
    )
