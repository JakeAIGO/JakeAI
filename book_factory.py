import json
from pathlib import Path
from fastapi import APIRouter
from book_source_lock import list_locks, public_lock_record, start_autolock
from book_structure_map import list_structures, public_structure, start_structure_mapper

router = APIRouter()
QUEUE_PATH = Path(__file__).resolve().parent / "book-factory" / "queue.json"
ALLOWED_RIGHTS_HOSTS = {"www.gutenberg.org", "gutenberg.org", "www.copyright.gov", "copyright.gov"}
QUEUE_REVISION = "2026-09-24-exact-text-lock"
PUBLIC_STAGES = {"candidate","rights_verified","source_verified","structure_verified","formatting","narration","text_qa","audio_qa","release_ready","public_preview","published"}

def _load():
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))

def _overlay_runtime_locks(jobs):
    locks=list_locks()
    structures=list_structures()
    out=[]
    for original in jobs:
        job=dict(original)
        row=locks.get(job.get("id"))
        structure_row=structures.get(job.get("id"))
        if row:
            job["text_lock"]=public_lock_record(row)
            if job.get("stage")=="rights_verified":
                job["stage"]="source_verified"
        if structure_row:
            job["structure_map"]=public_structure(structure_row)
            if job.get("stage")=="source_verified":
                job["stage"]="structure_verified"
        out.append(job)
    return out

def validate_job(job):
    errors=[]
    rights=job.get("rights")
    stage=job.get("stage")
    if stage not in PUBLIC_STAGES:
        errors.append("unknown_stage")
    if rights=="green":
        if not job.get("source_url") or not job.get("source_id"):
            errors.append("green_without_source_evidence")
        if job.get("source_rights_statement")!="Public domain in the USA":
            errors.append("green_without_exact_us_public_domain_statement")
    elif rights!="pending":
        errors.append("unsupported_rights_state")
    if job.get("paid_release") and stage!="published":
        errors.append("paid_release_before_published_stage")
    if job.get("release") in {"public_preview","published"} and rights!="green":
        errors.append("public_release_without_green_rights")

    text_lock = job.get("text_lock") or {}
    full_text_stage = stage in {"source_verified","structure_verified","formatting","narration","text_qa","audio_qa","release_ready","published"}
    full_text_release = job.get("release") == "published" or job.get("paid_release") is True
    if full_text_stage or full_text_release:
        if text_lock.get("status") != "locked":
            errors.append("full_text_without_immutable_source_lock")
        if text_lock.get("comparison") != "exact_bytes":
            errors.append("full_text_without_exact_byte_comparison")
        if text_lock.get("normalization") != "none":
            errors.append("text_normalization_is_forbidden")
        if not text_lock.get("canonical_sha256"):
            errors.append("full_text_without_canonical_sha256")
        if not text_lock.get("fidelity_verified"):
            errors.append("full_text_without_verified_fidelity")

    if job.get("release") == "public_preview" and text_lock.get("status") != "locked":
        if job.get("content_mode") != "marketing_preview_no_full_book_text":
            errors.append("preview_without_lock_must_not_contain_book_body")

    structure = job.get("structure_map") or {}
    if stage in {"structure_verified","formatting","narration","text_qa","audio_qa","release_ready","published"}:
        if structure.get("status") != "verified":
            errors.append("advanced_without_verified_structure")
        if not structure.get("exact_reassembly_verified"):
            errors.append("structure_without_exact_reassembly")
        if structure.get("canonical_sha256") != text_lock.get("canonical_sha256"):
            errors.append("structure_hash_does_not_match_text_lock")
        if structure.get("text_modified") is not False:
            errors.append("structure_modified_text")
        if structure.get("normalization") != "none":
            errors.append("structure_normalization_is_forbidden")
    return errors

def snapshot():
    data=_load()
    jobs=_overlay_runtime_locks(data.get("jobs",[]))
    validations=[{"id":j.get("id"),"errors":validate_job(j)} for j in jobs]
    invalid=[x for x in validations if x["errors"]]
    counts={
        "total":len(jobs),
        "rights_green":sum(1 for j in jobs if j.get("rights")=="green"),
        "rights_pending":sum(1 for j in jobs if j.get("rights")=="pending"),
        "public_preview":sum(1 for j in jobs if j.get("release")=="public_preview"),
        "source_locked":sum(1 for j in jobs if (j.get("text_lock") or {}).get("status")=="locked"),
        "structure_mapped":sum(1 for j in jobs if (j.get("structure_map") or {}).get("status")=="verified"),
        "published_paid":sum(1 for j in jobs if j.get("paid_release") is True),
        "invalid":len(invalid)
    }
    return {"factory_id":data.get("factory_id"),"territory":data.get("territory"),"policy":data.get("policy"),"counts":counts,"valid":not invalid,"validation_errors":invalid,"jobs":jobs}

@router.get("/v1/book-factory/status")
@router.get("/api/v1/book-factory/status")
def book_factory_status():
    s=snapshot()
    return {"factory_id":s["factory_id"],"territory":s["territory"],"policy":s["policy"],"counts":s["counts"],"valid":s["valid"]}

@router.get("/v1/book-factory/jobs")
@router.get("/api/v1/book-factory/jobs")
def book_factory_jobs():
    s=snapshot()
    return {"factory_id":s["factory_id"],"counts":s["counts"],"valid":s["valid"],"jobs":s["jobs"]}

def register_book_factory_routes(app):
    app.include_router(router)
    start_autolock(QUEUE_PATH)
    start_structure_mapper()
