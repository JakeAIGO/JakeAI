#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "release_promotion_policy.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha(ref="HEAD"):
    p = subprocess.run(["git", "rev-parse", ref], cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "git rev-parse failed")
    return p.stdout.strip()


def validate_request(policy, request, fingerprint):
    errors = []
    for field in policy["required_request_fields"]:
        if field not in request:
            errors.append(f"missing promotion request field: {field}")
    if errors:
        return errors
    if request["schema_version"] != "1.0":
        errors.append("promotion request schema_version must be 1.0")
    if request["target"] not in policy["allowed_targets"]:
        errors.append("promotion target is not allowed")
    auth_fields = [
        "promotion_authorized",
        "deployment_authorized",
        "publication_authorized",
        "commercial_activation_authorized",
    ]
    for field in auth_fields:
        if not isinstance(request[field], bool):
            errors.append(f"{field} must be boolean")
    any_authorized = any(request.get(field) is True for field in auth_fields)
    if any_authorized:
        if request.get("status") != "approved":
            errors.append("authorization requires status=approved")
        if request.get("candidate_manifest_sha256") != fingerprint.get("candidate_manifest_sha256"):
            errors.append("authorization requires exact candidate manifest fingerprint match")
        if request.get("candidate_builder_head") != fingerprint.get("builder_head"):
            errors.append("authorization requires exact candidate builder head match")
        if not str(request.get("human_approval_record") or "").strip():
            errors.append("authorization requires a human_approval_record")
        reviews = request.get("reviews") or {}
        for lane, state in policy["required_approval_states"].items():
            if reviews.get(lane) != state:
                errors.append(f"authorization requires {lane} review={state}")
    return errors


def build_release_plan():
    policy = load(POLICY_PATH)
    candidate_manifest_path = ROOT / policy["candidate_manifest"]
    candidate_fingerprint_path = ROOT / policy["candidate_fingerprint"]
    request_path = ROOT / policy["promotion_request"]
    if not candidate_manifest_path.exists() or not candidate_fingerprint_path.exists():
        raise ValueError("production candidate artifacts are missing; build candidate first")
    candidate = load(candidate_manifest_path)
    fingerprint = load(candidate_fingerprint_path)
    request = load(request_path)
    errors = validate_request(policy, request, fingerprint)
    authorized = not errors and request.get("promotion_authorized") is True
    release_plan = {
        "schema_version": "1.0",
        "engine": policy["engine"],
        "engine_head": git_sha(),
        "source_baseline": policy["source_baseline"],
        "candidate_builder_head": fingerprint.get("builder_head"),
        "candidate_manifest_sha256": fingerprint.get("candidate_manifest_sha256"),
        "target": request.get("target"),
        "promotion_authorized": authorized,
        "deployment_authorized": authorized and request.get("deployment_authorized") is True,
        "publication_authorized": authorized and request.get("publication_authorized") is True,
        "commercial_activation_authorized": authorized and request.get("commercial_activation_authorized") is True,
        "execution_performed": False,
        "state": "authorized_plan_only" if authorized else "blocked_pending_explicit_approval",
        "errors": errors,
        "candidate_summary": {
            "modules": len(candidate.get("modules", [])),
            "products": len(candidate.get("products", [])),
            "platform_terms": len(candidate.get("platform_terms", {})),
        },
    }
    rollback_plan = {
        "schema_version": "1.0",
        "source_baseline": policy["source_baseline"],
        "rollback_ref": policy["source_baseline"],
        "candidate_builder_head": fingerprint.get("builder_head"),
        "candidate_manifest_sha256": fingerprint.get("candidate_manifest_sha256"),
        "execution_performed": False,
        "state": "rollback_reference_recorded",
    }
    out = ROOT / "build" / "release_promotion"
    out.mkdir(parents=True, exist_ok=True)
    (out / "release_plan.json").write_text(json.dumps(release_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "rollback_plan.json").write_text(json.dumps(rollback_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "promotion_authorized": release_plan["promotion_authorized"],
        "execution_performed": False,
        "state": release_plan["state"],
        "errors": errors,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(build_release_plan())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        sys.exit(1)
