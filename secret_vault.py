import hashlib
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

COOKIE_NAME = "jakeai_vault_session"
ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")

class SecretStoreRequest(BaseModel):
    alias: str = Field(min_length=2, max_length=80)
    value: str = Field(min_length=1, max_length=65536)
    provider: str = Field(default="", max_length=120)
    purpose: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit = os.environ.get("JAKEAI_VAULT_DATABASE_PATH", "").strip()
    if explicit:
        return explicit
    return "/data/jakeai-secrets.db" if os.path.isdir("/data") else "/tmp/jakeai-secrets.db"

def _conn():
    path = _db_path()
    os.makedirs(os.path.dirname(path) or "/tmp", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def _fernet():
    key = os.environ.get("JAKEAI_VAULT_KEY", "").strip()
    if not key:
        raise HTTPException(503, "JakeAI Secret Vault encryption is not configured")
    return Fernet(key.encode("ascii"))

def init_secret_vault():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS jakeai_secrets(
      alias TEXT PRIMARY KEY,
      ciphertext BLOB NOT NULL,
      content_type TEXT NOT NULL,
      provider TEXT,
      purpose TEXT,
      notes TEXT,
      byte_length INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jakeai_vault_sessions(
      token_hash TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      expires_at INTEGER NOT NULL,
      revoked_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jakeai_vault_bootstrap(
      token_hash TEXT PRIMARY KEY,
      used_at TEXT NOT NULL)""")
    conn.commit()
    conn.close()

def _hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _normalize_alias(alias):
    value = str(alias or "").strip().lower()
    if not ALIAS_RE.fullmatch(value):
        raise HTTPException(400, "Alias must use lowercase letters, numbers, dots, dashes or underscores")
    return value

def _issue_session():
    raw = secrets.token_urlsafe(36)
    conn = _conn()
    conn.execute(
        "INSERT INTO jakeai_vault_sessions(token_hash,created_at,expires_at,revoked_at) VALUES (?,?,?,NULL)",
        (_hash(raw), _now_iso(), int(time.time()) + 31536000),
    )
    conn.commit()
    conn.close()
    return raw

def _require_session(request):
    raw = request.cookies.get(COOKIE_NAME, "")
    if not raw:
        raise HTTPException(401, "JakeAI Secret Vault device enrollment required")
    conn = _conn()
    row = conn.execute(
        "SELECT expires_at,revoked_at FROM jakeai_vault_sessions WHERE token_hash=?",
        (_hash(raw),),
    ).fetchone()
    conn.close()
    if not row or row["revoked_at"] or int(row["expires_at"]) < int(time.time()):
        raise HTTPException(401, "JakeAI Secret Vault session is invalid or expired")

def _store(alias, payload, content_type, provider="", purpose="", notes=""):
    alias = _normalize_alias(alias)
    if not payload:
        raise HTTPException(400, "Secret value is empty")
    if len(payload) > 65536:
        raise HTTPException(413, "Secret payload exceeds the 64 KB vault limit")
    ciphertext = _fernet().encrypt(payload)
    now = _now_iso()
    conn = _conn()
    existing = conn.execute("SELECT created_at FROM jakeai_secrets WHERE alias=?", (alias,)).fetchone()
    created = existing["created_at"] if existing else now
    conn.execute(
        """INSERT OR REPLACE INTO jakeai_secrets
        (alias,ciphertext,content_type,provider,purpose,notes,byte_length,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (alias, ciphertext, content_type, provider.strip(), purpose.strip(), notes.strip(), len(payload), created, now),
    )
    conn.commit()
    conn.close()
    return {"alias": alias, "stored": True, "byte_length": len(payload), "raw_value_returned": False}

def register_secret_vault_routes(app):
    init_secret_vault()

    @app.get("/v1/secrets/health")
    def vault_health():
        configured = bool(os.environ.get("JAKEAI_VAULT_KEY", "").strip())
        return {"status": "ready" if configured else "gated", "encrypted_at_rest": configured, "raw_reveal_ui": False}

    @app.get("/v1/secrets/bootstrap")
    def vault_bootstrap(token: str):
        expected = os.environ.get("JAKEAI_VAULT_BOOTSTRAP_TOKEN", "").strip()
        if not expected or not secrets.compare_digest(token or "", expected):
            raise HTTPException(403, "Invalid JakeAI Secret Vault enrollment token")
        token_hash = _hash(token)
        conn = _conn()
        used = conn.execute("SELECT used_at FROM jakeai_vault_bootstrap WHERE token_hash=?", (token_hash,)).fetchone()
        if used:
            conn.close()
            raise HTTPException(410, "This one-time JakeAI Secret Vault enrollment link has already been used")
        conn.execute("INSERT INTO jakeai_vault_bootstrap(token_hash,used_at) VALUES (?,?)", (token_hash, _now_iso()))
        conn.commit()
        conn.close()
        session = _issue_session()
        response = RedirectResponse("https://jakeaiofficial.com/secrets/", 303)
        response.set_cookie(COOKIE_NAME, session, httponly=True, secure=True, samesite="strict", max_age=31536000, path="/")
        return response

    @app.get("/v1/secrets/list")
    def vault_list(request: Request):
        _require_session(request)
        conn = _conn()
        rows = conn.execute(
            "SELECT alias,content_type,provider,purpose,notes,byte_length,created_at,updated_at FROM jakeai_secrets ORDER BY updated_at DESC"
        ).fetchall()
        conn.close()
        return {"secrets": [dict(r) for r in rows], "raw_values_included": False}

    @app.post("/v1/secrets/store")
    def vault_store(body: SecretStoreRequest, request: Request):
        _require_session(request)
        return _store(body.alias, body.value.encode("utf-8"), "text/plain; charset=utf-8", body.provider, body.purpose, body.notes)

    @app.post("/v1/secrets/store-file")
    async def vault_store_file(
        request: Request,
        alias: str = Form(...),
        provider: str = Form(""),
        purpose: str = Form(""),
        notes: str = Form(""),
        secret_file: UploadFile = File(...),
    ):
        _require_session(request)
        payload = await secret_file.read(65537)
        return _store(alias, payload, secret_file.content_type or "application/octet-stream", provider, purpose, notes)

    @app.post("/v1/secrets/logout")
    def vault_logout(request: Request):
        raw = request.cookies.get(COOKIE_NAME, "")
        if raw:
            conn = _conn()
            conn.execute("UPDATE jakeai_vault_sessions SET revoked_at=? WHERE token_hash=?", (_now_iso(), _hash(raw)))
            conn.commit()
            conn.close()
        response = JSONResponse({"status": "logged_out"})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response
