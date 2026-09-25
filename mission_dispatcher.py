from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import sqlite3
import time
import uuid
import threading
import urllib.error
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

MISSION_DB_PATH = os.environ.get("MISSION_DATABASE_PATH", "/data/jakeai-missions.db")
TRAFFIC_QUALITY_START = os.environ.get("TRAFFIC_QUALITY_START", "2026-09-21T02:07:00+00:00")
MISSION_CONTROL_COOKIE = "jakeai_owner_session"
MISSION_CONTROL_SESSION_DAYS = 30
ALLOWED_STATUSES = {
    "received",
    "triaging",
    "investigating",
    "building",
    "testing",
    "needs_information",
    "ready_for_review",
    "approved",
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
                customer_token_hash TEXT,
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_artifacts (
                artifact_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                manifest_json TEXT NOT NULL,
                validation_json TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                human_approved INTEGER NOT NULL DEFAULT 0,
                deployed INTEGER NOT NULL DEFAULT 0,
                released_to_customer INTEGER NOT NULL DEFAULT 0,
                released_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS owner_enrollment_uses (
                token_hash TEXT PRIMARY KEY,
                used_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traffic_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                visitor_hash TEXT NOT NULL,
                session_hash TEXT NOT NULL,
                event_type TEXT NOT NULL,
                path TEXT NOT NULL,
                referrer_host TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'direct',
                medium TEXT NOT NULL DEFAULT '',
                campaign TEXT NOT NULL DEFAULT '',
                device TEXT NOT NULL DEFAULT 'unknown',
                is_internal INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                agent TEXT NOT NULL,
                purpose TEXT NOT NULL,
                verification TEXT NOT NULL,
                path TEXT NOT NULL,
                method TEXT NOT NULL,
                response_status INTEGER,
                referrer_host TEXT NOT NULL DEFAULT '',
                machine_surface INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(missions)").fetchall()}
        if "analysis_json" not in columns:
            conn.execute("ALTER TABLE missions ADD COLUMN analysis_json TEXT")
        if "customer_token_hash" not in columns:
            conn.execute("ALTER TABLE missions ADD COLUMN customer_token_hash TEXT")
        artifact_columns = {row["name"] for row in conn.execute("PRAGMA table_info(mission_artifacts)").fetchall()}
        if "review_note" not in artifact_columns:
            conn.execute("ALTER TABLE mission_artifacts ADD COLUMN review_note TEXT")
        if "reviewed_at" not in artifact_columns:
            conn.execute("ALTER TABLE mission_artifacts ADD COLUMN reviewed_at TEXT")
        if "released_to_customer" not in artifact_columns:
            conn.execute("ALTER TABLE mission_artifacts ADD COLUMN released_to_customer INTEGER NOT NULL DEFAULT 0")
        if "released_at" not in artifact_columns:
            conn.execute("ALTER TABLE mission_artifacts ADD COLUMN released_at TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_status_lease ON missions(status, lease_expires_at, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_lease_owner ON missions(lease_owner, lease_expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mission_events_mission ON mission_events(mission_id, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mission_artifacts_mission ON mission_artifacts(mission_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_created ON traffic_events(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_type_created ON traffic_events(event_type, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_visitor_created ON traffic_events(visitor_hash, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_session_created ON traffic_events(session_hash, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_created ON agent_events(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_provider_created ON agent_events(provider, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_path_created ON agent_events(path, created_at)")
    finally:
        conn.close()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean(value, maximum: int = 5000) -> str:
    return str(value or "").strip()[:maximum]


def _customer_token(idempotency_key: str) -> str:
    secret = os.environ.get("MISSION_CONTROL_TOKEN", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Customer mission portal is not configured")
    return hmac.new(
        secret.encode("utf-8"),
        ("customer-portal:" + idempotency_key).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:48]


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
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None,
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


def _session_secret() -> str:
    return os.environ.get("MISSION_CONTROL_SESSION_SECRET", "").strip() or os.environ.get("MISSION_CONTROL_TOKEN", "").strip()


def _issue_owner_session() -> str:
    secret = _session_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Mission Control session authorization is not configured")
    expires = int(time.time()) + (MISSION_CONTROL_SESSION_DAYS * 86400)
    payload = f"owner:{expires}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _owner_session_validation_secrets() -> list[str]:
    """Return current + legacy session signing keys for safe key rotation.

    New sessions are always issued with MISSION_CONTROL_SESSION_SECRET when
    configured. Older sessions may have been signed with MISSION_CONTROL_TOKEN
    before the dedicated session secret existed. Accept those legacy cookies
    only until their embedded expiry; no legacy key is used to issue new ones.
    """
    values = [
        os.environ.get("MISSION_CONTROL_SESSION_SECRET", "").strip(),
        os.environ.get("MISSION_CONTROL_TOKEN", "").strip(),
    ]
    out = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _valid_owner_session(value: str) -> bool:
    try:
        expires_text, signature = (value or "").split(".", 1)
        expires = int(expires_text)
    except Exception:
        return False
    if expires <= int(time.time()):
        return False
    payload = f"owner:{expires}"
    for secret in _owner_session_validation_secrets():
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(signature, expected_signature):
            return True
    return False


def _require_control(authorization: Optional[str], request: Optional[Request] = None) -> None:
    expected = os.environ.get("MISSION_CONTROL_TOKEN", "").strip()
    candidate = (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Mission Control authorization is not configured")
    if candidate and hmac.compare_digest(candidate, expected):
        return
    if request and _valid_owner_session(request.cookies.get(MISSION_CONTROL_COOKIE, "")):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def _require_worker(worker_token: Optional[str]) -> None:
    expected = os.environ.get("MISSION_WORKER_TOKEN", "").strip()
    candidate = (worker_token or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Mission worker authorization is not configured")
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _direct_runtime_url() -> str:
    return os.environ.get("DIRECT_RUNTIME_URL", "").strip()


def _direct_runtime_token() -> str:
    return os.environ.get("DIRECT_RUNTIME_INTERNAL_TOKEN", "").strip()


def _extract_json_object(text_value: str) -> dict:
    raw = (text_value or "").strip()
    if not raw:
        raise ValueError("empty model response")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        parsed = json.loads(raw[start:end + 1])
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("model did not return a JSON object")


def _tinyfish_key() -> str:
    return os.environ.get("TINYFISH_API_KEY", "").strip()


def _tinyfish_search(query: str, purpose: str) -> list[dict]:
    key = _tinyfish_key()
    if not key:
        return []
    params = urllib.parse.urlencode({
        "query": _clean(query, 500),
        "purpose": _clean(purpose, 1000),
        "location": "US",
        "language": "en",
        "domain_type": "web",
        "page": 0,
    })
    req = urllib.request.Request(
        "https://api.search.tinyfish.ai?" + params,
        headers={
            "X-API-Key": key,
            "User-Agent": "JakeAI-Mission-Evidence/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"TinyFish search failed HTTP {exc.code}", flush=True)
        return []
    except Exception as exc:
        print(f"TinyFish search failed: {type(exc).__name__}", flush=True)
        return []
    results = []
    for item in (data.get("results") or [])[:5]:
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        results.append({
            "title": _clean(item.get("title"), 500),
            "url": url[:2000],
            "snippet": _clean(item.get("snippet"), 1200),
            "site_name": _clean(item.get("site_name"), 200),
            "date": _clean(item.get("date"), 100),
        })
    return results


def _tinyfish_fetch(urls: list[str], purpose: str) -> list[dict]:
    key = _tinyfish_key()
    clean_urls = []
    for url in urls:
        value = str(url or "").strip()
        if value.startswith(("http://", "https://")) and value not in clean_urls:
            clean_urls.append(value)
        if len(clean_urls) >= 5:
            break
    if not key or not clean_urls:
        return []

    payload = {
        "urls": clean_urls,
        "purpose": _clean(purpose, 1000),
        "format": "markdown",
        "links": False,
        "image_links": False,
        "ttl": 3600,
        "per_url_timeout_ms": 30000,
    }
    req = urllib.request.Request(
        "https://api.fetch.tinyfish.ai",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-API-Key": key,
            "Content-Type": "application/json",
            "User-Agent": "JakeAI-Mission-Evidence/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"TinyFish fetch failed HTTP {exc.code}", flush=True)
        return []
    except Exception as exc:
        print(f"TinyFish fetch failed: {type(exc).__name__}", flush=True)
        return []

    pages = []
    for item in data.get("results") or []:
        text_value = str(item.get("text") or "").strip()
        pages.append({
            "url": str(item.get("final_url") or item.get("url") or "")[:2000],
            "title": _clean(item.get("title"), 500),
            "description": _clean(item.get("description"), 1000),
            "published_date": _clean(item.get("published_date"), 100),
            "text_excerpt": text_value[:4500],
        })
    return pages


def _synthesize_investigation_with_evidence(mission: dict, planning: dict, search_results: list[dict], pages: list[dict]) -> dict:
    runtime_url = _direct_runtime_url()
    runtime_token = _direct_runtime_token()
    if not runtime_url or not runtime_token:
        return planning

    evidence = {
        "search_results": search_results[:12],
        "pages": pages[:5],
    }
    prompt = f"""You are the JakeAI evidence synthesis worker.

You are given a customer mission, a preliminary investigation, and external public-web evidence gathered by JakeAI's search/fetch adapter. Use ONLY the supplied evidence for web-derived factual claims. Do not invent sources. Every URL in sources_used must exactly match a URL present in the evidence object. Distinguish source-backed facts from assumptions and unresolved unknowns.

Return ONE JSON object only with this exact top-level schema:
{{
  "summary": "short evidence-backed investigation summary",
  "problem_definition": "precise problem statement",
  "known": ["mission facts and source-backed facts"],
  "assumptions": ["assumptions, clearly labeled"],
  "unknowns": ["important unknowns"],
  "existing_capability_assessment": {{
    "candidate_ids": ["JakeAI capability IDs if relevant"],
    "reuse_likely": true,
    "reason": "why"
  }},
  "evidence_needed": ["remaining evidence gaps"],
  "research_queries": ["additional bounded queries only if still needed"],
  "sources_used": [{{"title":"source title","url":"exact supplied URL","supports":"brief claim supported"}}],
  "risks": ["material risks or constraints"],
  "recommended_route": "building|needs_information|ready_for_review",
  "route_reason": "why",
  "proposed_next_step": "bounded next step",
  "confidence": "low|medium|high"
}}

Routing rules:
- "needs_information" when customer clarification is essential.
- "building" only if the mission is sufficiently defined and the evidence supports a concrete bounded prototype/build as the next step.
- "ready_for_review" when evidence is sufficient for a human decision or when consequential next actions require approval.
- Human release gate stays ON. Outbound contact, publishing, purchases and deployment remain blocked.

MISSION:
{json.dumps(mission, ensure_ascii=False)[:12000]}

PRELIMINARY INVESTIGATION:
{json.dumps(planning, ensure_ascii=False)[:10000]}

EXTERNAL EVIDENCE:
{json.dumps(evidence, ensure_ascii=False)[:28000]}
"""
    payload = {"prompt": prompt, "workflow": "research"}
    request = urllib.request.Request(
        runtime_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-JakeAI-Internal-Token": runtime_token,
            "Content-Type": "application/json",
            "User-Agent": "JakeAI-Mission-Evidence-Synthesis/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            data = json.loads(response.read().decode("utf-8"))
        report = _extract_json_object(str(data.get("text") or ""))
    except Exception:
        return planning

    route = str(report.get("recommended_route") or "").strip()
    if route not in {"building", "needs_information", "ready_for_review"}:
        report["recommended_route"] = "ready_for_review"
        report["route_reason"] = "Evidence synthesis did not return an allowed route; human review required."
    return report


def _call_build_runtime(mission: dict) -> dict:
    runtime_url = _direct_runtime_url()
    runtime_token = _direct_runtime_token()
    if not runtime_url or not runtime_token:
        raise HTTPException(status_code=503, detail="JakeAI build runtime is not configured")

    prompt = f"""You are the bounded JakeAI Build worker.

Create a SMALL, REVIEWABLE prototype package for the mission below. This is a draft artifact for human review, not a deployment. Do not send messages, publish, purchase, modify external systems, call external APIs, or claim that anything was deployed. Do not include real secrets, credentials, tokens, private keys, or customer data beyond what appears in the mission.

Return ONE JSON object only with this exact top-level schema:
{{
  "title": "short artifact title",
  "artifact_type": "prototype|workflow_spec|code_bundle|document_bundle",
  "summary": "what was built",
  "files": [
    {{
      "path": "relative/path.ext",
      "purpose": "why this file exists",
      "content": "complete draft file contents"
    }}
  ],
  "test_plan": ["reviewable test or check"],
  "limitations": ["known limitation"],
  "approval_requirements": ["what must be approved before any external action"],
  "next_step": "what the human should review next"
}}

Rules:
- Maximum 5 files.
- File paths must be relative and must not contain '..', absolute paths, home directories, or environment-secret paths.
- Prefer the smallest viable artifact that demonstrates the approach.
- The artifact must be understandable without executing arbitrary shell commands.
- Do not include destructive commands.
- Human approval is required before deployment, publication, customer contact, purchasing, or changing an external system.

MISSION:
{json.dumps(mission, ensure_ascii=False)[:18000]}
"""
    payload = {"prompt": prompt, "workflow": "site"}
    request = urllib.request.Request(
        runtime_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-JakeAI-Internal-Token": runtime_token,
            "Content-Type": "application/json",
            "User-Agent": "JakeAI-Mission-Builder/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=502, detail="JakeAI build runtime rejected the request") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="JakeAI build runtime is unavailable") from exc

    raw_text = str(data.get("text") or "").strip()
    try:
        package = _extract_json_object(raw_text)
    except Exception:
        fallback_prompt = f"""Create ONE compact draft artifact for this mission.

Return ONLY the complete file contents, with no markdown fences and no explanation.
Keep it under 3500 characters.
If the mission is for a browser/site tool, return one self-contained HTML file with inline CSS/JS and no network calls.
Otherwise return a concise Markdown implementation artifact.
Do not include secrets, credentials, destructive commands, deployment steps, outreach, purchases, or external actions.

MISSION:
{json.dumps(mission, ensure_ascii=False)[:14000]}
"""
        fallback_payload = {"prompt": fallback_prompt, "workflow": "site"}
        fallback_request = urllib.request.Request(
            runtime_url,
            data=json.dumps(fallback_payload).encode("utf-8"),
            headers={
                "X-JakeAI-Internal-Token": runtime_token,
                "Content-Type": "application/json",
                "User-Agent": "JakeAI-Mission-Builder-Fallback/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(fallback_request, timeout=55) as response:
                fallback_data = json.loads(response.read().decode("utf-8"))
            artifact_text = str(fallback_data.get("text") or "").strip()
        except Exception as exc:
            raise HTTPException(status_code=502, detail="JakeAI build runtime returned malformed output") from exc
        if artifact_text.startswith("```") and artifact_text.endswith("```"):
            artifact_text = artifact_text.split("\n", 1)[-1].rsplit("\n```", 1)[0]
        if not artifact_text:
            raise HTTPException(status_code=502, detail="JakeAI build runtime returned no usable fallback artifact")
        mission_text = " ".join([
            str(mission.get("signal") or ""),
            str(mission.get("outcome") or ""),
        ]).lower()
        is_web = any(term in mission_text for term in ("browser", "html", "web", "website", "site", "page"))
        package = {
            "title": "JakeAI Mission Prototype",
            "artifact_type": "prototype" if is_web else "document_bundle",
            "summary": "Compact bounded prototype generated for human review.",
            "files": [{
                "path": "prototype.html" if is_web else "prototype.md",
                "purpose": "Primary review artifact",
                "content": artifact_text[:12000],
            }],
            "test_plan": [
                "Review the artifact content manually.",
                "Confirm it stays within the mission boundaries before any execution or deployment.",
            ],
            "limitations": ["Fallback single-file build used because the structured build response was incomplete."],
            "approval_requirements": ["Human approval required before deployment, publication, outreach, purchase, or external action."],
            "next_step": "Review the draft artifact and its static validation results.",
        }

    files = package.get("files")
    if not isinstance(files, list) or not files or len(files) > 5:
        raise HTTPException(status_code=502, detail="JakeAI build runtime returned an invalid file manifest")

    cleaned_files = []
    total_chars = 0
    for item in files:
        if not isinstance(item, dict):
            raise HTTPException(status_code=502, detail="JakeAI build runtime returned an invalid file entry")
        path = str(item.get("path") or "").strip().replace("\\", "/")
        content = str(item.get("content") or "")
        purpose = _clean(item.get("purpose"), 600)
        if (
            not path
            or path.startswith(("/", "~"))
            or ".." in path.split("/")
            or path.lower().startswith((".env", "secrets/", "credentials/"))
        ):
            raise HTTPException(status_code=502, detail="JakeAI build runtime returned an unsafe file path")
        total_chars += len(content)
        if total_chars > 60000:
            raise HTTPException(status_code=502, detail="JakeAI build artifact exceeds the bounded size limit")
        cleaned_files.append({"path": path[:300], "purpose": purpose, "content": content[:20000]})

    package["files"] = cleaned_files
    package["title"] = _clean(package.get("title"), 300) or "JakeAI Mission Prototype"
    package["artifact_type"] = _clean(package.get("artifact_type"), 80) or "prototype"
    package["summary"] = _clean(package.get("summary"), 3000)
    package["test_plan"] = [str(x)[:800] for x in (package.get("test_plan") or [])[:12]]
    package["limitations"] = [str(x)[:800] for x in (package.get("limitations") or [])[:12]]
    package["approval_requirements"] = [str(x)[:800] for x in (package.get("approval_requirements") or [])[:12]]
    package["next_step"] = _clean(package.get("next_step"), 1500)

    return {
        "package": package,
        "model": str(data.get("model") or "unknown"),
        "response_id": str(data.get("response_id") or ""),
        "input_tokens": int(data.get("input_tokens") or 0),
        "output_tokens": int(data.get("output_tokens") or 0),
    }


def _persist_build_artifact(mission_id: str, package: dict) -> dict:
    artifact_id = "JAI-ART-" + uuid.uuid4().hex[:16].upper()
    now = _now_iso()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO mission_artifacts(
                artifact_id,mission_id,artifact_type,title,summary,manifest_json,validation_json,
                status,human_approved,deployed,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,NULL,'draft',0,0,?,?)
            """,
            (
                artifact_id,
                mission_id,
                _clean(package.get("artifact_type"), 80) or "prototype",
                _clean(package.get("title"), 300) or "JakeAI Mission Prototype",
                _clean(package.get("summary"), 3000),
                json.dumps(package, ensure_ascii=False)[:70000],
                now,
                now,
            ),
        )
        return {
            "artifact_id": artifact_id,
            "mission_id": mission_id,
            "artifact_type": _clean(package.get("artifact_type"), 80) or "prototype",
            "title": _clean(package.get("title"), 300) or "JakeAI Mission Prototype",
            "summary": _clean(package.get("summary"), 3000),
            "status": "draft",
            "human_approved": False,
            "deployed": False,
            "file_count": len(package.get("files") or []),
            "created": now,
        }
    finally:
        conn.close()


def _validate_latest_artifact(mission_id: str) -> dict:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM mission_artifacts WHERE mission_id=? ORDER BY created_at DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No build artifact found for mission")
        try:
            package = json.loads(row["manifest_json"] or "{}")
        except Exception:
            package = {}

        errors = []
        warnings = []
        files = package.get("files") if isinstance(package, dict) else None
        if not isinstance(files, list) or not files:
            errors.append("artifact_has_no_files")
            files = []

        total_chars = 0
        seen_paths = set()
        secret_markers = ("sk-", "api_key=", "private_key", "BEGIN PRIVATE KEY", "password=")
        destructive_markers = ("rm -rf /", "format c:", "del /s /q", "drop database")
        for item in files[:10]:
            if not isinstance(item, dict):
                errors.append("invalid_file_entry")
                continue
            path = str(item.get("path") or "").strip().replace("\\", "/")
            content = str(item.get("content") or "")
            total_chars += len(content)
            if not path or path.startswith(("/", "~")) or ".." in path.split("/"):
                errors.append("unsafe_file_path")
            if path in seen_paths:
                errors.append("duplicate_file_path")
            seen_paths.add(path)
            lowered = content.lower()
            if any(marker.lower() in lowered for marker in secret_markers):
                warnings.append("possible_secret_literal_requires_review")
            if any(marker.lower() in lowered for marker in destructive_markers):
                errors.append("destructive_command_detected")

        if total_chars > 60000:
            errors.append("artifact_exceeds_size_limit")

        validation = {
            "status": "pass" if not errors else "needs_human_review",
            "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)),
            "file_count": len(files),
            "total_chars": total_chars,
            "checks": [
                "manifest_present",
                "relative_paths_only",
                "duplicate_path_check",
                "bounded_size_check",
                "secret_literal_scan",
                "destructive_command_scan",
                "human_release_gate_preserved",
            ],
            "executed_code": False,
            "external_actions_executed": False,
        }
        now = _now_iso()
        conn.execute(
            "UPDATE mission_artifacts SET validation_json=?,status=?,updated_at=? WHERE artifact_id=?",
            (
                json.dumps(validation, ensure_ascii=False),
                "validated" if not errors else "review_required",
                now,
                row["artifact_id"],
            ),
        )
        return {
            "artifact_id": row["artifact_id"],
            "title": row["title"],
            "artifact_type": row["artifact_type"],
            "validation": validation,
            "human_approved": False,
            "deployed": False,
        }
    finally:
        conn.close()


def _call_investigation_runtime(mission: dict) -> dict:
    runtime_url = _direct_runtime_url()
    runtime_token = _direct_runtime_token()
    if not runtime_url or not runtime_token:
        raise HTTPException(status_code=503, detail="JakeAI investigation runtime is not configured")

    prompt = f"""You are the bounded JakeAI Mission Investigation worker.

Investigate the mission below using only the information in the mission and your general reasoning. Do not claim that you searched the web, contacted anyone, purchased anything, published anything, deployed anything, or changed an external system. Do not invent citations or sources. Distinguish facts supplied by the mission from assumptions and unknowns.

Return ONE JSON object only with this exact top-level schema:
{{
  "summary": "short investigation summary",
  "problem_definition": "precise problem statement",
  "known": ["facts actually supplied or logically certain"],
  "assumptions": ["assumptions, clearly labeled"],
  "unknowns": ["important unknowns"],
  "existing_capability_assessment": {{
    "candidate_ids": ["JakeAI capability IDs if relevant"],
    "reuse_likely": true,
    "reason": "why"
  }},
  "evidence_needed": ["what evidence should be gathered next"],
  "research_queries": ["bounded public research queries that would reduce uncertainty"],
  "risks": ["material risks or constraints"],
  "recommended_route": "building|needs_information|ready_for_review",
  "route_reason": "why this route is appropriate",
  "proposed_next_step": "bounded next step",
  "confidence": "low|medium|high"
}}

Routing rules:
- Use "needs_information" if the customer must clarify something essential before useful work can continue.
- Use "building" only when the mission is sufficiently defined AND a concrete build/prototype is the appropriate next bounded step. Do not use building merely because no existing JakeAI capability matches.
- Use "ready_for_review" when the investigation has reached a useful decision point for human review, including when outside evidence/search should be approved or evaluated.
- Human release gate is always ON. Outbound contact is always blocked.

Mission:
{json.dumps(mission, ensure_ascii=False)[:14000]}
"""
    payload = {"prompt": prompt, "workflow": "research"}
    request = urllib.request.Request(
        runtime_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-JakeAI-Internal-Token": runtime_token,
            "Content-Type": "application/json",
            "User-Agent": "JakeAI-Mission-Investigation/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=502, detail="JakeAI investigation runtime rejected the request") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="JakeAI investigation runtime is unavailable") from exc

    text_value = str(data.get("text") or "").strip()
    if not text_value:
        raise HTTPException(status_code=502, detail="JakeAI investigation runtime returned no usable output")
    try:
        report = _extract_json_object(text_value)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="JakeAI investigation runtime returned malformed output") from exc

    route = str(report.get("recommended_route") or "").strip()
    if route not in {"building", "needs_information", "ready_for_review"}:
        report["recommended_route"] = "ready_for_review"
        report["route_reason"] = "Runtime did not return an allowed route; human review required."

    search_results = []
    pages = []
    external_evidence_used = False
    queries = [str(q).strip() for q in (report.get("research_queries") or []) if str(q).strip()][:2]
    evidence_intent_text = " ".join([
        str(mission.get("signal") or ""),
        str(mission.get("outcome") or ""),
        str(mission.get("boundaries") or ""),
    ]).lower()
    evidence_requested = any(term in evidence_intent_text for term in (
        "research", "evidence", "source-backed", "sources", "public guidance",
        "current guidance", "documentation", "standards", "verify", "compare",
    ))
    if _tinyfish_key() and not queries and evidence_requested:
        fallback = _clean(mission.get("signal"), 450)
        if fallback:
            queries = [fallback]
    if _tinyfish_key() and queries and report.get("recommended_route") != "needs_information":
        purpose = "Gather public evidence for JakeAI mission " + _clean(mission.get("id"), 100)
        seen_urls = []
        for query in queries:
            hits = _tinyfish_search(query, purpose)
            search_results.extend(hits[:4])
            for hit in hits[:3]:
                url = hit.get("url")
                if url and url not in seen_urls:
                    seen_urls.append(url)
        pages = _tinyfish_fetch(seen_urls[:5], purpose)
        if search_results or pages:
            report = _synthesize_investigation_with_evidence(mission, report, search_results, pages)
            external_evidence_used = True

    return {
        "report": report,
        "model": str(data.get("model") or "unknown"),
        "response_id": str(data.get("response_id") or ""),
        "input_tokens": int(data.get("input_tokens") or 0),
        "output_tokens": int(data.get("output_tokens") or 0),
        "external_evidence_used": external_evidence_used,
        "evidence_adapter": "tinyfish-search-fetch" if _tinyfish_key() else "not_configured",
        "search_result_count": len(search_results),
        "fetched_page_count": len(pages),
    }


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
    result: Optional[dict] = None


class MissionInvestigationRequest(BaseModel):
    mission: dict


class MissionBuildRequest(BaseModel):
    mission: dict


class MissionBuildTestRequest(BaseModel):
    mission: dict

class ArtifactReviewRequest(BaseModel):
    artifact_id: str = Field(min_length=8, max_length=100)
    decision: str = Field(max_length=20)
    note: str = Field(default="", max_length=2000)


class CustomerMissionStatusRequest(BaseModel):
    mission_id: str = Field(min_length=8, max_length=100)
    access_token: str = Field(min_length=20, max_length=100)


class ArtifactReleaseRequest(BaseModel):
    artifact_id: str = Field(min_length=8, max_length=100)
    note: str = Field(default="", max_length=2000)


class OwnerLoginRequest(BaseModel):
    access_key: str = Field(min_length=8, max_length=500)


class OwnerEnrollRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class AgentObserverEvent(BaseModel):
    event_id: str = Field(min_length=8, max_length=120)
    path: str = Field(default="/", max_length=500)
    method: str = Field(default="GET", max_length=12)
    user_agent: str = Field(default="", max_length=1000)
    client_ip: str = Field(default="", max_length=100)
    referrer_host: str = Field(default="", max_length=240)
    response_status: int = Field(default=0, ge=0, le=599)
    machine_surface: bool = False


class TrafficEvent(BaseModel):
    event_id: str = Field(min_length=8, max_length=120)
    visitor_id: str = Field(min_length=8, max_length=200)
    session_id: str = Field(min_length=8, max_length=200)
    event_type: str = Field(default="page_view", max_length=40)
    path: str = Field(default="/", max_length=500)
    referrer_host: str = Field(default="", max_length=240)
    source: str = Field(default="direct", max_length=160)
    medium: str = Field(default="", max_length=120)
    campaign: str = Field(default="", max_length=180)
    device: str = Field(default="unknown", max_length=40)
    internal: bool = False



_AGENT_PREFIX_CACHE = {}


def _agent_machine_surface(path: str) -> bool:
    path = (path or "/").split("?", 1)[0]
    return path in {
        "/llms.txt",
        "/robots.txt",
        "/sitemap.xml",
        "/catalog.json",
        "/workflow-registry.json",
        "/.well-known/agent.json",
    } or path.startswith("/agent-catalog/")


def _classify_agent_user_agent(user_agent: str, machine_surface: bool = False) -> dict:
    ua = (user_agent or "").lower()
    signatures = [
        ("openai", "OAI-SearchBot", "search", "oai-searchbot"),
        ("openai", "GPTBot", "training-crawler", "gptbot"),
        ("openai", "ChatGPT-User", "user-fetch", "chatgpt-user"),
        ("openai", "OAI-AdsBot", "ads-validation", "oai-adsbot"),
        ("anthropic", "Claude-SearchBot", "search", "claude-searchbot"),
        ("anthropic", "Claude-User", "user-fetch", "claude-user"),
        ("anthropic", "ClaudeBot", "training-crawler", "claudebot"),
        ("perplexity", "Perplexity-User", "user-fetch", "perplexity-user"),
        ("perplexity", "PerplexityBot", "search", "perplexitybot"),
        ("google", "Googlebot", "search", "googlebot"),
        ("microsoft", "bingbot", "search", "bingbot"),
        ("apple", "Applebot", "search-ai", "applebot"),
        ("amazon", "Amazonbot", "search-ai", "amazonbot"),
        ("meta", "Meta-ExternalAgent", "ai-crawler", "meta-externalagent"),
        ("commoncrawl", "CCBot", "web-crawler", "ccbot"),
    ]
    for provider, agent, purpose, needle in signatures:
        if needle in ua:
            return {"provider": provider, "agent": agent, "purpose": purpose}
    if any(needle in ua for needle in ("bot", "crawler", "spider", "slurp", "headless")):
        return {"provider": "other", "agent": "UnidentifiedBot", "purpose": "crawler"}
    if machine_surface:
        return {"provider": "unknown", "agent": "MachineClient", "purpose": "machine-discovery"}
    return {"provider": "unknown", "agent": "UnknownClient", "purpose": "unknown"}


def _published_prefixes(url: str) -> list:
    now = int(time.time())
    cached = _AGENT_PREFIX_CACHE.get(url)
    if cached and now - int(cached.get("at", 0)) < 21600:
        return cached.get("prefixes", [])
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JakeAI-Agent-Observer/1.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        prefixes = []
        for item in data.get("prefixes") or []:
            value = item.get("ipv4Prefix") or item.get("ipv6Prefix") or item.get("prefix")
            if value:
                prefixes.append(str(value))
        _AGENT_PREFIX_CACHE[url] = {"at": now, "prefixes": prefixes}
        return prefixes
    except Exception:
        return cached.get("prefixes", []) if cached else []


def _ip_in_prefixes(client_ip: str, prefixes: list) -> bool:
    try:
        ip = ipaddress.ip_address((client_ip or "").split(",", 1)[0].strip())
    except Exception:
        return False
    for prefix in prefixes:
        try:
            if ip in ipaddress.ip_network(prefix, strict=False):
                return True
        except Exception:
            continue
    return False


def _verify_agent(provider: str, agent: str, client_ip: str) -> str:
    source = None
    if provider == "openai":
        source = {
            "OAI-SearchBot": "https://openai.com/searchbot.json",
            "GPTBot": "https://openai.com/gptbot.json",
            "OAI-AdsBot": "https://openai.com/adsbot.json",
        }.get(agent)
    elif provider == "perplexity":
        source = {
            "PerplexityBot": "https://www.perplexity.com/perplexitybot.json",
            "Perplexity-User": "https://www.perplexity.com/perplexity-user.json",
        }.get(agent)
    if source:
        prefixes = _published_prefixes(source)
        if prefixes and _ip_in_prefixes(client_ip, prefixes):
            return "verified-ip"
        return "claimed-ua"
    if provider in {"anthropic", "google", "microsoft", "apple", "amazon", "meta", "commoncrawl"}:
        return "claimed-ua"
    return "machine-surface" if agent == "MachineClient" else "generic-bot"


def _require_agent_observer(value: Optional[str]) -> None:
    expected = os.environ.get("AGENT_OBSERVER_TOKEN", "").strip()
    candidate = (value or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Agent observer authorization is not configured")
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def register_mission_dispatcher_routes(app) -> None:
    _init_db()

    @app.post("/v1/mission-control/enroll")
    @app.post("/api/v1/mission-control/enroll")
    def mission_control_enroll(req: OwnerEnrollRequest):
        expected_hash = os.environ.get("MISSION_CONTROL_ENROLL_HASH", "").strip().lower()
        expires_raw = os.environ.get("MISSION_CONTROL_ENROLL_EXPIRES", "").strip()
        try:
            expires = int(expires_raw)
        except Exception:
            expires = 0
        if not expected_hash or not expires:
            raise HTTPException(status_code=503, detail="Owner device enrollment is not configured")
        if int(time.time()) > expires:
            raise HTTPException(status_code=410, detail="Owner activation link has expired")
        candidate_hash = hashlib.sha256(req.token.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(candidate_hash, expected_hash):
            raise HTTPException(status_code=401, detail="Owner activation link rejected")
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            used = conn.execute(
                "SELECT used_at FROM owner_enrollment_uses WHERE token_hash=?",
                (candidate_hash,),
            ).fetchone()
            if used:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=409, detail="Owner activation link has already been used")
            conn.execute(
                "INSERT INTO owner_enrollment_uses(token_hash,used_at) VALUES(?,?)",
                (candidate_hash, _now_iso()),
            )
            conn.execute("COMMIT")
        except HTTPException:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()
        response = JSONResponse({"ok": True, "authenticated": True, "remembered_days": MISSION_CONTROL_SESSION_DAYS})
        response.set_cookie(
            key=MISSION_CONTROL_COOKIE,
            value=_issue_owner_session(),
            max_age=MISSION_CONTROL_SESSION_DAYS * 86400,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.post("/v1/mission-control/login")
    @app.post("/api/v1/mission-control/login")
    def mission_control_login(req: OwnerLoginRequest):
        expected = os.environ.get("MISSION_CONTROL_TOKEN", "").strip()
        candidate = _clean(req.access_key, 500)
        if not expected:
            raise HTTPException(status_code=503, detail="Mission Control authorization is not configured")
        if not candidate or not hmac.compare_digest(candidate, expected):
            raise HTTPException(status_code=401, detail="Owner access key rejected")
        response = JSONResponse({"ok": True, "authenticated": True, "remembered_days": MISSION_CONTROL_SESSION_DAYS})
        response.set_cookie(
            key=MISSION_CONTROL_COOKIE,
            value=_issue_owner_session(),
            max_age=MISSION_CONTROL_SESSION_DAYS * 86400,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.post("/v1/mission-control/logout")
    @app.post("/api/v1/mission-control/logout")
    def mission_control_logout():
        response = JSONResponse({"ok": True, "authenticated": False})
        response.delete_cookie(
            key=MISSION_CONTROL_COOKIE,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.post("/v1/agent-observer/event")
    @app.post("/api/v1/agent-observer/event")
    def agent_observer_event(
        req: AgentObserverEvent,
        x_agent_observer_token: Optional[str] = Header(None, alias="X-JakeAI-Agent-Observer"),
    ):
        _require_agent_observer(x_agent_observer_token)
        path = _clean(req.path, 500).split("?", 1)[0] or "/"
        if not path.startswith("/"):
            path = "/" + path
        machine_surface = bool(req.machine_surface or _agent_machine_surface(path))
        classification = _classify_agent_user_agent(req.user_agent, machine_surface)
        if classification["agent"] == "UnknownClient":
            return {"ok": True, "accepted": False}
        verification = _verify_agent(
            classification["provider"],
            classification["agent"],
            _clean(req.client_ip, 100),
        )
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO agent_events(
                    event_id,provider,agent,purpose,verification,path,method,
                    response_status,referrer_host,machine_surface,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    _clean(req.event_id, 120),
                    classification["provider"],
                    classification["agent"],
                    classification["purpose"],
                    verification,
                    path,
                    _clean(req.method, 12).upper() or "GET",
                    int(req.response_status or 0),
                    _clean(req.referrer_host, 240).lower(),
                    1 if machine_surface else 0,
                    _now_iso(),
                ),
            )
            return {
                "ok": True,
                "accepted": True,
                "provider": classification["provider"],
                "agent": classification["agent"],
                "verification": verification,
            }
        finally:
            conn.close()

    @app.post("/v1/traffic/event")
    @app.post("/api/v1/traffic/event")
    def traffic_event(req: TrafficEvent):
        allowed = {"page_view", "commission_view", "cta", "product_view", "checkout_start", "mission_submit"}
        event_type = req.event_type if req.event_type in allowed else "page_view"
        path = _clean(req.path, 500).split("?", 1)[0] or "/"
        if not path.startswith("/"):
            path = "/" + path
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO traffic_events(
                    event_id,visitor_hash,session_hash,event_type,path,referrer_host,
                    source,medium,campaign,device,is_internal,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    _clean(req.event_id, 120),
                    _hash("traffic-visitor:" + req.visitor_id),
                    _hash("traffic-session:" + req.session_id),
                    event_type,
                    path,
                    _clean(req.referrer_host, 240).lower(),
                    _clean(req.source, 160).lower() or "direct",
                    _clean(req.medium, 120).lower(),
                    _clean(req.campaign, 180),
                    _clean(req.device, 40).lower() or "unknown",
                    1 if (req.internal or _clean(req.source, 160).lower() == "jakeai-qa") else 0,
                    _now_iso(),
                ),
            )
            return {"ok": True, "accepted": True}
        finally:
            conn.close()

    @app.get("/v1/traffic/health")
    @app.get("/api/v1/traffic/health")
    def traffic_health():
        conn = _connect()
        try:
            total = conn.execute("SELECT COUNT(*) AS n FROM traffic_events").fetchone()["n"]
            internal = conn.execute("SELECT COUNT(*) AS n FROM traffic_events WHERE is_internal=1").fetchone()["n"]
            ext = conn.execute(
                """
                SELECT
                  SUM(CASE WHEN event_type='page_view' THEN 1 ELSE 0 END) AS pageviews,
                  COUNT(DISTINCT CASE WHEN event_type='page_view' THEN visitor_hash END) AS visitors,
                  COUNT(DISTINCT CASE WHEN event_type='page_view' THEN session_hash END) AS sessions,
                  SUM(CASE WHEN event_type='commission_view' THEN 1 ELSE 0 END) AS commission_views,
                  SUM(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END) AS product_views,
                  SUM(CASE WHEN event_type='checkout_start' THEN 1 ELSE 0 END) AS checkout_starts,
                  SUM(CASE WHEN event_type='mission_submit' THEN 1 ELSE 0 END) AS mission_submits
                FROM traffic_events WHERE is_internal=0 AND created_at>=?
                """,
                (TRAFFIC_QUALITY_START,),
            ).fetchone()
            first = conn.execute("SELECT MIN(created_at) AS at FROM traffic_events").fetchone()["at"]
            agent_total = conn.execute("SELECT COUNT(*) AS n FROM agent_events").fetchone()["n"]
            agent_verified = conn.execute("SELECT COUNT(*) AS n FROM agent_events WHERE verification='verified-ip'").fetchone()["n"]
            agent_machine = conn.execute("SELECT COUNT(*) AS n FROM agent_events WHERE machine_surface=1").fetchone()["n"]
            return {
                "status": "ready",
                "tracker": "first-party-privacy-minimized-v1",
                "total_events": int(total or 0),
                "internal_events": int(internal or 0),
                "external_events": int((total or 0) - (internal or 0)),
                "external_pageviews": int(ext["pageviews"] or 0),
                "external_visitors": int(ext["visitors"] or 0),
                "external_sessions": int(ext["sessions"] or 0),
                "external_commission_views": int(ext["commission_views"] or 0),
                "external_product_views": int(ext["product_views"] or 0),
                "external_checkout_starts": int(ext["checkout_starts"] or 0),
                "external_mission_submits": int(ext["mission_submits"] or 0),
                "agent_observer_events": int(agent_total or 0),
                "agent_observer_verified": int(agent_verified or 0),
                "agent_observer_machine_reads": int(agent_machine or 0),
                "started_at": first,
                "quality_measurement_started_at": TRAFFIC_QUALITY_START,
            }
        finally:
            conn.close()

    @app.get("/v1/traffic/summary")
    @app.get("/api/v1/traffic/summary")
    def traffic_summary(
        request: Request,
        days: int = 7,
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ):
        _require_control(authorization, request)
        days = max(1, min(90, int(days or 7)))
        now = datetime.now(timezone.utc)
        cut24 = (now - timedelta(hours=24)).isoformat()
        cut7 = (now - timedelta(days=7)).isoformat()
        cut30 = (now - timedelta(days=30)).isoformat()
        cut_window = (now - timedelta(days=days)).isoformat()
        cut5m = (now - timedelta(minutes=5)).isoformat()
        def quality_cut(cutoff: str) -> str:
            return max(cutoff, TRAFFIC_QUALITY_START)
        conn = _connect()
        try:
            def snapshot(cutoff: str) -> dict:
                row = conn.execute(
                    """
                    SELECT
                      SUM(CASE WHEN event_type='page_view' THEN 1 ELSE 0 END) AS pageviews,
                      COUNT(DISTINCT CASE WHEN event_type='page_view' THEN visitor_hash END) AS visitors,
                      COUNT(DISTINCT CASE WHEN event_type='page_view' THEN session_hash END) AS sessions,
                      SUM(CASE WHEN event_type='commission_view' THEN 1 ELSE 0 END) AS commission_views,
                      SUM(CASE WHEN event_type='product_view' THEN 1 ELSE 0 END) AS product_views,
                      SUM(CASE WHEN event_type='checkout_start' THEN 1 ELSE 0 END) AS checkout_starts,
                      SUM(CASE WHEN event_type='mission_submit' THEN 1 ELSE 0 END) AS mission_submits
                    FROM traffic_events
                    WHERE is_internal=0 AND created_at>=?
                    """,
                    (quality_cut(cutoff),),
                ).fetchone()
                commission = int(row["commission_views"] or 0)
                product_views = int(row["product_views"] or 0)
                checkout_starts = int(row["checkout_starts"] or 0)
                missions = int(row["mission_submits"] or 0)
                return {
                    "pageviews": int(row["pageviews"] or 0),
                    "visitors": int(row["visitors"] or 0),
                    "sessions": int(row["sessions"] or 0),
                    "commission_views": commission,
                    "product_views": product_views,
                    "checkout_starts": checkout_starts,
                    "mission_submits": missions,
                    "product_to_checkout_rate": round((checkout_starts / product_views) * 100, 1) if product_views else 0.0,
                    "commission_to_mission_rate": round((missions / commission) * 100, 1) if commission else 0.0,
                }

            active = conn.execute(
                "SELECT COUNT(DISTINCT session_hash) AS n FROM traffic_events WHERE is_internal=0 AND created_at>=?",
                (quality_cut(cut5m),),
            ).fetchone()["n"]

            top_pages = [
                {"path": row["path"], "views": row["n"]}
                for row in conn.execute(
                    """
                    SELECT path,COUNT(*) AS n FROM traffic_events
                    WHERE is_internal=0 AND event_type='page_view' AND created_at>=?
                    GROUP BY path ORDER BY n DESC,path ASC LIMIT 12
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            top_products = [
                {"path": row["path"], "views": row["n"]}
                for row in conn.execute(
                    """
                    SELECT path,COUNT(*) AS n FROM traffic_events
                    WHERE is_internal=0 AND event_type='product_view' AND created_at>=?
                    GROUP BY path ORDER BY n DESC,path ASC LIMIT 12
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            sources = [
                {"source": row["source"] or "direct", "sessions": row["n"]}
                for row in conn.execute(
                    """
                    SELECT source,COUNT(DISTINCT session_hash) AS n FROM traffic_events
                    WHERE is_internal=0 AND event_type='page_view' AND created_at>=?
                    GROUP BY source ORDER BY n DESC,source ASC LIMIT 12
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            agent_24h = conn.execute(
                "SELECT COUNT(*) AS n FROM agent_events WHERE created_at>=?",
                (cut24,),
            ).fetchone()["n"]
            agent_verified_24h = conn.execute(
                "SELECT COUNT(*) AS n FROM agent_events WHERE created_at>=? AND verification='verified-ip'",
                (cut24,),
            ).fetchone()["n"]
            agent_machine_24h = conn.execute(
                "SELECT COUNT(*) AS n FROM agent_events WHERE created_at>=? AND machine_surface=1",
                (cut24,),
            ).fetchone()["n"]
            agent_families = [
                {
                    "provider": row["provider"],
                    "agent": row["agent"],
                    "purpose": row["purpose"],
                    "verification": row["verification"],
                    "requests": int(row["n"] or 0),
                }
                for row in conn.execute(
                    """
                    SELECT provider,agent,purpose,verification,COUNT(*) AS n
                    FROM agent_events
                    WHERE created_at>=?
                    GROUP BY provider,agent,purpose,verification
                    ORDER BY n DESC,provider ASC,agent ASC
                    LIMIT 20
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            agent_surfaces = [
                {"path": row["path"], "requests": int(row["n"] or 0)}
                for row in conn.execute(
                    """
                    SELECT path,COUNT(*) AS n
                    FROM agent_events
                    WHERE created_at>=? AND machine_surface=1
                    GROUP BY path
                    ORDER BY n DESC,path ASC
                    LIMIT 20
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            agent_latest = [
                {
                    "at": row["created_at"],
                    "provider": row["provider"],
                    "agent": row["agent"],
                    "purpose": row["purpose"],
                    "verification": row["verification"],
                    "path": row["path"],
                    "status": int(row["response_status"] or 0),
                }
                for row in conn.execute(
                    """
                    SELECT created_at,provider,agent,purpose,verification,path,response_status
                    FROM agent_events
                    WHERE created_at>=?
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            referral_rows = conn.execute(
                """
                SELECT
                  COUNT(DISTINCT CASE WHEN source LIKE '%chatgpt%' OR referrer_host LIKE '%chatgpt%' THEN session_hash END) AS chatgpt,
                  COUNT(DISTINCT CASE WHEN source LIKE '%perplexity%' OR referrer_host LIKE '%perplexity%' THEN session_hash END) AS perplexity,
                  COUNT(DISTINCT CASE WHEN source LIKE '%claude%' OR referrer_host LIKE '%claude%' THEN session_hash END) AS claude
                FROM traffic_events
                WHERE is_internal=0 AND event_type='page_view' AND created_at>=?
                """,
                (quality_cut(cut_window),),
            ).fetchone()
            devices = [
                {"device": row["device"] or "unknown", "visitors": row["n"]}
                for row in conn.execute(
                    """
                    SELECT device,COUNT(DISTINCT visitor_hash) AS n FROM traffic_events
                    WHERE is_internal=0 AND event_type='page_view' AND created_at>=?
                    GROUP BY device ORDER BY n DESC,device ASC
                    """,
                    (quality_cut(cut_window),),
                ).fetchall()
            ]
            daily = [
                {
                    "date": row["day"],
                    "pageviews": int(row["pageviews"] or 0),
                    "visitors": int(row["visitors"] or 0),
                    "sessions": int(row["sessions"] or 0),
                    "missions": int(row["missions"] or 0),
                }
                for row in conn.execute(
                    """
                    SELECT substr(created_at,1,10) AS day,
                      SUM(CASE WHEN event_type='page_view' THEN 1 ELSE 0 END) AS pageviews,
                      COUNT(DISTINCT CASE WHEN event_type='page_view' THEN visitor_hash END) AS visitors,
                      COUNT(DISTINCT CASE WHEN event_type='page_view' THEN session_hash END) AS sessions,
                      SUM(CASE WHEN event_type='mission_submit' THEN 1 ELSE 0 END) AS missions
                    FROM traffic_events
                    WHERE is_internal=0 AND created_at>=?
                    GROUP BY day ORDER BY day ASC
                    """,
                    (quality_cut((now - timedelta(days=13)).isoformat()),),
                ).fetchall()
            ]
            first = conn.execute(
                "SELECT MIN(created_at) AS at FROM traffic_events WHERE is_internal=0 AND created_at>=?",
                (TRAFFIC_QUALITY_START,),
            ).fetchone()["at"]
            internal_views = conn.execute(
                "SELECT COUNT(*) AS n FROM traffic_events WHERE is_internal=1 AND event_type='page_view' AND created_at>=?",
                (quality_cut(cut_window),),
            ).fetchone()["n"]
            setup_events = conn.execute(
                "SELECT COUNT(*) AS n FROM traffic_events WHERE is_internal=0 AND created_at<?",
                (TRAFFIC_QUALITY_START,),
            ).fetchone()["n"]
            return {
                "service": "JakeAI Traffic Monitor",
                "measurement": "first-party privacy-minimized",
                "started_at": first,
                "window_days": days,
                "active_sessions_5m": int(active or 0),
                "periods": {"24h": snapshot(cut24), "7d": snapshot(cut7), "30d": snapshot(cut30)},
                "top_pages": top_pages,
                "top_products": top_products,
                "sources": sources,
                "agent_observatory": {
                    "requests_24h": int(agent_24h or 0),
                    "verified_requests_24h": int(agent_verified_24h or 0),
                    "machine_surface_reads_24h": int(agent_machine_24h or 0),
                    "families": agent_families,
                    "machine_surfaces": agent_surfaces,
                    "latest": agent_latest,
                    "referrals": {
                        "chatgpt": int(referral_rows["chatgpt"] or 0),
                        "perplexity": int(referral_rows["perplexity"] or 0),
                        "claude": int(referral_rows["claude"] or 0),
                    },
                    "verification_note": "verified-ip means the claimed crawler user-agent also matched a provider-published IP range; claimed-ua is not independently verified.",
                },
                "devices": devices,
                "daily": daily,
                "internal_pageviews_excluded": int(internal_views or 0),
                "setup_events_excluded": int(setup_events or 0),
                "quality_measurement_started_at": TRAFFIC_QUALITY_START,
                "privacy": {
                    "raw_ip_stored": False,
                    "raw_user_agent_stored": False,
                    "full_referrer_url_stored": False,
                    "visitor_identifier": "random first-party identifier stored only as a one-way hash server-side",
                },
            }
        finally:
            conn.close()

    @app.post("/v1/missions/intake")
    @app.post("/api/v1/missions/intake")
    def mission_intake(req: MissionIntake):
        if req.website.strip():
            return {"ok": True, "accepted": True}

        signal = _clean(req.signal)
        outcome = _clean(req.outcome)
        boundaries = _clean(req.boundaries)
        idem_hash = _hash(req.idempotency_key)
        customer_token = _customer_token(req.idempotency_key)
        customer_token_hash = _hash(customer_token)
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
                mission_out = _mission_dict(existing, include_private=False)
                if existing["customer_token_hash"] and hmac.compare_digest(existing["customer_token_hash"], customer_token_hash):
                    mission_out["customer_access_token"] = customer_token
                    mission_out["status_url"] = "/mission/#id=" + existing["id"] + "&key=" + customer_token
                return {"ok": True, "duplicate": True, "mission": mission_out}

            conn.execute(
                """
                INSERT INTO missions(
                    id,idempotency_hash,body_hash,signal,outcome,boundaries,category,completeness,
                    missing_json,priority,status,source,outbound_authorized,human_release_gate,
                    created_at,updated_at,customer_token_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?,?)
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
                    customer_token_hash,
                ),
            )
            _event(conn, mission_id, "received", None, initial_status, "commission-bay")
            row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            conn.execute("COMMIT")
            mission_out = _mission_dict(row, include_private=False)
            mission_out["customer_access_token"] = customer_token
            mission_out["status_url"] = "/mission/#id=" + mission_id + "&key=" + customer_token
            return {"ok": True, "duplicate": False, "mission": mission_out}
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

    @app.post("/v1/missions/customer-status")
    @app.post("/api/v1/missions/customer-status")
    def mission_customer_status(req: CustomerMissionStatusRequest):
        mission_id = _clean(req.mission_id, 100)
        token_hash = _hash(_clean(req.access_token, 100))
        conn = _connect()
        try:
            mission = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if not mission or not mission["customer_token_hash"] or not hmac.compare_digest(mission["customer_token_hash"], token_hash):
                raise HTTPException(status_code=404, detail="Mission not found")

            artifact = conn.execute(
                """
                SELECT * FROM mission_artifacts
                WHERE mission_id=? AND released_to_customer=1
                ORDER BY released_at DESC,created_at DESC LIMIT 1
                """,
                (mission_id,),
            ).fetchone()

            result = {
                "mission": {
                    "id": mission["id"],
                    "status": mission["status"],
                    "created": mission["created_at"],
                    "updated": mission["updated_at"],
                    "released": bool(artifact),
                },
                "message": "Your mission is being worked through the JakeAI pipeline." if not artifact else "A human-approved result has been released to your private mission portal.",
            }
            if artifact:
                try:
                    manifest = json.loads(artifact["manifest_json"] or "{}")
                except Exception:
                    manifest = {}
                result["artifact"] = {
                    "artifact_id": artifact["artifact_id"],
                    "title": artifact["title"],
                    "summary": artifact["summary"],
                    "artifact_type": artifact["artifact_type"],
                    "released_at": artifact["released_at"],
                    "files": manifest.get("files") or [],
                    "next_step": manifest.get("next_step") or "",
                    "limitations": manifest.get("limitations") or [],
                }
            return result
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
    def mission_control_list(request: Request, authorization: Optional[str] = Header(None, alias="Authorization")):
        _require_control(authorization, request)
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
                artifact_rows = conn.execute(
                    """
                    SELECT artifact_id,artifact_type,title,summary,status,human_approved,deployed,created_at,updated_at,validation_json,review_note,reviewed_at,released_to_customer,released_at
                    FROM mission_artifacts WHERE mission_id=? ORDER BY created_at DESC LIMIT 5
                    """,
                    (row["id"],),
                ).fetchall()
                artifacts = []
                for artifact_row in artifact_rows:
                    try:
                        validation = json.loads(artifact_row["validation_json"]) if artifact_row["validation_json"] else None
                    except Exception:
                        validation = None
                    artifacts.append({
                        "artifact_id": artifact_row["artifact_id"],
                        "artifact_type": artifact_row["artifact_type"],
                        "title": artifact_row["title"],
                        "summary": artifact_row["summary"],
                        "status": artifact_row["status"],
                        "human_approved": bool(artifact_row["human_approved"]),
                        "deployed": bool(artifact_row["deployed"]),
                        "created": artifact_row["created_at"],
                        "updated": artifact_row["updated_at"],
                        "validation": validation,
                        "review_note": artifact_row["review_note"],
                        "reviewed_at": artifact_row["reviewed_at"],
                        "released_to_customer": bool(artifact_row["released_to_customer"]),
                        "released_at": artifact_row["released_at"],
                    })
                item["artifacts"] = artifacts
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

    @app.get("/v1/mission-control/artifacts/{artifact_id}")
    @app.get("/api/v1/mission-control/artifacts/{artifact_id}")
    def mission_control_artifact(
        artifact_id: str,
        request: Request,
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ):
        _require_control(authorization, request)
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM mission_artifacts WHERE artifact_id=?",
                (_clean(artifact_id, 100),),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Artifact not found")
            try:
                manifest = json.loads(row["manifest_json"] or "{}")
            except Exception:
                manifest = {}
            try:
                validation = json.loads(row["validation_json"]) if row["validation_json"] else None
            except Exception:
                validation = None
            return {
                "artifact_id": row["artifact_id"],
                "mission_id": row["mission_id"],
                "artifact_type": row["artifact_type"],
                "title": row["title"],
                "summary": row["summary"],
                "status": row["status"],
                "human_approved": bool(row["human_approved"]),
                "deployed": bool(row["deployed"]),
                "manifest": manifest,
                "validation": validation,
                "created": row["created_at"],
                "updated": row["updated_at"],
                "review_note": row["review_note"] if "review_note" in row.keys() else None,
                "reviewed_at": row["reviewed_at"] if "reviewed_at" in row.keys() else None,
                "released_to_customer": bool(row["released_to_customer"]) if "released_to_customer" in row.keys() else False,
                "released_at": row["released_at"] if "released_at" in row.keys() else None,
                "controls": {
                    "human_release_gate": True,
                    "outbound_authorized": False,
                    "deployed": bool(row["deployed"]),
                },
            }
        finally:
            conn.close()

    @app.post("/v1/mission-control/artifacts/review")
    @app.post("/api/v1/mission-control/artifacts/review")
    def mission_control_artifact_review(
        req: ArtifactReviewRequest,
        request: Request,
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ):
        _require_control(authorization, request)
        decision = _clean(req.decision, 20).lower()
        note = _clean(req.note, 2000)
        if decision not in {"approve", "revise", "reject"}:
            raise HTTPException(status_code=400, detail="Invalid artifact review decision")
        if decision == "revise" and not note:
            raise HTTPException(status_code=400, detail="Revision instructions are required")

        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            artifact = conn.execute(
                "SELECT * FROM mission_artifacts WHERE artifact_id=?",
                (_clean(req.artifact_id, 100),),
            ).fetchone()
            if not artifact:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=404, detail="Artifact not found")

            mission = conn.execute("SELECT * FROM missions WHERE id=?", (artifact["mission_id"],)).fetchone()
            if not mission:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=404, detail="Mission not found")

            now = _now_iso()
            old_status = mission["status"]
            if decision == "approve":
                artifact_status = "approved"
                mission_status = "approved"
                approved = 1
                event_type = "human_approved"
                event_note = note or "Human approved the validated draft for a future controlled release. No external action executed."
            elif decision == "revise":
                artifact_status = "revision_requested"
                mission_status = "building"
                approved = 0
                event_type = "human_revision_requested"
                event_note = note
            else:
                artifact_status = "rejected"
                mission_status = "closed"
                approved = 0
                event_type = "human_rejected"
                event_note = note or "Human rejected the draft. Mission closed without external action."

            conn.execute(
                """
                UPDATE mission_artifacts
                SET status=?,human_approved=?,review_note=?,reviewed_at=?,updated_at=?,deployed=0,released_to_customer=0,released_at=NULL
                WHERE artifact_id=?
                """,
                (artifact_status, approved, note or None, now, now, artifact["artifact_id"]),
            )

            analysis = {}
            try:
                if mission["analysis_json"]:
                    loaded = json.loads(mission["analysis_json"])
                    if isinstance(loaded, dict):
                        analysis = loaded
            except Exception:
                analysis = {}
            analysis["human_review"] = {
                "decision": decision,
                "artifact_id": artifact["artifact_id"],
                "note": note,
                "at": now,
                "external_actions_executed": False,
            }

            conn.execute(
                """
                UPDATE missions
                SET status=?,analysis_json=?,updated_at=?,outbound_authorized=0,human_release_gate=1,
                    lease_owner=NULL,lease_token_hash=NULL,lease_expires_at=NULL
                WHERE id=?
                """,
                (mission_status, json.dumps(analysis, ensure_ascii=False)[:20000], now, mission["id"]),
            )
            _event(conn, mission["id"], event_type, old_status, mission_status, "human-mission-control", event_note)
            conn.execute("COMMIT")
            return {
                "ok": True,
                "decision": decision,
                "mission_id": mission["id"],
                "mission_status": mission_status,
                "artifact": {
                    "artifact_id": artifact["artifact_id"],
                    "status": artifact_status,
                    "human_approved": bool(approved),
                    "deployed": False,
                    "reviewed_at": now,
                },
                "controls": {
                    "human_release_gate": True,
                    "outbound_authorized": False,
                    "external_actions_executed": False,
                    "deployment_executed": False,
                },
            }
        except HTTPException:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    @app.post("/v1/mission-control/artifacts/release")
    @app.post("/api/v1/mission-control/artifacts/release")
    def mission_control_artifact_release(
        req: ArtifactReleaseRequest,
        request: Request,
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ):
        _require_control(authorization, request)
        artifact_id = _clean(req.artifact_id, 100)
        note = _clean(req.note, 2000)
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            artifact = conn.execute("SELECT * FROM mission_artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
            if not artifact:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=404, detail="Artifact not found")
            if not bool(artifact["human_approved"]):
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=409, detail="Artifact must be human-approved before release")
            if bool(artifact["released_to_customer"]):
                conn.execute("COMMIT")
                return {"ok": True, "already_released": True, "artifact_id": artifact_id}

            mission = conn.execute("SELECT * FROM missions WHERE id=?", (artifact["mission_id"],)).fetchone()
            if not mission:
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=404, detail="Mission not found")

            now = _now_iso()
            conn.execute(
                """
                UPDATE mission_artifacts
                SET status='released',released_to_customer=1,released_at=?,updated_at=?
                WHERE artifact_id=?
                """,
                (now, now, artifact_id),
            )
            conn.execute(
                """
                UPDATE missions SET status='closed',updated_at=?,outbound_authorized=0,human_release_gate=1
                WHERE id=?
                """,
                (now, mission["id"]),
            )
            _event(
                conn,
                mission["id"],
                "human_released_to_customer_portal",
                mission["status"],
                "closed",
                "human-mission-control",
                note or "Human released the approved artifact to the mission's private customer portal. No outbound message was sent.",
            )
            conn.execute("COMMIT")
            return {
                "ok": True,
                "artifact_id": artifact_id,
                "mission_id": mission["id"],
                "released_at": now,
                "channel": "private-customer-portal",
                "controls": {
                    "public_release": False,
                    "outbound_authorized": False,
                    "external_message_sent": False,
                    "deployment_executed": False,
                },
            }
        except HTTPException:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    @app.patch("/v1/mission-control")
    @app.patch("/api/v1/mission-control")
    def mission_control_update(req: MissionAdminUpdate, request: Request, authorization: Optional[str] = Header(None, alias="Authorization")):
        _require_control(authorization, request)
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

    @app.post("/v1/missions/build")
    @app.post("/api/v1/missions/build")
    def mission_build(
        req: MissionBuildRequest,
        x_jakeai_worker_token: Optional[str] = Header(None, alias="X-JakeAI-Worker-Token"),
    ):
        _require_worker(x_jakeai_worker_token)
        mission = req.mission if isinstance(req.mission, dict) else {}
        mission_id = _clean(mission.get("id"), 100)
        if not mission_id:
            raise HTTPException(status_code=400, detail="Mission ID is required")
        try:
            built = _call_build_runtime(mission)
            artifact = _persist_build_artifact(mission_id, built["package"])
        except HTTPException:
            raise
        except Exception as exc:
            print(f"Mission build failure {mission_id}: {type(exc).__name__}: {exc}", flush=True)
            raise HTTPException(status_code=500, detail=f"Mission build persistence failed: {type(exc).__name__}") from exc
        return {
            "ok": True,
            "mission_id": mission_id,
            "artifact": artifact,
            "build": {
                "title": built["package"]["title"],
                "artifact_type": built["package"]["artifact_type"],
                "summary": built["package"]["summary"],
                "file_count": len(built["package"].get("files") or []),
                "test_plan": built["package"].get("test_plan") or [],
                "limitations": built["package"].get("limitations") or [],
                "approval_requirements": built["package"].get("approval_requirements") or [],
                "next_step": built["package"].get("next_step") or "",
            },
            "runtime": {
                "model": built["model"],
                "response_id": built["response_id"],
                "input_tokens": built["input_tokens"],
                "output_tokens": built["output_tokens"],
            },
            "controls": {
                "human_release_gate": True,
                "outbound_authorized": False,
                "deployed": False,
                "external_actions_executed": False,
            },
        }

    @app.post("/v1/missions/test-build")
    @app.post("/api/v1/missions/test-build")
    def mission_test_build(
        req: MissionBuildTestRequest,
        x_jakeai_worker_token: Optional[str] = Header(None, alias="X-JakeAI-Worker-Token"),
    ):
        _require_worker(x_jakeai_worker_token)
        mission = req.mission if isinstance(req.mission, dict) else {}
        mission_id = _clean(mission.get("id"), 100)
        if not mission_id:
            raise HTTPException(status_code=400, detail="Mission ID is required")
        artifact = _validate_latest_artifact(mission_id)
        return {
            "ok": True,
            "mission_id": mission_id,
            "artifact": artifact,
            "controls": {
                "human_release_gate": True,
                "outbound_authorized": False,
                "deployed": False,
                "executed_code": False,
                "external_actions_executed": False,
            },
        }

    @app.post("/v1/missions/investigate")
    @app.post("/api/v1/missions/investigate")
    def mission_investigate(
        req: MissionInvestigationRequest,
        x_jakeai_worker_token: Optional[str] = Header(None, alias="X-JakeAI-Worker-Token"),
    ):
        _require_worker(x_jakeai_worker_token)
        mission = req.mission if isinstance(req.mission, dict) else {}
        mission_id = _clean(mission.get("id"), 100)
        if not mission_id:
            raise HTTPException(status_code=400, detail="Mission ID is required")
        result = _call_investigation_runtime(mission)
        return {
            "ok": True,
            "mission_id": mission_id,
            "investigation": result["report"],
            "runtime": {
                "model": result["model"],
                "response_id": result["response_id"],
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "external_evidence_used": result.get("external_evidence_used", False),
                "evidence_adapter": result.get("evidence_adapter", "not_configured"),
                "search_result_count": result.get("search_result_count", 0),
                "fetched_page_count": result.get("fetched_page_count", 0),
            },
            "controls": {
                "human_release_gate": True,
                "outbound_authorized": False,
                "external_actions_executed": False,
            },
        }

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
            existing_analysis = {}
            try:
                if row["analysis_json"]:
                    loaded = json.loads(row["analysis_json"])
                    if isinstance(loaded, dict):
                        existing_analysis = loaded
            except Exception:
                existing_analysis = {}
            merged_analysis = existing_analysis
            if req.result is not None:
                merged_analysis = {**existing_analysis, **req.result}

            conn.execute(
                """
                UPDATE missions
                SET status=?, lease_owner=NULL, lease_token_hash=NULL, lease_expires_at=NULL,
                    last_error=?, analysis_json=?, updated_at=?, outbound_authorized=0, human_release_gate=1
                WHERE id=?
                """,
                (
                    req.next_status,
                    _clean(req.error, 1200) or None,
                    json.dumps(merged_analysis, ensure_ascii=False)[:20000] if merged_analysis else None,
                    _now_iso(),
                    req.mission_id,
                ),
            )
            _event(conn, req.mission_id, "lease_released", old, req.next_status, req.worker_id, req.note or req.error)
            updated = conn.execute("SELECT * FROM missions WHERE id=?", (req.mission_id,)).fetchone()
            conn.execute("COMMIT")
            return {"ok": True, "mission": _mission_dict(updated)}
        finally:
            conn.close()

    @app.post("/v1/mission-control/dispatcher-self-test")
    @app.post("/api/v1/mission-control/dispatcher-self-test")
    def mission_dispatcher_self_test(request: Request, authorization: Optional[str] = Header(None, alias="Authorization")):
        _require_control(authorization, request)
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
            investigation_reports = 0
            evidence_backed_reports = 0
            for row in conn.execute("SELECT analysis_json FROM missions WHERE analysis_json IS NOT NULL").fetchall():
                try:
                    analysis = json.loads(row["analysis_json"] or "{}")
                    investigation = analysis.get("investigation") if isinstance(analysis, dict) else None
                    if isinstance(investigation, dict):
                        investigation_reports += 1
                        sources = investigation.get("sources_used") or []
                        runtime = analysis.get("investigation_runtime") or {}
                        if (
                            isinstance(sources, list)
                            and any(isinstance(s, dict) and s.get("url") for s in sources)
                        ) or (
                            isinstance(runtime, dict) and bool(runtime.get("external_evidence_used"))
                        ):
                            evidence_backed_reports += 1
                except Exception:
                    continue
            artifact_total = conn.execute("SELECT COUNT(*) AS n FROM mission_artifacts").fetchone()["n"]
            artifact_validated = conn.execute("SELECT COUNT(*) AS n FROM mission_artifacts WHERE status='validated'").fetchone()["n"]
            return {
                "status": "ready",
                "dispatcher": "transactional-sqlite-lease-v1",
                "database": "persistent-volume",
                "atomic_claim": True,
                "max_lease_seconds": 900,
                "human_release_gate": True,
                "outbound_default": "blocked",
                "investigation_runtime_configured": bool(_direct_runtime_url() and _direct_runtime_token()),
                "external_evidence_adapter": "tinyfish-search-fetch" if _tinyfish_key() else "not_configured",
                "investigation_reports": investigation_reports,
                "evidence_backed_reports": evidence_backed_reports,
                "artifacts_total": artifact_total,
                "validated_artifacts": artifact_validated,
            }
        finally:
            conn.close()


_init_db()
