"""Private EPUB release-candidate packager for JakeAI Editions.

The canonical book body is never rewritten. XHTML is a reversible presentation
transform of exact UTF-8 source slices. Every slice is round-tripped back to the
original bytes before packaging, and the exact canonical source is included as a
non-spine asset for independent verification.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import sqlite3
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from book_source_lock import list_locks
from book_structure_map import list_structures

def _now():
    return datetime.now(timezone.utc).isoformat()

def _db_path():
    explicit=os.environ.get("BOOK_FACTORY_DATABASE_PATH","").strip()
    if explicit:
        return explicit
    return "/data/jakeai-book-factory.db" if os.path.isdir("/data") else "/tmp/jakeai-book-factory.db"

def _out_dir():
    p=Path(os.environ.get("BOOK_FACTORY_EPUB_DIR","").strip() or ("/data/book-factory-epubs" if os.path.isdir("/data") else "/tmp/book-factory-epubs"))
    p.mkdir(parents=True,exist_ok=True)
    return p

def _conn():
    c=sqlite3.connect(_db_path(),timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS book_epub_builds(
      job_id TEXT PRIMARY KEY,
      canonical_sha256 TEXT NOT NULL,
      epub_sha256 TEXT NOT NULL,
      epub_bytes INTEGER NOT NULL,
      epub_path TEXT NOT NULL,
      section_count INTEGER NOT NULL,
      exact_roundtrip_verified INTEGER NOT NULL,
      status TEXT NOT NULL,
      built_at TEXT NOT NULL
    )""")
    c.commit()
    return c

def _sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def _xhtml(title:str, body_text:bytes)->bytes:
    text=body_text.decode("utf-8",errors="strict")
    escaped=html.escape(text,quote=False)
    # Prove the reversible presentation transform before the XHTML exists.
    if html.unescape(escaped).encode("utf-8") != body_text:
        raise ValueError("XHTML escape roundtrip changed canonical bytes")
    safe_title=xml_escape(title or "Section")
    doc=(
      '<?xml version="1.0" encoding="utf-8"?>\n'
      '<!DOCTYPE html>\n'
      '<html xmlns="http://www.w3.org/1999/xhtml" lang="en">\n'
      '<head><meta charset="utf-8"/><title>'+safe_title+'</title>'
      '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
      '<body><pre class="book">'+escaped+'</pre></body></html>'
    )
    return doc.encode("utf-8")

def _container_xml()->bytes:
    return b'''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

def _style()->bytes:
    return b'''html,body{margin:0;padding:0;background:#fffdf8;color:#211d18}
body{padding:5%;font-family:serif}
pre.book{white-space:pre-wrap;word-wrap:break-word;font:1em/1.55 serif;margin:0}
'''

def _nav(title:str, navigation:list[dict])->bytes:
    items=[]
    # Front matter is exact canonical material before first navigation marker.
    items.append('<li><a href="front.xhtml">Front matter</a></li>')
    for i,item in enumerate(navigation):
        label=item.get("line") or f"Section {i+1}"
        subtitle=item.get("subtitle")
        if subtitle:
            label=f"{label} — {subtitle}"
        items.append(f'<li><a href="section-{i+1:03d}.xhtml">{xml_escape(label)}</a></li>')
    return (
      '<?xml version="1.0" encoding="utf-8"?>\n'
      '<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" '
      'xmlns:epub="http://www.idpf.org/2007/ops" lang="en"><head><meta charset="utf-8"/>'
      f'<title>{xml_escape(title)} — Contents</title><link rel="stylesheet" type="text/css" href="style.css"/></head>'
      '<body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>'+''.join(items)+'</ol></nav></body></html>'
    ).encode("utf-8")

def _opf(job_id:str,title:str,author:str,section_count:int,canonical_sha256:str)->bytes:
    manifest=[
      '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
      '<item id="css" href="style.css" media-type="text/css"/>',
      '<item id="source" href="source/canonical.txt" media-type="text/plain"/>',
      '<item id="front" href="front.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine=['<itemref idref="front"/>']
    for i in range(section_count):
        ident=f"s{i+1:03d}"
        href=f"section-{i+1:03d}.xhtml"
        manifest.append(f'<item id="{ident}" href="{href}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{ident}"/>')
    uid=f"urn:jakeai:{job_id}:{canonical_sha256}"
    return (
      '<?xml version="1.0" encoding="utf-8"?>'
      '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">'
      '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
      f'<dc:identifier id="pub-id">{xml_escape(uid)}</dc:identifier>'
      f'<dc:title>{xml_escape(title)}</dc:title><dc:creator>{xml_escape(author)}</dc:creator>'
      '<dc:language>en</dc:language>'
      f'<meta property="dcterms:modified">{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>'
      f'<meta property="jakeai:canonical-sha256">{canonical_sha256}</meta>'
      '<meta property="jakeai:text-policy">immutable-exact-source</meta>'
      '</metadata><manifest>'+''.join(manifest)+'</manifest><spine>'+''.join(spine)+'</spine></package>'
    ).encode("utf-8")

def build_epub(job_id:str,title:str,author:str)->dict:
    locks=list_locks()
    structures=list_structures()
    lock=locks.get(job_id)
    structure=structures.get(job_id)
    if not lock or not structure:
        raise ValueError("source lock or structure map missing")
    if structure["status"]!="verified":
        raise ValueError("structure map is not verified")
    mapping=json.loads(structure["mapping_json"])
    if not mapping.get("exact_reassembly_verified") or not mapping.get("semantic_count_verified"):
        raise ValueError("structure verification incomplete")

    source=Path(lock["source_file"]).read_bytes()
    canonical_sha=lock["canonical_sha256"]
    if _sha(source)!=canonical_sha:
        raise ValueError("canonical source hash mismatch")

    c=_conn()
    existing=c.execute("SELECT * FROM book_epub_builds WHERE job_id=?",(job_id,)).fetchone()
    if existing and existing["canonical_sha256"]==canonical_sha and existing["status"]=="ready" and Path(existing["epub_path"]).exists():
        data=Path(existing["epub_path"]).read_bytes()
        if _sha(data)==existing["epub_sha256"]:
            out=dict(existing); c.close(); return out
    c.close()

    segments=mapping.get("segments") or []
    navigation=mapping.get("navigation") or []
    if len(segments)!=len(navigation)+1:
        raise ValueError("EPUB packaging requires one front segment plus one segment per navigation entry")

    xhtml_files=[]
    reconstructed=[]
    for idx,seg in enumerate(segments):
        a,b=int(seg["start"]),int(seg["end"])
        chunk=source[a:b]
        reconstructed.append(chunk)
        if idx==0:
            filename="front.xhtml"
            section_title="Front matter"
        else:
            filename=f"section-{idx:03d}.xhtml"
            nav=navigation[idx-1]
            section_title=nav.get("line") or f"Section {idx}"
        xhtml_files.append((filename,_xhtml(section_title,chunk)))

    if b"".join(reconstructed)!=source or _sha(b"".join(reconstructed))!=canonical_sha:
        raise ValueError("EPUB segment reconstruction changed canonical source")

    passport={
      "edition_id":job_id,
      "status":"PRE_RELEASE",
      "canonical_sha256":canonical_sha,
      "canonical_bytes":len(source),
      "source_text_policy":"immutable_exact_source",
      "xhtml_transform":"HTML escaping only; each transformed section round-trips to its exact UTF-8 source bytes.",
      "exact_roundtrip_verified":True,
      "public":False,
      "paid":False,
      "human_release_approved":False,
      "built_at":_now(),
    }

    out_path=_out_dir()/(job_id+".epub")
    tmp=out_path.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp,"w") as z:
        mi=zipfile.ZipInfo("mimetype")
        mi.compress_type=zipfile.ZIP_STORED
        z.writestr(mi,b"application/epub+zip")
        z.writestr("META-INF/container.xml",_container_xml(),compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/jakeai-fidelity.json",json.dumps(passport,separators=(",",":"),ensure_ascii=False).encode("utf-8"),compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css",_style(),compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml",_nav(title,navigation),compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf",_opf(job_id,title,author,len(navigation),canonical_sha),compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/source/canonical.txt",source,compress_type=zipfile.ZIP_DEFLATED)
        for name,data in xhtml_files:
            z.writestr("OEBPS/"+name,data,compress_type=zipfile.ZIP_DEFLATED)

    # Validate the actual ZIP artifact, not just the inputs.
    with zipfile.ZipFile(tmp,"r") as z:
        if z.namelist()[0]!="mimetype" or z.read("mimetype")!=b"application/epub+zip":
            raise ValueError("invalid EPUB mimetype packaging")
        archived_source=z.read("OEBPS/source/canonical.txt")
        if archived_source!=source or _sha(archived_source)!=canonical_sha:
            raise ValueError("archived canonical source changed")
        for idx,seg in enumerate(segments):
            name="OEBPS/front.xhtml" if idx==0 else f"OEBPS/section-{idx:03d}.xhtml"
            doc=z.read(name).decode("utf-8")
            start=doc.index('<pre class="book">')+len('<pre class="book">')
            end=doc.index('</pre>',start)
            recovered=html.unescape(doc[start:end]).encode("utf-8")
            expected=source[int(seg["start"]):int(seg["end"])]
            if recovered!=expected:
                raise ValueError(f"EPUB XHTML roundtrip failed for segment {idx}")

    epub_bytes=tmp.read_bytes()
    epub_sha=_sha(epub_bytes)
    tmp.replace(out_path)
    c=_conn()
    c.execute("""INSERT OR REPLACE INTO book_epub_builds
      (job_id,canonical_sha256,epub_sha256,epub_bytes,epub_path,section_count,exact_roundtrip_verified,status,built_at)
      VALUES (?,?,?,?,?,?,?,?,?)""",(
        job_id,canonical_sha,epub_sha,len(epub_bytes),str(out_path),len(navigation),1,"ready",_now()
    ))
    c.commit()
    row=c.execute("SELECT * FROM book_epub_builds WHERE job_id=?",(job_id,)).fetchone()
    c.close()
    return dict(row)

def build_all(book_meta:dict):
    for job_id,meta in book_meta.items():
        try:
            build_epub(job_id,meta["title"],meta["author"])
        except Exception as exc:
            print(f"[book-factory] EPUB blocked for {job_id}: {exc}",flush=True)
        time.sleep(0.1)

def start_epub_builder(book_meta:dict):
    _conn().close()
    threading.Thread(target=build_all,args=(book_meta,),daemon=True,name="book-factory-epub-builder").start()

def get_build(job_id:str):
    c=_conn()
    row=c.execute("SELECT * FROM book_epub_builds WHERE job_id=?",(job_id,)).fetchone()
    c.close()
    return dict(row) if row else None

def public_build(row:dict|None):
    if not row:
        return {"status":"pending","exact_roundtrip_verified":False}
    return {
      "status":row["status"],
      "canonical_sha256":row["canonical_sha256"],
      "epub_sha256":row["epub_sha256"],
      "epub_bytes":row["epub_bytes"],
      "section_count":row["section_count"],
      "exact_roundtrip_verified":bool(row["exact_roundtrip_verified"]),
      "built_at":row["built_at"],
      "public":False,
      "paid":False,
    }
