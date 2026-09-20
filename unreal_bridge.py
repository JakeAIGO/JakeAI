import hashlib
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

from secret_vault import _require_session

PAIR_TTL_SECONDS = 15 * 60
DEVICE_HEADER = "X-JakeAI-Unreal-Device-Token"
ALLOWED_ACTIONS = {
    "ue_status",
    "ue_list_actors",
    "ue_get_camera",
    "ue_screenshot",
    "ue_focus_actor",
    "ue_set_camera",
}

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit = os.environ.get("JAKEAI_UNREAL_DATABASE_PATH", "").strip()
    if explicit:
        return explicit
    return "/data/jakeai-unreal-bridge.db" if os.path.isdir("/data") else "/tmp/jakeai-unreal-bridge.db"

def _conn():
    path = _db_path()
    os.makedirs(os.path.dirname(path) or "/tmp", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def _hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _fernet():
    key = os.environ.get("JAKEAI_VAULT_KEY", "").strip()
    if not key:
        raise HTTPException(503, "JakeAI encryption key is not configured")
    return Fernet(key.encode("ascii"))

def _new_pair_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"

def _normalize_pair_code(value):
    return str(value or "").strip().upper().replace(" ", "")

def _new_device_secret():
    return "jau_" + secrets.token_urlsafe(40)

def init_unreal_bridge():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS unreal_devices(
      device_id TEXT PRIMARY KEY,
      device_name TEXT NOT NULL,
      token_hash TEXT NOT NULL,
      paired_at TEXT NOT NULL,
      last_seen_at TEXT,
      revoked_at TEXT,
      project_file TEXT,
      engine_version TEXT,
      current_level TEXT,
      actor_count INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS unreal_pairings(
      pair_hash TEXT PRIMARY KEY,
      pair_code_display TEXT NOT NULL,
      device_id TEXT NOT NULL,
      device_name TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at INTEGER NOT NULL,
      approved_at TEXT,
      claimed_at TEXT,
      secret_ciphertext BLOB)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS unreal_jobs(
      job_id TEXT PRIMARY KEY,
      device_id TEXT NOT NULL,
      action TEXT NOT NULL,
      args_json TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      claimed_at TEXT,
      completed_at TEXT,
      result_json TEXT,
      error_text TEXT)""")
    conn.commit()
    conn.close()

def _require_device(device_id, token):
    if not device_id or not token:
        raise HTTPException(401, "JakeAI Unreal device authentication required")
    conn = _conn()
    row = conn.execute(
        "SELECT device_id,revoked_at FROM unreal_devices WHERE device_id=? AND token_hash=?",
        (device_id, _hash(token)),
    ).fetchone()
    if not row or row["revoked_at"]:
        conn.close()
        raise HTTPException(401, "Invalid or revoked JakeAI Unreal device")
    conn.execute("UPDATE unreal_devices SET last_seen_at=? WHERE device_id=?", (_now_iso(), device_id))
    conn.commit()
    conn.close()

class PairStartRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=120)
    device_name: str = Field(min_length=1, max_length=120)

class PairCodeRequest(BaseModel):
    pair_code: str = Field(min_length=8, max_length=32)

class PairClaimRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=120)
    pair_code: str = Field(min_length=8, max_length=32)

class DevicePollRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=120)

class JobResultRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=120)
    job_id: str = Field(min_length=8, max_length=120)
    ok: bool
    result: dict = Field(default_factory=dict)
    error: str = Field(default="", max_length=4000)

class CreateJobRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=120)
    action: str = Field(min_length=3, max_length=80)
    args: dict = Field(default_factory=dict)

def _queue_job(device_id, action, args=None):
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(400, "Action is not allowed by JakeAI Unreal Bridge v1")
    job_id = "ujob_" + secrets.token_urlsafe(12)
    conn = _conn()
    exists = conn.execute("SELECT 1 FROM unreal_devices WHERE device_id=? AND revoked_at IS NULL", (device_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(404, "Paired Unreal device not found")
    conn.execute(
        "INSERT INTO unreal_jobs(job_id,device_id,action,args_json,status,created_at) VALUES (?,?,?,?,?,?)",
        (job_id, device_id, action, json.dumps(args or {}, separators=(",", ":")), "pending", _now_iso()),
    )
    conn.commit()
    conn.close()
    return job_id

def register_unreal_bridge_routes(app):
    init_unreal_bridge()

    def route(method, path):
        return getattr(app, method)(path)

    @app.get("/v1/unreal/health")
    @app.get("/api/v1/unreal/health")
    def unreal_health():
        conn = _conn()
        devices = conn.execute("SELECT COUNT(*) c FROM unreal_devices WHERE revoked_at IS NULL").fetchone()["c"]
        pending = conn.execute("SELECT COUNT(*) c FROM unreal_jobs WHERE status='pending'").fetchone()["c"]
        conn.close()
        return {
            "status": "ready",
            "mode": "outbound_polling",
            "public_inbound_to_unreal": False,
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "paired_devices": devices,
            "pending_jobs": pending,
        }

    @app.post("/v1/unreal/pair/start")
    @app.post("/api/v1/unreal/pair/start")
    def pair_start(body: PairStartRequest):
        pair_code = _new_pair_code()
        normalized = _normalize_pair_code(pair_code)
        pair_hash = _hash(normalized)
        now = int(time.time())
        conn = _conn()
        conn.execute("DELETE FROM unreal_pairings WHERE device_id=? AND claimed_at IS NULL", (body.device_id,))
        conn.execute(
            """INSERT INTO unreal_pairings
            (pair_hash,pair_code_display,device_id,device_name,created_at,expires_at,approved_at,claimed_at,secret_ciphertext)
            VALUES (?,?,?,?,?,?,NULL,NULL,NULL)""",
            (pair_hash, pair_code, body.device_id, body.device_name, _now_iso(), now + PAIR_TTL_SECONDS),
        )
        conn.commit()
        conn.close()
        return {
            "status": "pending_owner_approval",
            "pair_code": pair_code,
            "expires_in_seconds": PAIR_TTL_SECONDS,
            "approval_url": "https://jakeaiofficial.com/unreal/pair/",
        }

    @app.get("/v1/unreal/pair/lookup")
    @app.get("/api/v1/unreal/pair/lookup")
    def pair_lookup(pair_code: str, request: Request):
        _require_session(request)
        normalized = _normalize_pair_code(pair_code)
        conn = _conn()
        row = conn.execute(
            "SELECT device_id,device_name,created_at,expires_at,approved_at,claimed_at FROM unreal_pairings WHERE pair_hash=?",
            (_hash(normalized),),
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(404, "Pairing code not found")
        if int(row["expires_at"]) < int(time.time()):
            raise HTTPException(410, "Pairing code expired")
        return dict(row)

    @app.post("/v1/unreal/pair/approve")
    @app.post("/api/v1/unreal/pair/approve")
    def pair_approve(body: PairCodeRequest, request: Request):
        _require_session(request)
        normalized = _normalize_pair_code(body.pair_code)
        pair_hash = _hash(normalized)
        conn = _conn()
        row = conn.execute(
            "SELECT device_id,device_name,expires_at,approved_at,claimed_at FROM unreal_pairings WHERE pair_hash=?",
            (pair_hash,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Pairing code not found")
        if int(row["expires_at"]) < int(time.time()):
            conn.close()
            raise HTTPException(410, "Pairing code expired")
        if row["claimed_at"]:
            conn.close()
            raise HTTPException(409, "Pairing code already claimed")
        if row["approved_at"]:
            conn.close()
            return {"status": "already_approved", "device_name": row["device_name"]}
        raw_secret = _new_device_secret()
        ciphertext = _fernet().encrypt(raw_secret.encode("utf-8"))
        conn.execute(
            "UPDATE unreal_pairings SET approved_at=?,secret_ciphertext=? WHERE pair_hash=?",
            (_now_iso(), ciphertext, pair_hash),
        )
        conn.commit()
        conn.close()
        return {"status": "approved", "device_name": row["device_name"]}

    @app.post("/v1/unreal/pair/claim")
    @app.post("/api/v1/unreal/pair/claim")
    def pair_claim(body: PairClaimRequest):
        normalized = _normalize_pair_code(body.pair_code)
        pair_hash = _hash(normalized)
        conn = _conn()
        row = conn.execute(
            """SELECT device_id,device_name,expires_at,approved_at,claimed_at,secret_ciphertext
               FROM unreal_pairings WHERE pair_hash=?""",
            (pair_hash,),
        ).fetchone()
        if not row or row["device_id"] != body.device_id:
            conn.close()
            raise HTTPException(404, "Pairing request not found")
        if int(row["expires_at"]) < int(time.time()):
            conn.close()
            raise HTTPException(410, "Pairing code expired")
        if not row["approved_at"]:
            conn.close()
            return {"status": "waiting_for_owner"}
        if row["claimed_at"]:
            conn.close()
            raise HTTPException(410, "Pairing credential already claimed")
        raw_secret = _fernet().decrypt(row["secret_ciphertext"]).decode("utf-8")
        conn.execute(
            """INSERT OR REPLACE INTO unreal_devices
               (device_id,device_name,token_hash,paired_at,last_seen_at,revoked_at,project_file,engine_version,current_level,actor_count)
               VALUES (?,?,?,?,?,NULL,NULL,NULL,NULL,NULL)""",
            (row["device_id"], row["device_name"], _hash(raw_secret), _now_iso(), _now_iso()),
        )
        conn.execute(
            "UPDATE unreal_pairings SET claimed_at=?,secret_ciphertext=NULL WHERE pair_hash=?",
            (_now_iso(), pair_hash),
        )
        conn.commit()
        conn.close()
        # Automatic cloud->PC proof job. Safe and read-only.
        _queue_job(row["device_id"], "ue_status", {})
        return {
            "status": "paired",
            "device_id": row["device_id"],
            "device_name": row["device_name"],
            "device_secret": raw_secret,
            "secret_returned_once": True,
        }

    @app.post("/v1/unreal/device/poll")
    @app.post("/api/v1/unreal/device/poll")
    def device_poll(
        body: DevicePollRequest,
        x_device_token: str = Header(default="", alias=DEVICE_HEADER),
    ):
        _require_device(body.device_id, x_device_token)
        conn = _conn()
        row = conn.execute(
            """SELECT job_id,action,args_json FROM unreal_jobs
               WHERE device_id=? AND status='pending'
               ORDER BY created_at ASC LIMIT 1""",
            (body.device_id,),
        ).fetchone()
        if not row:
            conn.close()
            return {"job": None}
        conn.execute(
            "UPDATE unreal_jobs SET status='claimed',claimed_at=? WHERE job_id=? AND status='pending'",
            (_now_iso(), row["job_id"]),
        )
        conn.commit()
        conn.close()
        return {
            "job": {
                "job_id": row["job_id"],
                "action": row["action"],
                "args": json.loads(row["args_json"] or "{}"),
            }
        }

    @app.post("/v1/unreal/device/result")
    @app.post("/api/v1/unreal/device/result")
    def device_result(
        body: JobResultRequest,
        x_device_token: str = Header(default="", alias=DEVICE_HEADER),
    ):
        _require_device(body.device_id, x_device_token)
        conn = _conn()
        job = conn.execute(
            "SELECT action FROM unreal_jobs WHERE job_id=? AND device_id=?",
            (body.job_id, body.device_id),
        ).fetchone()
        if not job:
            conn.close()
            raise HTTPException(404, "JakeAI Unreal job not found")
        conn.execute(
            """UPDATE unreal_jobs SET status=?,completed_at=?,result_json=?,error_text=?
               WHERE job_id=? AND device_id=?""",
            (
                "completed" if body.ok else "failed",
                _now_iso(),
                json.dumps(body.result or {}, separators=(",", ":")),
                body.error[:4000],
                body.job_id,
                body.device_id,
            ),
        )
        if body.ok and job["action"] == "ue_status":
            status = body.result or {}
            conn.execute(
                """UPDATE unreal_devices SET project_file=?,engine_version=?,current_level=?,actor_count=?,last_seen_at=?
                   WHERE device_id=?""",
                (
                    status.get("project_file"),
                    status.get("engine_version"),
                    status.get("current_level"),
                    status.get("actor_count"),
                    _now_iso(),
                    body.device_id,
                ),
            )
        conn.commit()
        conn.close()
        return {"status": "recorded"}

    @app.get("/v1/unreal/devices")
    @app.get("/api/v1/unreal/devices")
    def list_devices(request: Request):
        _require_session(request)
        conn = _conn()
        rows = conn.execute(
            """SELECT device_id,device_name,paired_at,last_seen_at,project_file,engine_version,current_level,actor_count
               FROM unreal_devices WHERE revoked_at IS NULL ORDER BY paired_at DESC"""
        ).fetchall()
        conn.close()
        return {"devices": [dict(r) for r in rows]}

    @app.post("/v1/unreal/jobs")
    @app.post("/api/v1/unreal/jobs")
    def create_job(body: CreateJobRequest, request: Request):
        _require_session(request)
        job_id = _queue_job(body.device_id, body.action, body.args)
        return {"job_id": job_id, "status": "pending"}

    @app.get("/v1/unreal/jobs/latest")
    @app.get("/api/v1/unreal/jobs/latest")
    def latest_jobs(request: Request, device_id: str):
        _require_session(request)
        conn = _conn()
        rows = conn.execute(
            """SELECT job_id,action,status,created_at,claimed_at,completed_at,result_json,error_text
               FROM unreal_jobs WHERE device_id=? ORDER BY created_at DESC LIMIT 20""",
            (device_id,),
        ).fetchall()
        conn.close()
        data = []
        for row in rows:
            item = dict(row)
            try:
                item["result"] = json.loads(item.pop("result_json") or "{}")
            except Exception:
                item["result"] = {}
                item.pop("result_json", None)
            data.append(item)
        return {"jobs": data}
