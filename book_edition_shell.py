"""JakeAI Editions shell builder.

Builds non-public edition configuration around a locked, structure-verified book.
No canonical text is copied into shell records. Shells reference immutable source
and structure hashes only.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

from book_source_lock import list_locks
from book_structure_map import list_structures

SHELL_PROFILES = {
 "JAE-TTM-001":{"family":"retro_future","narrator":"classic_british","accent":"brass_cosmic","collection":"H. G. Wells"},
 "JAE-SH-001":{"family":"gaslight_detective","narrator":"classic_british","accent":"gaslight_crimson","collection":"Sherlock Holmes"},
 "JAE-DRAC-001":{"family":"gothic_nocturne","narrator":"gothic_british","accent":"midnight_crimson","collection":"Gothic Classics"},
 "JAE-TI-001":{"family":"maritime_adventure","narrator":"adventure_british","accent":"navy_parchment","collection":"Adventure Classics"},
 "JAE-FRANK-001":{"family":"gothic_science","narrator":"gothic_british","accent":"storm_copper","collection":"Gothic Classics"},
 "JAE-ALICE-001":{"family":"whimsical_surreal","narrator":"storybook_british","accent":"ivory_cobalt","collection":"Wonder Classics"},
 "JAE-MOBY-001":{"family":"maritime_monumental","narrator":"literary_american","accent":"deep_sea_ivory","collection":"American Classics"},
 "JAE-PRIDE-001":{"family":"regency_elegance","narrator":"classic_british","accent":"ivory_sage","collection":"Regency Classics"},
 "JAE-JANE-001":{"family":"gothic_literary","narrator":"literary_british","accent":"moor_ember","collection":"Gothic Classics"},
 "JAE-DORIAN-001":{"family":"decadent_aesthetic","narrator":"literary_british","accent":"obsidian_gold","collection":"Fin-de-siècle Classics"},
}

def _now():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit=os.environ.get("BOOK_FACTORY_DATABASE_PATH","").strip()
    if explicit:return explicit
    return "/data/jakeai-book-factory.db" if os.path.isdir("/data") else "/tmp/jakeai-book-factory.db"

def _conn():
    c=sqlite3.connect(_db_path(),timeout=20); c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS book_edition_shells(
      job_id TEXT PRIMARY KEY,
      canonical_sha256 TEXT NOT NULL,
      structure_sha256 TEXT NOT NULL,
      family TEXT NOT NULL,
      narrator_profile TEXT NOT NULL,
      shell_json TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )""")
    c.commit(); return c

def _structure_fingerprint(row):
    import hashlib
    payload=row["mapping_json"].encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def build_one(job_id,lock,structure):
    if structure["status"]!="verified":
        raise ValueError("structure is not verified")
    mapping=json.loads(structure["mapping_json"])
    if not mapping.get("exact_reassembly_verified") or not mapping.get("semantic_count_verified"):
        raise ValueError("structure QA not complete")
    if structure["canonical_sha256"]!=lock["canonical_sha256"]:
        raise ValueError("source/structure hash mismatch")
    profile=SHELL_PROFILES.get(job_id)
    if not profile:
        raise ValueError("no approved shell profile")
    structure_sha=_structure_fingerprint(structure)
    now=_now()
    shell={
      "version":"1.0",
      "job_id":job_id,
      "status":"pre_release_shell_ready",
      "canonical_sha256":lock["canonical_sha256"],
      "structure_sha256":structure_sha,
      "source_text_policy":"immutable_exact_source",
      "text_rendering":{"mode":"offset_slices","normalization":"none","rewrite_allowed":False},
      "reader":{"chapter_navigation":True,"bookmarks":True,"font_controls":True,"high_contrast":True,"read_listen_sync_target":True},
      "narration":{"profile":profile["narrator"],"script_source":"immutable_canonical_offsets","rewriting_allowed":False,"celebrity_imitation":False},
      "visual":{"family":profile["family"],"accent":profile["accent"],"original_art_required":True,"third_party_cover_art_allowed":False},
      "collection":profile["collection"],
      "provenance":{"edition_label":"JakeAI Autonomous Edition","original_human_work":True,"ai_produced_edition":True,"rights_verified":True,"human_release_required":True},
      "commerce":{"credits_eligible_target":True,"paid_release":False,"entitlement_required":True},
      "release":{"public":False,"human_approved":False}
    }
    c=_conn()
    c.execute("""INSERT OR REPLACE INTO book_edition_shells
      (job_id,canonical_sha256,structure_sha256,family,narrator_profile,shell_json,status,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?)""",(job_id,lock["canonical_sha256"],structure_sha,profile["family"],profile["narrator"],json.dumps(shell,separators=(",",":")),"ready",now,now))
    c.commit(); row=c.execute("SELECT * FROM book_edition_shells WHERE job_id=?",(job_id,)).fetchone(); c.close()
    return dict(row)

def list_shells():
    c=_conn(); rows=c.execute("SELECT * FROM book_edition_shells ORDER BY created_at,job_id").fetchall(); c.close()
    return {r["job_id"]:dict(r) for r in rows}

def public_shell(row):
    data=json.loads(row["shell_json"])
    return {
      "status":"ready",
      "family":row["family"],
      "narrator_profile":row["narrator_profile"],
      "canonical_sha256":row["canonical_sha256"],
      "structure_sha256":row["structure_sha256"],
      "source_text_policy":data["source_text_policy"],
      "human_release_required":True,
      "public":False,
    }

def run_builder():
    for _ in range(8):
        locks=list_locks(); structures=list_structures()
        for job_id,lock in locks.items():
            structure=structures.get(job_id)
            if not structure: continue
            try: build_one(job_id,lock,structure)
            except Exception as exc:
                print(f"[book-factory] edition shell blocked for {job_id}: {exc}",flush=True)
        time.sleep(2)

def start_shell_builder():
    _conn().close()
    threading.Thread(target=run_builder,daemon=True,name="book-factory-shell-builder").start()
