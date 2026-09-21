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
import urllib.error
import urllib.request
import urllib.parse
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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(missions)").fetchall()}
        if "analysis_json" not in columns:
            conn.execute("ALTER TABLE missions ADD COLUMN analysis_json TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_status_lease ON missions(status, lease_expires_at, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_lease_owner ON missions(lease_owner, lease_expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mission_events_mission ON mission_events(mission_id, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mission_artifacts_mission ON mission_artifacts(mission_id, created_at)")
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

    package = _extract_json_object(str(data.get("text") or ""))
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
                artifact_rows = conn.execute(
                    """
                    SELECT artifact_id,artifact_type,title,summary,status,human_approved,deployed,created_at,updated_at,validation_json
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
            }
        finally:
            conn.close()


_init_db()
