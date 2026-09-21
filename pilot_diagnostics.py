import base64
import os
import re
import secrets
import sqlite3
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from direct_billing import _db_path
from insurance_growth_desk import _require_session


class DiagnosticCreate(BaseModel):
    area: str = ""
    action: str = ""
    error_text: str = ""
    notes: str = ""
    page_url: str = ""
    user_agent: str = ""
    client_time: str = ""
    screenshot_data: str = ""


def _safe(value, limit=6000):
    return str(value or "").strip()[:limit]


def _redact_diagnostic_text(value, limit=6000):
    text = _safe(value, limit)
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*)([^\s,;]+(?:\s+[^\s,;]+)?)",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)((?:api[_ -]?key|token|secret|password|access[_ -]?code)\s*[:=]\s*)([^\s,;]+)",
        r"\1[REDACTED]",
        text,
    )
    return text


def _diagnostic_code():
    return "JAI-J-" + secrets.token_hex(3).upper()


def _classify_diagnostic(error_text, action=""):
    text = f"{error_text} {action}".lower()
    if re.search(r"401|403|unauthor|forbidden|sign.?in|session|login|access code", text):
        return (
            "ACCESS / SESSION",
            "Confirm the private pilot session is active and retry once. If it repeats, reference this JAI-J code to JakeAI.",
        )
    if re.search(r"consent|opt.?in|do not contact|contact approved", text):
        return (
            "CONSENT / LEAD STATE",
            "Keep the lead in its current state. Review the consent evidence before any contact approval; no outreach is triggered by this report.",
        )
    if re.search(r"timeout|network|failed to fetch|502|503|unavailable|offline|connection", text):
        return (
            "SERVICE / CONNECTIVITY",
            "Check connectivity and retry once. If it repeats, reference this JAI-J code so JakeAI can trace the service failure.",
        )
    if re.search(r"required|invalid|validation|400|missing|unknown", text):
        return (
            "INPUT / VALIDATION",
            "Review the field or selection named in the error and retry. Nothing external was sent or published.",
        )
    if re.search(r"campaign|model|generation|openai|ai|run failed|draft", text):
        return (
            "AI WORKFLOW",
            "The prior pilot data remains authoritative. Retry once; if it repeats, reference this JAI-J code for workflow repair.",
        )
    if re.search(r"database|sqlite|save|persist|record|storage|lead", text):
        return (
            "DATA / PERSISTENCE",
            "Avoid entering consequential data repeatedly until the stored state is checked. Reference this JAI-J code to JakeAI.",
        )
    return (
        "UNCLASSIFIED",
        "Keep this JAI-J code and the copied report. JakeAI can use the stored context to diagnose the failure.",
    )


def _diagnostics_dir():
    path = Path(_db_path()).resolve().parent / "pilot-diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _decode_screenshot(data):
    value = _safe(data, 2_100_000)
    if not value:
        return None
    match = re.fullmatch(
        r"data:(image/(png|jpeg|webp));base64,([A-Za-z0-9+/=]+)",
        value,
    )
    if not match:
        raise HTTPException(400, "Screenshot must be PNG, JPG, or WEBP")
    payload = match.group(3)
    if len(payload) > 2_000_000:
        raise HTTPException(413, "Screenshot is too large")
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise HTTPException(400, "Screenshot data is invalid") from exc
    if len(raw) > 1_500_000:
        raise HTTPException(413, "Screenshot is too large")
    ext = "jpg" if match.group(2) == "jpeg" else match.group(2)
    return raw, ext, match.group(1)


def _init_diagnostics_db():
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pilot_diagnostics(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            pilot TEXT NOT NULL,
            actor TEXT NOT NULL,
            area TEXT,
            action TEXT,
            error_text TEXT,
            notes TEXT,
            page_url TEXT,
            user_agent TEXT,
            client_time TEXT,
            classification TEXT NOT NULL,
            next_action TEXT NOT NULL,
            screenshot_path TEXT,
            screenshot_mime TEXT,
            status TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


def register_pilot_diagnostics_routes(app):
    _init_diagnostics_db()

    @app.get("/pilot-diagnostics.js", response_class=PlainTextResponse)
    def pilot_diagnostics_javascript():
        asset = Path(__file__).resolve().parent / "pilot-diagnostics.js"
        if not asset.exists():
            raise HTTPException(503, "Pilot diagnostics interface is unavailable")
        return PlainTextResponse(
            asset.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.post("/v1/insurance/diagnostics")
    @app.post("/api/v1/insurance/diagnostics")
    def create_insurance_diagnostic(body: DiagnosticCreate, request: Request):
        _require_session(request)
        action = _redact_diagnostic_text(body.action, 240) or "Manual problem report"
        error_text = _redact_diagnostic_text(body.error_text, 6000)
        notes = _redact_diagnostic_text(body.notes, 6000)
        if not error_text and not notes:
            raise HTTPException(400, "Error text or notes are required")

        classification, next_action = _classify_diagnostic(error_text, action)
        report_code = _diagnostic_code()
        screenshot_path = ""
        screenshot_mime = ""
        decoded = _decode_screenshot(body.screenshot_data)
        if decoded:
            raw, ext, screenshot_mime = decoded
            target = _diagnostics_dir() / f"{report_code}.{ext}"
            target.write_bytes(raw)
            screenshot_path = str(target)

        from insurance_growth_desk import _now

        conn = sqlite3.connect(_db_path(), timeout=10)
        conn.execute(
            """INSERT INTO pilot_diagnostics(
                report_code,created_at,pilot,actor,area,action,error_text,notes,
                page_url,user_agent,client_time,classification,next_action,
                screenshot_path,screenshot_mime,status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                report_code,
                _now(),
                "jim-insurance-growth-desk",
                "Jim",
                _redact_diagnostic_text(body.area, 160),
                action,
                error_text,
                notes,
                _redact_diagnostic_text(body.page_url, 1000),
                _redact_diagnostic_text(body.user_agent, 1000),
                _redact_diagnostic_text(body.client_time, 80),
                classification,
                next_action,
                screenshot_path,
                screenshot_mime,
                "open",
            ),
        )
        conn.commit()
        conn.close()
        return {
            "status": "stored",
            "report_code": report_code,
            "classification": classification,
            "next_action": next_action,
            "has_screenshot": bool(screenshot_path),
        }

    @app.get("/v1/insurance/diagnostics")
    @app.get("/api/v1/insurance/diagnostics")
    def list_insurance_diagnostics(request: Request):
        _require_session(request)
        conn = sqlite3.connect(_db_path(), timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT report_code,created_at,actor,area,action,error_text,notes,
                      classification,next_action,status,
                      CASE WHEN screenshot_path IS NOT NULL AND screenshot_path != '' THEN 1 ELSE 0 END AS has_screenshot
               FROM pilot_diagnostics
               WHERE pilot=?
               ORDER BY id DESC LIMIT 40""",
            ("jim-insurance-growth-desk",),
        ).fetchall()
        conn.close()
        return {"items": [dict(row) for row in rows]}

    @app.get("/v1/insurance/diagnostics/{report_code}/screenshot")
    @app.get("/api/v1/insurance/diagnostics/{report_code}/screenshot")
    def insurance_diagnostic_screenshot(report_code: str, request: Request):
        _require_session(request)
        code = _safe(report_code, 40)
        conn = sqlite3.connect(_db_path(), timeout=10)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT screenshot_path,screenshot_mime FROM pilot_diagnostics WHERE pilot=? AND report_code=?",
            ("jim-insurance-growth-desk", code),
        ).fetchone()
        conn.close()
        if not row or not row["screenshot_path"]:
            raise HTTPException(404, "Screenshot not found")
        path = Path(row["screenshot_path"]).resolve()
        root = _diagnostics_dir().resolve()
        if root not in path.parents or not path.exists():
            raise HTTPException(404, "Screenshot not found")
        return FileResponse(
            path,
            media_type=row["screenshot_mime"] or "application/octet-stream",
            headers={"Cache-Control": "no-store, max-age=0"},
        )
