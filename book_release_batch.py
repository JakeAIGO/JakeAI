from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from mission_dispatcher import _require_control
from book_source_lock import list_locks
from book_structure_map import list_structures
from book_edition_shell import list_shells
from book_epub_packager import get_build, public_build, start_epub_builder

router = APIRouter()

BOOK_META = {
    "JAE-TTM-001":{"title":"The Time Machine","author":"H. G. Wells"},
    "JAE-SH-001":{"title":"The Adventures of Sherlock Holmes","author":"Arthur Conan Doyle"},
    "JAE-DRAC-001":{"title":"Dracula","author":"Bram Stoker"},
    "JAE-TI-001":{"title":"Treasure Island","author":"Robert Louis Stevenson"},
    "JAE-FRANK-001":{"title":"Frankenstein; or, the Modern Prometheus","author":"Mary Wollstonecraft Shelley"},
    "JAE-ALICE-001":{"title":"Alice’s Adventures in Wonderland","author":"Lewis Carroll"},
    "JAE-MOBY-001":{"title":"Moby-Dick; or, The Whale","author":"Herman Melville"},
    "JAE-PRIDE-001":{"title":"Pride and Prejudice","author":"Jane Austen"},
    "JAE-JANE-001":{"title":"Jane Eyre","author":"Charlotte Brontë"},
    "JAE-DORIAN-001":{"title":"The Picture of Dorian Gray","author":"Oscar Wilde"},
}

VISUALS = {
    "JAE-TTM-001": {
        "family": "retro_future",
        "label": "Brass Chronosphere",
        "motif": "◷",
        "primary": "#07101a",
        "accent": "#e3b957",
        "glow": "#6eeaff",
        "design": "Deep navy field, brass chronometer rings, restrained cyan temporal glow, embossed JakeAI Autonomous Edition seal."
    },
    "JAE-SH-001": {
        "family": "gaslight_detective",
        "label": "Gaslight Lens",
        "motif": "⌕",
        "primary": "#090d12",
        "accent": "#c49b5c",
        "glow": "#d65f54",
        "design": "Victorian black field, gaslight amber typography, magnifying-lens geometry, subtle crimson case-file accent."
    },
    "JAE-DRAC-001": {
        "family": "gothic_nocturne",
        "label": "Crimson Cathedral",
        "motif": "✦",
        "primary": "#09070c",
        "accent": "#b89454",
        "glow": "#a8202f",
        "design": "Obsidian gothic field, cathedral-arch geometry, blood-crimson atmospheric glow, antique gold title treatment."
    },
    "JAE-TI-001": {
        "family": "maritime_adventure",
        "label": "Compass & Tide",
        "motif": "✣",
        "primary": "#071521",
        "accent": "#d6bd7c",
        "glow": "#50bdd0",
        "design": "Deep-ocean navy, compass-rose construction, parchment-gold type, cyan tide lines with restrained map-grid detail."
    },
    "JAE-FRANK-001": {
        "family": "gothic_science",
        "label": "Storm Laboratory",
        "motif": "ϟ",
        "primary": "#081016",
        "accent": "#c58b55",
        "glow": "#8be6ff",
        "design": "Storm-black laboratory field, copper scientific rings, electric-blue discharge motif, severe serif typography."
    },
    "JAE-ALICE-001": {
        "family": "whimsical_surreal",
        "label": "Rabbit-Hole Geometry",
        "motif": "◇",
        "primary": "#11132a",
        "accent": "#f0dba6",
        "glow": "#8bbcff",
        "design": "Midnight cobalt, concentric falling-frame illusion, ivory type, playful card-like geometry without borrowed illustrations."
    },
    "JAE-MOBY-001": {
        "family": "maritime_monumental",
        "label": "Abyssal Whale",
        "motif": "≈",
        "primary": "#061018",
        "accent": "#e5dfcf",
        "glow": "#4dabc0",
        "design": "Near-black sea field, monumental ivory typography, abstract whale-and-wave negative space, cold ocean glow."
    },
    "JAE-PRIDE-001": {
        "family": "regency_elegance",
        "label": "Regency Frame",
        "motif": "❦",
        "primary": "#111816",
        "accent": "#e8d6ac",
        "glow": "#91b89d",
        "design": "Deep sage-black field, Regency ornamental frame, warm ivory typography, quiet botanical geometry."
    },
    "JAE-JANE-001": {
        "family": "gothic_literary",
        "label": "Moor Window",
        "motif": "▱",
        "primary": "#0a1014",
        "accent": "#d7c4a4",
        "glow": "#bb7049",
        "design": "Charcoal moorland field, narrow-window geometry, ember glow, restrained literary serif treatment."
    },
    "JAE-DORIAN-001": {
        "family": "decadent_aesthetic",
        "label": "Fractured Portrait",
        "motif": "◈",
        "primary": "#0d0b11",
        "accent": "#d4b064",
        "glow": "#8f6fae",
        "design": "Obsidian-violet field, ornate portrait-frame geometry, fractured gold linework, elegant decadent typography."
    },
}

NARRATION = {
    "JAE-TTM-001": {"profile":"Classic British","target_wpm":150,"tone":"measured, intelligent, slightly mysterious","dialogue":"subtle character distinction; never theatrical parody"},
    "JAE-SH-001": {"profile":"Classic British Detective","target_wpm":158,"tone":"clear, observant, brisk","dialogue":"Watson/Holmes distinction through cadence and register only"},
    "JAE-DRAC-001": {"profile":"Gothic British Ensemble","target_wpm":146,"tone":"intimate journals, restrained dread","dialogue":"source-document voices distinguished without changing any words"},
    "JAE-TI-001": {"profile":"British Adventure","target_wpm":160,"tone":"energetic, seaworthy, lucid","dialogue":"light character differentiation; no caricature"},
    "JAE-FRANK-001": {"profile":"Literary British","target_wpm":145,"tone":"reflective, grave, emotionally controlled","dialogue":"speaker shifts marked by performance only"},
    "JAE-ALICE-001": {"profile":"Storybook British","target_wpm":160,"tone":"bright, precise, playful","dialogue":"character color through timing and pitch, never rewritten wording"},
    "JAE-MOBY-001": {"profile":"Literary American","target_wpm":145,"tone":"expansive, contemplative, maritime","dialogue":"clear speaker identity while preserving exact source"},
    "JAE-PRIDE-001": {"profile":"Regency British","target_wpm":158,"tone":"elegant, dry, socially observant","dialogue":"wit carried by timing, not editorial emphasis"},
    "JAE-JANE-001": {"profile":"Literary British Intimate","target_wpm":150,"tone":"first-person intimacy, strength, restraint","dialogue":"subtle distinctions; preserve narrator primacy"},
    "JAE-DORIAN-001": {"profile":"Literary British Aesthetic","target_wpm":150,"tone":"polished, controlled, faintly ominous","dialogue":"character distinction without celebrity imitation"},
}

class ReviewRequest(BaseModel):
    decision: str
    note: str = ""

def _now():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit=os.environ.get("BOOK_FACTORY_DATABASE_PATH","").strip()
    if explicit:
        return explicit
    return "/data/jakeai-book-factory.db" if os.path.isdir("/data") else "/tmp/jakeai-book-factory.db"

def _conn():
    c=sqlite3.connect(_db_path(),timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS book_release_candidate_reviews(
      job_id TEXT PRIMARY KEY,
      decision TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      reviewed_at TEXT NOT NULL
    )""")
    c.commit()
    return c

def _review_map():
    c=_conn()
    rows=c.execute("SELECT * FROM book_release_candidate_reviews").fetchall()
    c.close()
    return {r["job_id"]:dict(r) for r in rows}

def _qa(job_id, lock, structure, shell_row):
    checks=[]
    def add(name, passed, detail):
        checks.append({"name":name,"passed":bool(passed),"detail":detail})

    shell={}
    if shell_row:
        try:
            shell=json.loads(shell_row["shell_json"])
        except Exception:
            shell={}

    mapping={}
    if structure:
        try:
            mapping=json.loads(structure["mapping_json"])
        except Exception:
            mapping={}

    add("Immutable source lock", bool(lock and lock.get("fidelity_verified")), "Canonical source exists on persistent storage and passed its SHA-256 write/read check.")
    add("Exact-byte policy", bool(lock and lock.get("comparison")=="exact_bytes" and lock.get("normalization")=="none"), "No source normalization is allowed.")
    add("Structure reassembly", bool(mapping.get("exact_reassembly_verified")), "All mapped segments reassemble to the exact canonical source hash.")
    add("Semantic structure count", bool(mapping.get("semantic_count_verified")), "Known chapter/story count matches the title profile.")
    add("Structure/text hash match", bool(lock and structure and structure["canonical_sha256"]==lock["canonical_sha256"]), "Navigation offsets reference the same immutable text object.")
    add("Edition shell source policy", shell.get("source_text_policy")=="immutable_exact_source", "Reader and narration must use canonical offsets only.")
    add("No narration rewriting", bool(shell.get("narration",{}).get("rewriting_allowed") is False), "Performance direction may change delivery, never wording.")
    add("Original-art policy", bool(shell.get("visual",{}).get("original_art_required") and not shell.get("visual",{}).get("third_party_cover_art_allowed")), "No borrowed modern cover art enters the edition.")
    add("Celebrity imitation blocked", bool(shell.get("narration",{}).get("celebrity_imitation") is False), "Narrator profiles are original house direction.")
    add("Human release gate", bool(shell.get("provenance",{}).get("human_release_required")), "Owner approval remains mandatory.")
    add("Public release disabled", bool(shell.get("release",{}).get("public") is False and shell.get("commerce",{}).get("paid_release") is False), "This batch cannot publish or charge customers.")
    add("Visual plan present", job_id in VISUALS, "A title-specific original cover/reader family is assigned.")
    add("Narration plan present", job_id in NARRATION, "A title-specific performance plan exists.")

    return {
        "passed":all(x["passed"] for x in checks),
        "checks":checks,
        "check_count":len(checks),
        "failures":[x["name"] for x in checks if not x["passed"]],
    }

def _candidate(job_id, lock, structure, shell_row, review):
    shell=json.loads(shell_row["shell_json"]) if shell_row else {}
    visual=VISUALS.get(job_id)
    narration=NARRATION.get(job_id)
    qa=_qa(job_id,lock,structure,shell_row)
    provenance={
        "edition_mark":"JAKEAI AUTONOMOUS EDITION",
        "line":"Original Human Work · AI-Produced Edition · Rights-Verified · Human Release Pending",
        "final_release_label":"Original Human Work · AI-Produced Edition · Rights-Verified · Human-Approved",
        "human_approved":False,
        "original_author_credit_required":True,
        "source_sha256":lock["canonical_sha256"] if lock else None,
        "structure_sha256":shell_row["structure_sha256"] if shell_row else None,
    }
    return {
        "job_id":job_id,
        "title":BOOK_META.get(job_id,{}).get("title",job_id),
        "author":BOOK_META.get(job_id,{}).get("author",""),
        "visual":visual,
        "narration":{
            **(narration or {}),
            "script_source":"immutable canonical byte-offset segments",
            "rewrite_allowed":False,
            "celebrity_imitation":False,
            "pronunciation_policy":"Pronunciation metadata may guide performance but never replace, omit, add, or rewrite source words.",
        },
        "epub":public_build(get_build(job_id)),
        "reader":{
            "mode":"private release-candidate preview",
            "chapter_navigation":True,
            "bookmarks":True,
            "font_controls":True,
            "high_contrast":True,
            "read_listen_sync_target":True,
            "text_policy":"render immutable source slices without normalization",
        },
        "provenance":provenance,
        "qa":qa,
        "review":review or {"decision":"pending","note":"","reviewed_at":None},
        "release":{
            "state":"owner_review" if qa["passed"] else "blocked",
            "public":False,
            "paid":False,
            "can_publish_from_this_endpoint":False,
        },
    }

def _jobs():
    locks=list_locks()
    structures=list_structures()
    shells=list_shells()
    reviews=_review_map()
    ordered=[x for x in VISUALS.keys()]
    rows=[]
    for job_id in ordered:
        lock=locks.get(job_id)
        structure=structures.get(job_id)
        shell=shells.get(job_id)
        if not lock or not structure or not shell:
            continue
        rows.append(_candidate(job_id,lock,structure,shell,reviews.get(job_id)))
    return rows

@router.get("/api/v1/book-factory/private/release-batch")
@router.get("/v1/book-factory/private/release-batch")
def private_release_batch(request: Request, authorization: Optional[str]=Header(None)):
    _require_control(authorization,request)
    rows=_jobs()
    return {
        "batch_id":"JAE-BATCH-001",
        "title":"JakeAI Editions · First Autonomous Approval Batch",
        "status":"ready_for_owner_review" if rows and all(x["qa"]["passed"] for x in rows) else "blocked",
        "publication_enabled":False,
        "payment_enabled":False,
        "human_release_gate":True,
        "count":len(rows),
        "qa_passed":sum(1 for x in rows if x["qa"]["passed"]),
        "approved_internal":sum(1 for x in rows if x["review"]["decision"]=="approve_design"),
        "items":rows,
    }

@router.get("/api/v1/book-factory/private/release-batch/{job_id}/epub")
@router.get("/v1/book-factory/private/release-batch/{job_id}/epub")
def private_epub_status(job_id:str, request:Request, authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    if job_id not in BOOK_META:
        raise HTTPException(404,"Unknown release candidate")
    return public_build(get_build(job_id))

@router.get("/api/v1/book-factory/private/release-batch/{job_id}/epub/download")
@router.get("/v1/book-factory/private/release-batch/{job_id}/epub/download")
def private_epub_download(job_id:str, request:Request, authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    if job_id not in BOOK_META:
        raise HTTPException(404,"Unknown release candidate")
    row=get_build(job_id)
    if not row or row.get("status")!="ready" or not row.get("exact_roundtrip_verified"):
        raise HTTPException(409,"EPUB release candidate is not ready")
    path=Path(row["epub_path"])
    if not path.exists():
        raise HTTPException(409,"EPUB artifact is missing")
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=row["epub_sha256"]:
        raise HTTPException(409,"EPUB artifact hash mismatch")
    filename=job_id.lower()+".epub"
    return FileResponse(path=str(path),media_type="application/epub+zip",filename=filename)

@router.get("/api/v1/book-factory/private/release-batch/{job_id}/passport")
@router.get("/v1/book-factory/private/release-batch/{job_id}/passport")
def private_passport(job_id:str, request:Request, authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    locks=list_locks()
    structures=list_structures()
    shells=list_shells()
    reviews=_review_map()
    lock=locks.get(job_id)
    structure=structures.get(job_id)
    shell_row=shells.get(job_id)
    if not lock or not structure or not shell_row or job_id not in BOOK_META:
        raise HTTPException(404,"Edition passport not ready")
    mapping=json.loads(structure["mapping_json"])
    candidate=_candidate(job_id,lock,structure,shell_row,reviews.get(job_id))
    return {
        "passport_version":"1.0",
        "edition_id":job_id,
        "edition_mark":"JAKEAI AUTONOMOUS EDITION",
        "status":"PRE_RELEASE",
        "title":BOOK_META[job_id]["title"],
        "author":BOOK_META[job_id]["author"],
        "credit_statement":"The original literary work is credited to its human author. JakeAI claims production of this edition, not authorship of the underlying work.",
        "rights":{
            "territory":"United States",
            "source_landing_url":lock["source_landing_url"],
            "source_artifact_url":lock["source_artifact_url"],
            "source_id":lock["source_id"],
            "source_rights_statement":"Public domain in the USA",
            "scope":"Underlying source text only; supplemental modern art, introductions, annotations, translations, recordings, or other copyrighted material are not imported without separate clearance.",
        },
        "source_lock":{
            "canonical_sha256":lock["canonical_sha256"],
            "canonical_bytes":lock["canonical_bytes"],
            "encoding":lock["encoding"],
            "comparison":lock["comparison"],
            "normalization":lock["normalization"],
            "fidelity_verified":bool(lock["fidelity_verified"]),
            "locked_at":lock["locked_at"],
            "last_modified":lock["last_modified"],
        },
        "structure":{
            "algorithm":mapping.get("algorithm"),
            "navigation_count":mapping.get("navigation_count"),
            "expected_navigation_count":mapping.get("expected_navigation_count"),
            "semantic_count_verified":bool(mapping.get("semantic_count_verified")),
            "exact_reassembly_verified":bool(mapping.get("exact_reassembly_verified")),
            "text_modified":False,
        },
        "production":{
            "visual":candidate["visual"],
            "epub":candidate["epub"],
            "narration":candidate["narration"],
            "reader":candidate["reader"],
            "qa":candidate["qa"],
        },
        "approval":{
            "design_review":candidate["review"],
            "final_human_release_approved":False,
            "final_release_label_reserved":"Original Human Work · AI-Produced Edition · Rights-Verified · Human-Approved",
        },
        "release":{
            "public":False,
            "paid":False,
            "commerce_enabled":False,
            "can_publish_from_passport":False,
        },
    }

@router.get("/api/v1/book-factory/private/release-batch/{job_id}/toc")
@router.get("/v1/book-factory/private/release-batch/{job_id}/toc")
def private_toc(job_id:str, request:Request, authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    locks=list_locks()
    structures=list_structures()
    lock=locks.get(job_id)
    structure=structures.get(job_id)
    if not lock or not structure or job_id not in BOOK_META:
        raise HTTPException(404,"Release candidate not ready")
    mapping=json.loads(structure["mapping_json"])
    nav=mapping.get("navigation") or []
    return {
        "job_id":job_id,
        "title":BOOK_META[job_id]["title"],
        "author":BOOK_META[job_id]["author"],
        "canonical_sha256":lock["canonical_sha256"],
        "canonical_bytes":lock["canonical_bytes"],
        "section_count":len(nav),
        "sections":[
            {
                "index":i,
                "title":item.get("line") or f"Section {i+1}",
                "subtitle":item.get("subtitle"),
                "offset":item.get("offset"),
                "kind":item.get("kind"),
            }
            for i,item in enumerate(nav)
        ],
        "text_modified":False,
        "normalization":"none",
        "public":False,
        "paid":False,
    }

@router.get("/api/v1/book-factory/private/release-batch/{job_id}/section/{section_index}")
@router.get("/v1/book-factory/private/release-batch/{job_id}/section/{section_index}")
def private_section(job_id:str, section_index:int, request:Request, authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    locks=list_locks()
    structures=list_structures()
    lock=locks.get(job_id)
    structure=structures.get(job_id)
    if not lock or not structure:
        raise HTTPException(404,"Release candidate not ready")
    mapping=json.loads(structure["mapping_json"])
    segments=mapping.get("segments") or []
    target=section_index+1
    if section_index<0 or target>=len(segments):
        raise HTTPException(404,"Section not found")
    seg=segments[target]
    data=Path(lock["source_file"]).read_bytes()
    if hashlib.sha256(data).hexdigest()!=lock["canonical_sha256"]:
        raise HTTPException(409,"Canonical source hash mismatch")
    chunk=data[int(seg["start"]):int(seg["end"])]
    try:
        text_value=chunk.decode("utf-8",errors="strict")
    except UnicodeDecodeError:
        raise HTTPException(409,"Section boundary is not valid UTF-8")
    nav=(mapping.get("navigation") or [])
    title=(nav[section_index].get("line") if section_index<len(nav) else f"Section {section_index+1}")
    subtitle=(nav[section_index].get("subtitle") if section_index<len(nav) else None)
    return {
        "job_id":job_id,
        "section_index":section_index,
        "title":title,
        "subtitle":subtitle,
        "start":seg["start"],
        "end":seg["end"],
        "bytes":len(chunk),
        "canonical_sha256":lock["canonical_sha256"],
        "text":text_value,
        "text_modified":False,
        "normalization":"none",
    }

@router.post("/api/v1/book-factory/private/release-batch/{job_id}/review")
@router.post("/v1/book-factory/private/release-batch/{job_id}/review")
def review_candidate(job_id:str, body:ReviewRequest, request:Request, authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    if job_id not in VISUALS:
        raise HTTPException(404,"Unknown release candidate")
    decision=(body.decision or "").strip()
    if decision not in {"approve_design","revise","hold","pending"}:
        raise HTTPException(400,"Unsupported internal review decision")
    note=(body.note or "").strip()[:3000]
    now=_now()
    c=_conn()
    c.execute("""INSERT OR REPLACE INTO book_release_candidate_reviews(job_id,decision,note,reviewed_at)
      VALUES (?,?,?,?)""",(job_id,decision,note,now))
    c.commit(); c.close()
    return {
        "job_id":job_id,
        "decision":decision,
        "note":note,
        "reviewed_at":now,
        "publication_changed":False,
        "payment_changed":False,
        "message":"Internal design/narration review recorded. Public release remains separately gated.",
    }

def register_book_release_batch_routes(app):
    _conn().close()
    start_epub_builder(BOOK_META)
    app.include_router(router)
