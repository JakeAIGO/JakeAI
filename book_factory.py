import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()
QUEUE_PATH = Path(__file__).resolve().parent / "book-factory" / "queue.json"
ALLOWED_RIGHTS_HOSTS = {"www.gutenberg.org", "gutenberg.org", "www.copyright.gov", "copyright.gov"}
PUBLIC_STAGES = {"candidate","rights_verified","source_verified","formatting","narration","text_qa","audio_qa","release_ready","public_preview","published"}

def _load():
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))

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
    return errors

def snapshot():
    data=_load()
    jobs=data.get("jobs",[])
    validations=[{"id":j.get("id"),"errors":validate_job(j)} for j in jobs]
    invalid=[x for x in validations if x["errors"]]
    counts={
        "total":len(jobs),
        "rights_green":sum(1 for j in jobs if j.get("rights")=="green"),
        "rights_pending":sum(1 for j in jobs if j.get("rights")=="pending"),
        "public_preview":sum(1 for j in jobs if j.get("release")=="public_preview"),
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
