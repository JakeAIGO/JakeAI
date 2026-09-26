"""JakeAI Book Factory narration manifest and audio QA plan.

No audio is generated here. This module converts immutable canonical source bytes
into an exact, contiguous sequence of TTS input chunks. Every chunk stores source byte offsets and a SHA-256. Joining the chunks MUST recreate the canonical source exactly before the JakeAI local Founder Narrator is allowed to run.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from book_source_lock import list_locks

MAX_CHARS_PER_CHUNK = 850
MODEL = "jakeai-local-founder-narrator-v1"
OUTPUT_FORMAT = "wav_pcm_master_plus_web_mp3"
APPLY_TEXT_NORMALIZATION = "none_exact_source"

FOUNDER_PLAN = {
    "voice_id": "local-private-founder-reference",
    "profile": "JakeAI Founder Narrator",
    "delivery": "Virginia/Southern conversational calm storyteller; normal pace; moderately expressive; title-specific direction only",
    "status": "approved_local_primary",
    "external_voice_platform": False,
    "reference_public": False,
}
VOICE_PLAN = {}

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
    c.execute("""CREATE TABLE IF NOT EXISTS book_narration_manifests(
      job_id TEXT PRIMARY KEY,
      canonical_sha256 TEXT NOT NULL,
      total_bytes INTEGER NOT NULL,
      total_chars INTEGER NOT NULL,
      chunk_count INTEGER NOT NULL,
      chunks_json TEXT NOT NULL,
      exact_reassembly_verified INTEGER NOT NULL,
      model TEXT NOT NULL,
      output_format TEXT NOT NULL,
      text_normalization TEXT NOT NULL,
      voice_plan_json TEXT NOT NULL,
      generation_status TEXT NOT NULL,
      qa_status TEXT NOT NULL,
      created_at TEXT NOT NULL
    )""")
    c.commit()
    return c

def _sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def _valid_utf8_prefix(data:bytes, max_chars:int)->int:
    """Return a byte boundary containing no more than max_chars Unicode chars."""
    text=data.decode("utf-8",errors="strict")
    if len(text)<=max_chars:
        return len(data)
    prefix=text[:max_chars]
    return len(prefix.encode("utf-8"))

def _choose_break(data:bytes, target:int)->int:
    """Prefer paragraph/newline/space boundaries without altering any bytes."""
    if target>=len(data):
        return len(data)
    window=data[:target]
    for marker in (b"\r\n\r\n",b"\n\n",b"\r\n",b"\n",b" "):
        pos=window.rfind(marker)
        if pos>target//2:
            return pos+len(marker)
    return target

def build_manifest(job_id:str)->dict:
    locks=list_locks()
    lock=locks.get(job_id)
    if not lock:
        raise ValueError("canonical source lock missing")
    source=Path(lock["source_file"]).read_bytes()
    if _sha(source)!=lock["canonical_sha256"]:
        raise ValueError("canonical source hash mismatch")
    source.decode("utf-8",errors="strict")

    chunks=[]
    start=0
    index=0
    while start<len(source):
        remaining=source[start:]
        target=_valid_utf8_prefix(remaining,MAX_CHARS_PER_CHUNK)
        target=_choose_break(remaining,target)
        if target<=0:
            raise ValueError("narration chunker made no progress")
        raw=remaining[:target]
        text=raw.decode("utf-8",errors="strict")
        chunks.append({
            "index":index,
            "start":start,
            "end":start+len(raw),
            "bytes":len(raw),
            "chars":len(text),
            "sha256":_sha(raw),
        })
        start+=len(raw)
        index+=1

    reconstructed=b"".join(source[c["start"]:c["end"]] for c in chunks)
    exact=(reconstructed==source and _sha(reconstructed)==lock["canonical_sha256"])
    if not exact:
        raise ValueError("narration manifest does not exactly reassemble canonical source")

    plan=dict(VOICE_PLAN.get(job_id,FOUNDER_PLAN))
    total_chars=len(source.decode("utf-8"))
    c=_conn()
    c.execute("""INSERT OR REPLACE INTO book_narration_manifests
      (job_id,canonical_sha256,total_bytes,total_chars,chunk_count,chunks_json,
       exact_reassembly_verified,model,output_format,text_normalization,voice_plan_json,
       generation_status,qa_status,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
        job_id,lock["canonical_sha256"],len(source),total_chars,len(chunks),json.dumps(chunks,separators=(",",":")),
        1,MODEL,OUTPUT_FORMAT,APPLY_TEXT_NORMALIZATION,json.dumps(plan,separators=(",",":")),
        "queued_local_founder_render","script_manifest_verified",_now()
    ))
    c.commit()
    row=c.execute("SELECT * FROM book_narration_manifests WHERE job_id=?",(job_id,)).fetchone()
    c.close()
    return dict(row)

def build_all(job_ids:list[str]):
    for job_id in job_ids:
        try:
            row=build_manifest(job_id)
            print(f"[book-factory] narration manifest ready for {job_id}: {row['chunk_count']} chunks, {row['total_chars']} chars, exact_reassembly=True",flush=True)
        except Exception as exc:
            print(f"[book-factory] narration manifest blocked for {job_id}: {exc}",flush=True)

def start_manifest_builder(job_ids:list[str]):
    _conn().close()
    threading.Thread(target=build_all,args=(job_ids,),daemon=True,name="book-factory-narration-manifest").start()

def get_manifest(job_id:str):
    c=_conn()
    row=c.execute("SELECT * FROM book_narration_manifests WHERE job_id=?",(job_id,)).fetchone()
    c.close()
    if not row:
        return None
    d=dict(row)
    d["chunks"]=json.loads(d.pop("chunks_json"))
    d["voice_plan"]=json.loads(d.pop("voice_plan_json"))
    d["exact_reassembly_verified"]=bool(d["exact_reassembly_verified"])
    return d

def public_manifest(row):
    if not row:
        return {"status":"pending"}
    return {
      "status":"ready",
      "canonical_sha256":row["canonical_sha256"],
      "total_bytes":row["total_bytes"],
      "total_chars":row["total_chars"],
      "chunk_count":row["chunk_count"],
      "exact_reassembly_verified":bool(row["exact_reassembly_verified"]),
      "model":row["model"],
      "output_format":row["output_format"],
      "text_normalization":row["text_normalization"],
      "voice_plan":row["voice_plan"],
      "generation_status":row["generation_status"],
      "qa_status":row["qa_status"],
      "rules":{
        "input":"Every TTS request must be the exact UTF-8 decode of its immutable byte range.",
        "normalization":"Provider text normalization must remain OFF.",
        "coverage":"Every canonical source byte belongs to exactly one narration chunk.",
        "rewrite":"Forbidden.",
        "render_gate":"Narration renders locally with the private founder voice reference; no third-party voice platform is part of the production path.",
        "audio_qa":"After generation: verify artifact exists, duration/nonzero audio, chunk order, chunk count, source hash linkage, and optional ASR spot-checks. ASR is advisory; exact TTS input bytes are authoritative."
      }
    }
