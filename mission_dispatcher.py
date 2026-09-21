from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

MISSION_DB_PATH = os.environ.get("MISSION_DATABASE_PATH", "/data/jakeai-missions.db")
ALLOWED_STATUSES = {
    "received",
    "triaging",
    "investigating",
    "building",
    "testing",
    "needs_information",
    "ready_for_review",
    "closed",
}
WORKER_STATUSES = {
    "received",
    "triaging",
    "investigating",
    "building",
    "testing",
}
WORKER_RELEASE_STATUSES = {
    "received",
    "investigating",
    "building",
    "testing",
    "needs_information",
    "ready_for_review",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    parent = os.path.dirname(MISSION_DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(MISSION_DB_PATH, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def _init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS missions (
                id TEXT PRIMARY KEY,
                idempotency_hash TEXT NOT NULL UNIQUE,
                body_hash TEXT NOT NULL,
                signal TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT '',
                boundaries TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'general',
                completeness TEXT NOT NULL DEFAULT 'ready_for_triage',
                missing_json TEXT NOT NULL DEFAULT '[]',
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'received',
                source TEXT NOT NULL DEFAULT 'commission-bay',
                outbound_authorized INTEGER NOT NULL DEFAULT 0,
                human_release_gate INTEGER NOT NULL DEFAULT 1,
                lease_owner TEXT,
                lease_token_hash TEXT,
                lease_expires_at INTEGER,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                state_from TEXT,
                state_to TEXT,
                actor TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_status_lease ON missions(status, lease_expires_at, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_lease_owner ON missions(lease_owner, lease_expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mission_events_mission ON mission_events(mission_id, id)")
    finally:
        conn.close()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean(value, maximum: int = 5000) -> str:
    return str(value or "").strip()[:maximum]


def _classify(signal: str, outcome: str, boundaries: str) -> dict:
    all_text = f"{signal} {outcome} {boundaries}".lower()
    category = "general"
    if any(x in all_text for x in ("solar", "battery", "energy", "utility", "grid", "electric", "rfp", "rfq")):
        category = "energy"
    elif any(x in all_text for x in ("roof", "construction", "contractor", "permit")):
        category = "construction"
    elif any(x in all_text for x in ("manufactur", "factory", "machine", "quality", "supplier")):
        category = "manufacturing"
    elif any(x in all_text for x in ("farm", "crop", "agricultur", "livestock")):
        category = "agriculture"
    elif any(x in all_text for x in ("video", "music", "film", "creator", "media", "youtube", "game")):
        category = "creator-media"
    elif any(x in all_text for x in ("agent", "workflow", "automation", "api", "model", "llm", "software")):
        category = "ai-operations"

    missing = []
    if len(signal) < 20:
        missing.append("problem_detail")
    if len(outcome) < 10:
        missing.append("desired_outcome")

    return {
        "category": category,
        "completeness": "needs_detail" if missing else "ready_for_triage",
        "missing": missing,
        "priority": "normal",
    }


def _event(conn: sqlite3.Connection, mission_id: str, event_type: str, state_from: Optional[str], state_to: Optional[str], actor: str, note: str = "") -> None:
    conn.execute(
        """
        INSERT INTO mission_events(mission_id,event_type,state_from,state_to,actor,note,created_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (mission_id, event_type, state_from, state_to, actor[:120], note[:2000], _now_iso()),
    )


def _mission_dict(row: sqlite3.Row, *, include_private: bool = True) -> dict:
    missing = []
    try:
        missing = json.loads(row["missing_json"] or "[]")
    except Exception:
        pass
    base = {
        "id": row["id"],
        "status": row["status"],
        "triage": {
            "category": row["category"],
            "completeness": row["completeness"],
            "missing": missing,
            "priority": row["priority"],
        },
        "created": row["created_at"],
        "updated": row["updated_at"],
        "lease": {
            "owner": row["lease_owner"],
            "expires_at": row["lease_expires_at"],
            "active": bool(row["lease_owner"] and row["lease_expires_at"] and row["lease_expires_at"] > int(time.time())),
            "attempts": row["attempts"],
        },
        "controls": {
            "human_release_gate": bool(row["human_release_gate"]),
            "outbound_authorized": bool(row["outbound_authorized"]),
        },
    }
    if include_private:
        base.update(
            {
                "signal": row["signal"],
                "outcome": row["outcome"],
                "boundaries": row["boundaries"],
                "source": row["source"],
                "last_error": row["last_error"],
            }
        )
    return base


def _require_control(authorization: Optional[str]) -> None:
    expected = os.environ.get("MISSION_CONTROL_TOKEN", "").strip()
    candidate = (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Mission Control authorization is not configured")
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _require_worker(worker_token: Optional[str]) -> None:
    expected = os.environ.get("MISSION_WORKER_TOKEN", "").strip()
    candidate = (worker_token or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Mission worker authorization is not configured")
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


class MissionIntake(BaseModel):
    signal: str = Field(min_length=1, max_length=5000)
    outcome: str = Field(default="", max_length=5000)
    boundaries: str = Field(default="", max_length=5000)
    idempotency_key: str = Field(min_length=16, max_length=200)
    website: str = Field(default="", max_length=200)


class MissionAdminUpdate(BaseModel):
    id: str = Field(min_length=8, max_length=100)
    status: str = Field(max_length=40)
    note: str = Field(default="", max_length=1200)


class MissionClaimRequest(BaseModel):
    worker_id: str = Field(min_length=3, max_length=120)
    statuses: list[str] = Field(default_factory=lambda: ["received"])
    lease_seconds: int = Field(default=300, ge=30, le=900)


class MissionLeaseRequest(BaseModel):
    worker_id: str = Field(min_length=3, max_length=120)
    mission_id: str = Field(min_length=8, max_length=100)
    lease_token: str = Field(min_length=20, max_length=200)
    lease_seconds: int = Field(default=300, ge=30, le=900)


class MissionReleaseRequest(MissionLeaseRequest):
    next_status: str = Field(default="received", max_length=40)
    note: str = Field(default="", max_length=1200)
    error: str = Field(default="", max_length=1200)


def register_mission_dispatcher_routes(app) -> None:
    _init_db()

    @app.post("/v1/missions/intake")
    @app.post("/api/v1/missions/intake")
    def mission_intake(req: MissionIntake):
        if req.website.strip():
            return {"ok": True, "accepted": True}

        signal = _clean(req.signal)
        outcome = _clean(req.outcome)
        boundaries = _clean(req.boundaries)
        idem_hash = _hash(req.idempotency_key)
        body_hash = _hash(json.dumps({"signal": signal, "outcome": outcome, "boundaries": boundaries}, sort_keys=True))
        triage = _classify(signal, outcome, boundaries)
        initial_status = "needs_information" if triage["completeness"] == "needs_detail" else "received"
        mission_id = "JAI-MISSION-" + uuid.uuid4().hex[:16].upper()
        now = _now_iso()

        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM missions WHERE idempotency_hash=?", (idem_hash,)).fetchone()
            if existing:
                if existing["body_hash"] != body_hash:
                    conn.execute("ROLLBACK")
                    raise HTTPException(status_code=409, detail="Idempotency key was already used for different mission data")
                conn.execute("COMMIT")
                return {"ok": True, "duplicate": True, "mission": _mission_dict(existing, include_private=False)}

            conn.execute(
                """
                INSERT INTO missions(
                    id,idempotency_hash,body_hash,signal,outcome,boundaries,category,completeness,
                    missing_json,priority,status,source,outbound_authorized,human_release_gate,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?)
                """,
                (
                    mission_id,
                    idem_hash,
                    body_hash,
                    signal,
                    outcome,
                    boundaries,
                    triage["category"],
                    triage["completeness"],
                    json.dumps(triage["missing"]),
                    triage["priority"],
                    initial_status,
                    "commission-bay",
                    now,
                    now,
                ),
            )
            _event(conn, mission_id, "received", None, initial_status, "commission-bay")
            row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            conn.execute("COMMIT")
            return {"ok": True, "duplicate": False, "mission": _mission_dict(row, include_private=False)}
        except HTTPException:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Mission intake could not be persisted")
        finally:
            conn.close()

    @app.get("/v1/missions/public-status")
    @app.get("/api/v1/missions/public-status")
    def mission_public_status():
        conn = _connect()
        try:
            rows = conn.execute("SELECT status,COUNT(*) AS n FROM missions GROUP BY status").fetchall()
            total = conn.execute("SELECT COUNT(*) AS n FROM missions").fetchone()["n"]
            latest = conn.execute("SELECT created_at FROM missions ORDER BY created_at DESC LIMIT 1").fetchone()
            return {
                "service": "JakeAI Mission Intake",
                "accepting": True,
                "total": total,
                "counts": {r["status"]: r["n"] for r in rows},
                "latest_received_at": latest["created_at"] if latest else None,
                "public_detail": "aggregate-only",
                "dispatcher": "transactional-sqlite-lease-v1",
            }
        finally:
            conn.close()

    @app.get("/v1/mission-control")
    @app.get("/api/v1/mission-control")
    def mission_control_list(authorization: Optional[str] = Header(None, alias="Authorization")):
        _require_control(authorization)
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM missions ORDER BY created_at DESC LIMIT 250").fetchall()
            counts_rows = conn.execute("SELECT status,COUNT(*) AS n FROM missions GROUP BY status").fetchall()
            now = int(time.time())
            leased = conn.execute("SELECT COUNT(*) AS n FROM missions WHERE lease_owner IS NOT NULL AND lease_expires_at>?", (now,)).fetchone()["n"]
            missions = []
            for row in rows:
                item = _mission_dict(row)
                events = conn.execute(
                    "SELECT event_type,state_from,state_to,actor,note,created_at FROM mission_events WHERE mission_id=? ORDER BY id DESC LIMIT 30",
                    (row["id"],),
                ).fetchall()
                item["events"] = [dict(e) for e in events]
                missions.append(item)
            return {
                "service": "JakeAI Mission Control",
                "total": len(missions),
                "counts": {r["status"]: r["n"] for r in counts_rows},
                "leased": leased,
                "missions": missions,
                "controls": {"human_release_gate": True, "outbound_default": "blocked"},
                "dispatcher": {"mode": "transactional_sqlite", "lease_max_seconds": 900},
            }
        finally:
            conn.close()

    @app.patch("/v1/mission-control")
    @app.patch("/api/v1/mission-control")
    def mission_control_update(req: MissionAdminUpdate, authorization: Optional[str] = Header(None, alias="Authorization")):
        _require_control(authorization)
        if req.status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid mission state")
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM missions WHERE id=?", (req.id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=404, detail="Mission not found")
            old = row["status"]
            conn.execute(
                """
                UPDATE missions SET status=?, updated_at=?, outbound_authorized=0, human_release_gate=1,
                lease_owner=NULL, lease_token_hash=NULL, lease_expires_at=NULL
                WHERE id=?
                """,
                (req.status, _now_iso(), req.id),
            )
            _event(conn, req.id, "status_changed", old, req.status, "mission-control", req.note)
            updated = conn.execute("SELECT * FROM missions WHERE id=?", (req.id,)).fetchone()
            conn.execute("COMMIT")
            return {"ok": True, "mission": _mission_dict(updated)}
        finally:
            conn.close()

    @app.post("/v1/missions/claim")
    @app.post("/api/v1/missions/claim")
    def mission_claim(req: MissionClaimRequest, x_jakeai_worker_token: Optional[str] = Header(None, alias="X-JakeAI-Worker-Token")):
        _require_worker(x_jakeai_worker_token)
        statuses = [s for s in req.statuses if s in WORKER_STATUSES]
        if not statuses:
            raise HTTPException(status_code=400, detail="No claimable statuses requested")
        now = int(time.time())
        lease_token = secrets.token_urlsafe(32)
        lease_hash = _hash(lease_token)
        lease_expires = now + req.lease_seconds
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            held = conn.execute(
                "SELECT id FROM missions WHERE lease_owner=? AND lease_expires_at>?",
                (req.worker_id, now),
            ).fetchone()
            if held:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=409, detail={"message": "Worker already holds an active lease", "mission_id": held["id"]})

            placeholders = ",".join("?" for _ in statuses)
            row = conn.execute(
                f"""
                SELECT * FROM missions
                WHERE status IN ({placeholders})
                  AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at<=?)
                ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, created_at ASC
                LIMIT 1
                """,
                (*statuses, now),
            ).fetchone()
            if not row:
                conn.execute("COMMIT")
                return {"claimed": False}

            old = row["status"]
            next_status = "triaging" if old == "received" else old
            conn.execute(
                """
                UPDATE missions
                SET status=?, lease_owner=?, lease_token_hash=?, lease_expires_at=?,
                    attempts=attempts+1, updated_at=?, outbound_authorized=0, human_release_gate=1
                WHERE id=? AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at<=?)
                """,
                (next_status, req.worker_id, lease_hash, lease_expires, _now_iso(), row["id"], now),
            )
            if conn.total_changes < 1:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=409, detail="Mission was claimed by another worker")
            _event(conn, row["id"], "lease_claimed", old, next_status, req.worker_id, f"Lease until {lease_expires}")
            claimed = conn.execute("SELECT * FROM missions WHERE id=?", (row["id"],)).fetchone()
            conn.execute("COMMIT")
            mission = _mission_dict(claimed)
            return {
                "claimed": True,
                "mission": mission,
                "lease": {
                    "token": lease_token,
                    "expires_at": lease_expires,
                    "seconds": req.lease_seconds,
                },
            }
        finally:
            conn.close()

    @app.post("/v1/missions/heartbeat")
    @app.post("/api/v1/missions/heartbeat")
    def mission_heartbeat(req: MissionLeaseRequest, x_jakeai_worker_token: Optional[str] = Header(None, alias="X-JakeAI-Worker-Token")):
        _require_worker(x_jakeai_worker_token)
        now = int(time.time())
        expires = now + req.lease_seconds
        conn = _connect()
        try:
            cur = conn.execute(
                """
                UPDATE missions SET lease_expires_at=?,updated_at=?
                WHERE id=? AND lease_owner=? AND lease_token_hash=? AND lease_expires_at>?
                """,
                (expires, _now_iso(), req.mission_id, req.worker_id, _hash(req.lease_token), now),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Lease is missing, expired, or owned by another worker")
            return {"ok": True, "mission_id": req.mission_id, "lease_expires_at": expires}
        finally:
            conn.close()

    @app.post("/v1/missions/release")
    @app.post("/api/v1/missions/release")
    def mission_release(req: MissionReleaseRequest, x_jakeai_worker_token: Optional[str] = Header(None, alias="X-JakeAI-Worker-Token")):
        _require_worker(x_jakeai_worker_token)
        if req.next_status not in WORKER_RELEASE_STATUSES:
            raise HTTPException(status_code=400, detail="Workers cannot release into that state")
        now = int(time.time())
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM missions WHERE id=?", (req.mission_id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=404, detail="Mission not found")
            if row["lease_owner"] != req.worker_id or row["lease_token_hash"] != _hash(req.lease_token) or not row["lease_expires_at"] or row["lease_expires_at"] <= now:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=409, detail="Lease is missing, expired, or owned by another worker")
            old = row["status"]
            conn.execute(
                """
                UPDATE missions
                SET status=?, lease_owner=NULL, lease_token_hash=NULL, lease_expires_at=NULL,
                    last_error=?, updated_at=?, outbound_authorized=0, human_release_gate=1
                WHERE id=?
                """,
                (req.next_status, _clean(req.error, 1200) or None, _now_iso(), req.mission_id),
            )
            _event(conn, req.mission_id, "lease_released", old, req.next_status, req.worker_id, req.note or req.error)
            updated = conn.execute("SELECT * FROM missions WHERE id=?", (req.mission_id,)).fetchone()
            conn.execute("COMMIT")
            return {"ok": True, "mission": _mission_dict(updated)}
        finally:
            conn.close()

    @app.post("/v1/mission-control/dispatcher-self-test")
    @app.post("/api/v1/mission-control/dispatcher-self-test")
    def mission_dispatcher_self_test(authorization: Optional[str] = Header(None, alias="Authorization")):
        _require_control(authorization)
        test_id = "JAI-QA-" + uuid.uuid4().hex[:16].upper()
        idem = _hash("dispatcher-self-test-" + test_id)
        now_iso = _now_iso()
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO missions(
                    id,idempotency_hash,body_hash,signal,outcome,boundaries,category,completeness,
                    missing_json,priority,status,source,outbound_authorized,human_release_gate,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?)
                """,
                (
                    test_id,
                    idem,
                    idem,
                    "Internal dispatcher concurrency self-test",
                    "Exactly one of two simultaneous workers may acquire the lease.",
                    "Synthetic QA only; never leaves Mission Control.",
                    "ai-operations",
                    "ready_for_triage",
                    "[]",
                    "normal",
                    "received",
                    "dispatcher-self-test",
                    now_iso,
                    now_iso,
                ),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()

        barrier = threading.Barrier(2)

        def contender(worker_id: str) -> bool:
            db = _connect()
            try:
                barrier.wait(timeout=5)
                db.execute("BEGIN IMMEDIATE")
                now = int(time.time())
                row = db.execute(
                    """
                    SELECT id FROM missions
                    WHERE id=? AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at<=?)
                    """,
                    (test_id, now),
                ).fetchone()
                if not row:
                    db.execute("COMMIT")
                    return False
                token_hash = _hash(secrets.token_urlsafe(32))
                cur = db.execute(
                    """
                    UPDATE missions
                    SET lease_owner=?,lease_token_hash=?,lease_expires_at=?,attempts=attempts+1,updated_at=?
                    WHERE id=? AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at<=?)
                    """,
                    (worker_id, token_hash, now + 60, _now_iso(), test_id, now),
                )
                db.execute("COMMIT")
                return cur.rowcount == 1
            except Exception:
                try:
                    db.execute("ROLLBACK")
                except Exception:
                    pass
                return False
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(contender, ("qa-worker-a", "qa-worker-b")))

        winner_count = sum(1 for r in results if r)
        verify = _connect()
        try:
            row = verify.execute("SELECT lease_owner,attempts FROM missions WHERE id=?", (test_id,)).fetchone()
            lease_owner = row["lease_owner"] if row else None
            attempts = row["attempts"] if row else 0
            passed = winner_count == 1 and bool(lease_owner) and attempts == 1
            verify.execute("BEGIN IMMEDIATE")
            verify.execute("DELETE FROM mission_events WHERE mission_id=?", (test_id,))
            verify.execute("DELETE FROM missions WHERE id=?", (test_id,))
            verify.execute("COMMIT")
        finally:
            verify.close()

        return {
            "status": "passed" if passed else "failed",
            "atomic_claim": passed,
            "contenders": 2,
            "winners": winner_count,
            "recorded_attempts": attempts,
            "winner": lease_owner,
            "synthetic_mission_removed": True,
        }

    @app.get("/v1/missions/dispatcher-health")
    @app.get("/api/v1/missions/dispatcher-health")
    def mission_dispatcher_health():
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("COMMIT")
            return {
                "status": "ready",
                "dispatcher": "transactional-sqlite-lease-v1",
                "database": "persistent-volume",
                "atomic_claim": True,
                "max_lease_seconds": 900,
                "human_release_gate": True,
                "outbound_default": "blocked",
            }
        finally:
            conn.close()


_init_db()
