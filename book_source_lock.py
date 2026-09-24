"""Autonomous exact-source acquisition for JakeAI Book Factory.

Fetches the approved Project Gutenberg UTF-8 artifact as raw bytes, removes only
the explicitly identified Project Gutenberg wrapper outside the book body, then
stores the untouched canonical body and its SHA-256 on persistent storage.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

START_RE = re.compile(br"(?m)^\*\*\* START OF THE PROJECT GUTENBERG EBOOK .*?\*\*\*[\r]?\n")
END_RE = re.compile(br"(?m)^\*\*\* END OF THE PROJECT GUTENBERG EBOOK .*?\*\*\*[\r]?\n?")
USER_AGENT = "JakeAI-Book-Factory/1.0 (+https://jakeaiofficial.com/book-factory/)"

def _now():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit=os.environ.get("BOOK_FACTORY_DATABASE_PATH","").strip()
    if explicit:
        return explicit
    return "/data/jakeai-book-factory.db" if os.path.isdir("/data") else "/tmp/jakeai-book-factory.db"

def _source_dir():
    p=Path(os.environ.get("BOOK_FACTORY_SOURCE_DIR","").strip() or ("/data/book-factory-sources" if os.path.isdir("/data") else "/tmp/book-factory-sources"))
    p.mkdir(parents=True,exist_ok=True)
    return p

def _conn():
    c=sqlite3.connect(_db_path(),timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS book_source_locks(
      job_id TEXT PRIMARY KEY,
      source_id TEXT NOT NULL,
      source_landing_url TEXT NOT NULL,
      source_artifact_url TEXT NOT NULL,
      resolved_artifact_url TEXT,
      canonical_sha256 TEXT NOT NULL,
      canonical_bytes INTEGER NOT NULL,
      encoding TEXT NOT NULL,
      comparison TEXT NOT NULL,
      normalization TEXT NOT NULL,
      start_marker_sha256 TEXT NOT NULL,
      end_marker_sha256 TEXT NOT NULL,
      etag TEXT,
      last_modified TEXT,
      source_file TEXT NOT NULL,
      fidelity_verified INTEGER NOT NULL DEFAULT 1,
      locked_at TEXT NOT NULL
    )""")
    c.commit()
    return c

def init_source_locks():
    c=_conn(); c.close()

def _artifact_url(source_id:str)->str:
    return f"https://www.gutenberg.org/ebooks/{source_id}.txt.utf-8"

def _extract_exact_body(raw:bytes):
    start=START_RE.search(raw)
    if not start:
        raise ValueError("Project Gutenberg START marker not found")
    end=END_RE.search(raw,start.end())
    if not end:
        raise ValueError("Project Gutenberg END marker not found")
    if end.start() <= start.end():
        raise ValueError("Invalid Gutenberg body boundaries")
    body=raw[start.end():end.start()]
    body.decode("utf-8",errors="strict")
    return body,start.group(0),end.group(0)

def lock_one(job:dict)->dict:
    if job.get("rights")!="green":
        raise ValueError("rights gate is not green")
    job_id=str(job["id"])
    source_id=str(job["source_id"])
    landing=str(job["source_url"])
    c=_conn()
    existing=c.execute("SELECT * FROM book_source_locks WHERE job_id=?",(job_id,)).fetchone()
    if existing:
        out=dict(existing); c.close(); return out
    c.close()

    req=urllib.request.Request(_artifact_url(source_id),headers={"User-Agent":USER_AGENT,"Accept":"text/plain"})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read()
        resolved=response.geturl()
        etag=response.headers.get("ETag")
        last_modified=response.headers.get("Last-Modified")
    body,start_marker,end_marker=_extract_exact_body(raw)
    digest=hashlib.sha256(body).hexdigest()
    dest=_source_dir()/(job_id+".txt")
    tmp=dest.with_suffix(".tmp")
    tmp.write_bytes(body)
    if hashlib.sha256(tmp.read_bytes()).hexdigest()!=digest:
        tmp.unlink(missing_ok=True)
        raise ValueError("persistent-write fidelity check failed")
    tmp.replace(dest)

    c=_conn()
    c.execute("""INSERT OR IGNORE INTO book_source_locks
      (job_id,source_id,source_landing_url,source_artifact_url,resolved_artifact_url,
       canonical_sha256,canonical_bytes,encoding,comparison,normalization,
       start_marker_sha256,end_marker_sha256,etag,last_modified,source_file,fidelity_verified,locked_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
        job_id,source_id,landing,_artifact_url(source_id),resolved,
        digest,len(body),"UTF-8","exact_bytes","none",
        hashlib.sha256(start_marker).hexdigest(),hashlib.sha256(end_marker).hexdigest(),
        etag,last_modified,str(dest),1,_now()
    ))
    c.commit()
    row=c.execute("SELECT * FROM book_source_locks WHERE job_id=?",(job_id,)).fetchone()
    c.close()
    return dict(row)

def list_locks()->dict:
    c=_conn()
    rows=c.execute("SELECT * FROM book_source_locks ORDER BY locked_at,job_id").fetchall()
    c.close()
    return {r["job_id"]:dict(r) for r in rows}

def public_lock_record(row:dict)->dict:
    return {
      "status":"locked",
      "source_id":row["source_id"],
      "source_landing_url":row["source_landing_url"],
      "source_artifact_url":row["source_artifact_url"],
      "resolved_artifact_url":row["resolved_artifact_url"],
      "canonical_sha256":row["canonical_sha256"],
      "canonical_bytes":row["canonical_bytes"],
      "encoding":row["encoding"],
      "comparison":row["comparison"],
      "normalization":row["normalization"],
      "etag":row["etag"],
      "last_modified":row["last_modified"],
      "fidelity_verified":bool(row["fidelity_verified"]),
      "locked_at":row["locked_at"],
      "wrapper_policy":"Only bytes outside the recorded Project Gutenberg START/END marker lines are excluded before lock."
    }

def run_autolock(queue_path:Path):
    if os.environ.get("BOOK_FACTORY_AUTO_LOCK_ENABLED","").strip().lower() not in {"1","true","yes","on"}:
        return
    try:
        queue=json.loads(queue_path.read_text(encoding="utf-8"))
        for job in queue.get("jobs",[]):
            if job.get("rights")=="green" and job.get("source_id"):
                try:
                    lock_one(job)
                    time.sleep(0.25)
                except Exception as exc:
                    print(f"[book-factory] source lock failed for {job.get('id')}: {exc}",flush=True)
    except Exception as exc:
        print(f"[book-factory] autolock initialization failed: {exc}",flush=True)

def start_autolock(queue_path:Path):
    init_source_locks()
    t=threading.Thread(target=run_autolock,args=(queue_path,),daemon=True,name="book-factory-autolock")
    t.start()
