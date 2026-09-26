"""JakeAI Book Factory structure mapper.

Maps navigation metadata onto immutable canonical source files. It NEVER rewrites,
normalizes, or emits a replacement book body. Structure is represented only as
byte offsets into the exact locked source.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from book_source_lock import list_locks

HEADING_PATTERNS = [
    ("chapter", re.compile(r"^(?:CHAPTER|Chapter)\s+(?:[IVXLCDM]+|\d+)(?:[.:-]?\s*.*)?$")),
    ("letter", re.compile(r"^(?:LETTER|Letter)\s+(?:[IVXLCDM]+|\d+)(?:[.:-]?\s*.*)?$")),
    ("part", re.compile(r"^(?:PART|Part)\s+(?:[IVXLCDM]+|\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)(?:[.:-]?\s*.*)?$")),
    ("roman", re.compile(r"^[IVXLCDM]{1,8}\.\s*(?:[A-Z][A-Z0-9 ,;:'’“”!?()\-—]*)?$")),
    ("epilogue", re.compile(r"^(?:EPILOGUE|Epilogue)\.?$")),
]
MIN_NARRATIVE_GAP = 700
MAX_HEADING_BYTES = 220
ALGORITHM_VERSION = "offset_map_v2_profiled"
EXPECTED_NAV = {
    "35": 17,     # 16 numbered sections + Epilogue
    "1661": 12,   # 12 Sherlock Holmes stories
    "345": 27,    # Dracula
    "120": 40,    # 6 Parts + 34 chapters
    "84": 28,     # 4 Letters + 24 chapters
    "11": 12,     # Alice
    "15": 136,    # 135 chapters + Epilogue
    "1342": 61,   # Pride and Prejudice
    "1260": 38,   # Jane Eyre
    "174": 20,    # Dorian Gray
}

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
    c.execute("""CREATE TABLE IF NOT EXISTS book_structures(
      job_id TEXT PRIMARY KEY,
      canonical_sha256 TEXT NOT NULL,
      segment_count INTEGER NOT NULL,
      navigation_count INTEGER NOT NULL,
      mapping_json TEXT NOT NULL,
      exact_reassembly_verified INTEGER NOT NULL,
      status TEXT NOT NULL,
      mapped_at TEXT NOT NULL
    )""")
    c.commit()
    return c

def _sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def _line_records(data:bytes):
    records=[]
    pos=0
    for raw in data.splitlines(keepends=True):
        end=pos+len(raw)
        records.append((pos,end,raw))
        pos=end
    if pos<len(data):
        records.append((pos,len(data),data[pos:]))
    return records

def _clean_line(raw:bytes):
    line=raw.rstrip(b"\r\n")
    if not line or len(line)>MAX_HEADING_BYTES:
        return None
    try:
        text=line.decode("utf-8",errors="strict").strip()
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    return text

def _record_candidate(records, idx, kind):
    start,end,raw=records[idx]
    text=_clean_line(raw)
    if not text:
        return None
    subtitle=None
    if idx+1<len(records):
        nxt=_clean_line(records[idx+1][2])
        if nxt and len(nxt)<=140:
            subtitle=nxt
    return {"offset":start,"line_end":end,"line":text,"kind":kind,"subtitle":subtitle}

def _candidate_headings(data:bytes, source_id:str):
    records=_line_records(data)
    out=[]
    for idx,(start,end,raw) in enumerate(records):
        text=_clean_line(raw)
        if text is None:
            continue
        sid=str(source_id)
        kind=None

        if sid=="35":
            if re.fullmatch(r"[IVXLCDM]{1,8}\.",text): kind="chapter"
            elif re.fullmatch(r"(?i:epilogue)\.?",text): kind="epilogue"
        elif sid=="1661":
            if re.fullmatch(r"[IVXLCDM]{1,8}\.\s+.+",text) and text==text.upper():
                kind="story"
        elif sid=="345":
            if re.fullmatch(r"CHAPTER\s+[IVXLCDM]+",text): kind="chapter"
        elif sid=="120":
            if re.fullmatch(r"PART\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX)(?:--.*)?",text): kind="part"
            elif re.fullmatch(r"[IVXLCDM]{1,8}",text): kind="chapter"
        elif sid=="84":
            if re.fullmatch(r"Letter\s+[1-4]",text): kind="letter"
            elif re.fullmatch(r"Chapter\s+\d+",text): kind="chapter"
        elif sid=="11":
            if re.fullmatch(r"CHAPTER\s+[IVXLCDM]+\.",text): kind="chapter"
        elif sid=="15":
            if re.fullmatch(r"CHAPTER\s+[IVXLCDM]+\.(?:\s+.*)?",text): kind="chapter"
            elif text=="EPILOGUE.": kind="epilogue"
        elif sid=="1342":
            if re.fullmatch(r"(?:CHAPTER|Chapter)\s+[IVXLCDM]+(?:\.\]?)?",text): kind="chapter"
        elif sid=="1260":
            if re.fullmatch(r"CHAPTER\s+[IVXLCDM]+(?:[—-].*)?",text): kind="chapter"
        elif sid=="174":
            if re.fullmatch(r"CHAPTER\s+[IVXLCDM]+\.",text): kind="chapter"
        else:
            for k,pat in HEADING_PATTERNS:
                if pat.fullmatch(text):
                    kind=k; break
        if kind:
            out.append(_record_candidate(records,idx,kind))
    return [x for x in out if x]

def _profiled_navigation(candidates:list[dict], total_bytes:int, source_id:str):
    sid=str(source_id)
    if not candidates:
        return []

    # Known duplicate-TOC profiles: select the real body reset.
    if sid=="35":
        starts=[i for i,x in enumerate(candidates) if x["line"]=="I."]
        return candidates[starts[-1]:] if starts else candidates
    if sid=="84":
        starts=[i for i,x in enumerate(candidates) if x["line"]=="Letter 1"]
        return candidates[starts[-1]:] if starts else candidates
    if sid=="174":
        starts=[i for i,x in enumerate(candidates) if x["line"]=="CHAPTER I."]
        return candidates[starts[-1]:] if starts else candidates
    if sid=="15":
        starts=[i for i,x in enumerate(candidates) if x["line"]=="CHAPTER I."]
        return candidates[starts[-1]:] if starts else candidates
    if sid=="1661":
        # Profile already excludes title-case TOC and internal roman-number-only subheads.
        return candidates
    if sid=="120":
        # Profile excludes dotted TOC entries; first body marker is PART ONE--...
        starts=[i for i,x in enumerate(candidates) if x["kind"]=="part" and x["line"].startswith("PART ONE--")]
        return candidates[starts[-1]:] if starts else candidates

    # For the other reference sources the profiled candidates are body headings.
    if sid in EXPECTED_NAV:
        return candidates

    # Generic fail-closed fallback for future candidates.
    start_index=0
    for i,x in enumerate(candidates):
        next_offset=candidates[i+1]["offset"] if i+1<len(candidates) else total_bytes
        if next_offset-x["offset"] >= MIN_NARRATIVE_GAP:
            start_index=i
            if i>0 and candidates[i-1]["kind"]=="part" and x["offset"]-candidates[i-1]["offset"]<500:
                start_index=i-1
            break
    return candidates[start_index:]

def map_exact_structure(lock:dict)->dict:
    path=Path(lock["source_file"])
    data=path.read_bytes()
    canonical=lock["canonical_sha256"]
    if _sha(data)!=canonical:
        raise ValueError("source file hash no longer matches immutable lock")
    source_id=str(lock.get("source_id") or "generic")
    candidates=_candidate_headings(data,source_id)
    nav=_profiled_navigation(candidates,len(data),source_id)
    expected=EXPECTED_NAV.get(source_id)
    # New production sources fail closed until an explicit expected navigation
    # profile is recorded and the detected count matches it exactly.
    semantic_count_verified=(expected is not None and len(nav)==expected)

    starts=[0]+sorted({int(x["offset"]) for x in nav if int(x["offset"])>0})
    if starts[-1]!=len(data):
        starts.append(len(data))
    segments=[]
    for i in range(len(starts)-1):
        a,b=starts[i],starts[i+1]
        segments.append({"index":i,"start":a,"end":b,"bytes":b-a,"kind":"front_matter" if i==0 else "section"})
    reconstructed=b"".join(data[s["start"]:s["end"]] for s in segments)
    exact=(reconstructed==data and _sha(reconstructed)==canonical)
    if not exact:
        raise ValueError("structure segmentation failed exact source reassembly")

    navigation=[]
    for n in nav:
        navigation.append({
          "offset":n["offset"],
          "line":n["line"],
          "kind":n["kind"],
          "subtitle":n["subtitle"]
        })
    return {
      "algorithm":ALGORITHM_VERSION,
      "canonical_sha256":canonical,
      "canonical_bytes":len(data),
      "candidate_heading_count":len(candidates),
      "navigation_count":len(navigation),
      "expected_navigation_count":expected,
      "semantic_count_verified":semantic_count_verified,
      "navigation":navigation,
      "segments":segments,
      "exact_reassembly_verified":True,
      "structure_verified":bool(exact and semantic_count_verified),
      "normalization":"none",
      "text_modified":False,
    }

def map_one(job_id:str,lock:dict):
    c=_conn()
    existing=c.execute("SELECT * FROM book_structures WHERE job_id=?",(job_id,)).fetchone()
    if existing and existing["canonical_sha256"]==lock["canonical_sha256"]:
        try:
            old=json.loads(existing["mapping_json"])
        except Exception:
            old={}
        if existing["status"]=="verified" and old.get("algorithm")==ALGORITHM_VERSION:
            out=dict(existing); c.close(); return out
    c.close()
    mapping=map_exact_structure(lock)
    c=_conn()
    c.execute("""INSERT OR REPLACE INTO book_structures
      (job_id,canonical_sha256,segment_count,navigation_count,mapping_json,
       exact_reassembly_verified,status,mapped_at)
      VALUES (?,?,?,?,?,?,?,?)""",(
        job_id,lock["canonical_sha256"],len(mapping["segments"]),mapping["navigation_count"],
        json.dumps(mapping,separators=(",",":")),1,
        "verified" if mapping.get("structure_verified") else "needs_review",_now()
    ))
    c.commit()
    row=c.execute("SELECT * FROM book_structures WHERE job_id=?",(job_id,)).fetchone()
    c.close()
    return dict(row)

def list_structures():
    c=_conn()
    rows=c.execute("SELECT * FROM book_structures ORDER BY mapped_at,job_id").fetchall()
    c.close()
    return {r["job_id"]:dict(r) for r in rows}

def public_structure(row:dict):
    mapping=json.loads(row["mapping_json"])
    return {
      "status":row["status"],
      "algorithm":mapping["algorithm"],
      "canonical_sha256":row["canonical_sha256"],
      "segment_count":row["segment_count"],
      "navigation_count":row["navigation_count"],
      "exact_reassembly_verified":bool(row["exact_reassembly_verified"]),
      "semantic_count_verified":bool(mapping.get("semantic_count_verified")),
      "expected_navigation_count":mapping.get("expected_navigation_count"),
      "text_modified":False,
      "normalization":"none",
      "navigation":mapping["navigation"],
      "mapped_at":row["mapped_at"],
    }

def run_mapper():
    # Locks may be generated concurrently on a fresh deploy, so retry briefly.
    for _ in range(8):
        locks=list_locks()
        for job_id,lock in locks.items():
            try:
                map_one(job_id,lock)
            except Exception as exc:
                print(f"[book-factory] structure mapping failed for {job_id}: {exc}",flush=True)
        time.sleep(2)

def start_structure_mapper():
    _conn().close()
    t=threading.Thread(target=run_mapper,daemon=True,name="book-factory-structure-mapper")
    t.start()
