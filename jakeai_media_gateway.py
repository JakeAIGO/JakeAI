"""JakeAI Media Gateway.

JakeAI owns routing, policy, provenance and release gates. Media engines are
replaceable adapters.

Default policy:
- local/self-hosted first
- no automatic paid fallback
- external hosted providers are optional adapters only
- release fails closed if provenance/licensing/watermark requirements are not met
- private founder voice stays local and is never uploaded by this gateway
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

from mission_dispatcher import _require_control

router = APIRouter()

LOCAL_MEDIA_ROOT = Path(
    os.environ.get("JAKEAI_MEDIA_ROOT", "").strip()
    or ("/data/jakeai-media" if os.path.isdir("/data") else "/tmp/jakeai-media")
)
LEGACY_DIR = LOCAL_MEDIA_ROOT / "legacy-assets"
LEGACY_MANIFEST = LOCAL_MEDIA_ROOT / "legacy-assets.json"

MEDIA_POLICY = {
    "owner": "JakeAI",
    "routing": "local_first",
    "automatic_paid_fallback": False,
    "provider_independence": True,
    "spend_gate": "explicit_human_approval_required",
    "public_release_gate": True,
    "provenance_required": True,
    "licensing_required": True,
    "private_founder_voice_upload_allowed": False,
}

ADAPTERS = {
    "voice": [{
        "id": "local_chatterbox",
        "role": "primary",
        "kind": "self_hosted",
        "engine": "Chatterbox Nano/Turbo",
        "marginal_metered_cost": False,
    }],
    "music": [{
        "id": "local_ace_step",
        "role": "primary",
        "kind": "self_hosted",
        "engine": "ACE-Step 1.5",
        "marginal_metered_cost": False,
    }],
    "audio_mix": [{
        "id": "local_ffmpeg_torchaudio",
        "role": "primary",
        "kind": "self_hosted",
        "engine": "FFmpeg / TorchAudio",
        "marginal_metered_cost": False,
    }],
    "graphics": [{
        "id": "deterministic_svg",
        "role": "primary_when_suitable",
        "kind": "self_hosted",
        "engine": "JakeAI SVG/code renderer",
        "marginal_metered_cost": False,
    },{
        "id": "native_image_generation",
        "role": "replaceable_model_adapter",
        "kind": "external_or_native_model",
        "engine": "selected available image model",
        "marginal_metered_cost": "provider_dependent",
    }],
    "video": [{
        "id": "external_video_renderer",
        "role": "optional",
        "kind": "replaceable_model_adapter",
        "engine": "selected video model/provider",
        "marginal_metered_cost": "provider_dependent",
    }],
    "optional_hosted": [{
        "id": "creative_claw",
        "role": "optional_adapter_only",
        "kind": "hosted_wrapper",
        "enabled_by_default": False,
        "automatic_fallback": False,
        "core_dependency": False,
    }],
}

LEGACY_ASSETS = {
    "neon-approach": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/a21ef492-565e-41f8-8e08-402fdd4d4f17.png",
        "filename": "neon-approach.png",
    },
    "neon-overmind": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/6dcf0d3a-fa33-418b-81f9-7c18bca56da0.png",
        "filename": "neon-overmind.png",
    },
    "neon-player": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/3528153f-ec3c-4a9d-bbea-869ca726edc9.webp",
        "filename": "neon-player.webp",
    },
    "neon-drone": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/7abd8ab2-8176-4fab-91ea-bda55033aa95.webp",
        "filename": "neon-drone.webp",
    },
    "neon-boss": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/269f1666-9fbd-4b1d-a128-e40bceb8208b.webp",
        "filename": "neon-boss.webp",
    },
    "neon-orb": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/60428c3b-796c-45f6-8ea8-397ade9d2c48.webp",
        "filename": "neon-orb.webp",
    },
    "neon-node": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/c1e0ed50-25a6-44b5-9d94-f95a2b1d71fb.webp",
        "filename": "neon-node.webp",
    },
    "comic-origin-00": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/6f56e664-0ca1-402e-977c-09d13c58fc0c.png",
        "filename": "comic-origin-00.png",
    },
    "infinite-foundry-book": {
        "source_url": "https://cdn.creativeclaw.co/u/7a5f511f/images/93686b27-79de-48f0-bc54-75c4a140cd9e.png",
        "filename": "infinite-foundry-book.png",
    },
}

def _now():
    return datetime.now(timezone.utc).isoformat()

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _valid_image_bytes(data: bytes, filename: str) -> bool:
    if len(data) < 64:
        return False
    name = filename.lower()
    if name.endswith(".png"):
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if name.endswith(".webp"):
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return True

def _manifest():
    if LEGACY_MANIFEST.exists():
        try:
            return json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "updated_at": None, "assets": {}}

def _write_manifest(m):
    LOCAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = LEGACY_MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2), encoding="utf-8")
    tmp.replace(LEGACY_MANIFEST)

def _download_one(asset_id: str, spec: dict):
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    dest = LEGACY_DIR / spec["filename"]
    m = _manifest()
    existing = m["assets"].get(asset_id) or {}
    if dest.exists() and dest.stat().st_size >= 64:
        data = dest.read_bytes()
        digest = _sha(data)
        if existing.get("sha256") in {None, digest}:
            m["assets"][asset_id] = {
                **existing,
                "id": asset_id,
                "filename": spec["filename"],
                "local_path": str(dest),
                "sha256": digest,
                "bytes": len(data),
                "status": "cached",
                "source_vendor": "legacy_creative_claw_cdn",
                "source_url_retained_for_audit_only": spec["source_url"],
                "served_from": f"/api/v1/media/assets/{asset_id}",
            }
            m["updated_at"] = _now()
            _write_manifest(m)
            return

    req = urllib.request.Request(
        spec["source_url"],
        headers={"User-Agent": "JakeAI-Media-Migrator/1.0 (+https://jakeaiofficial.com/)"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = r.read()
        content_type = r.headers.get("Content-Type") or mimetypes.guess_type(spec["filename"])[0]
    if not _valid_image_bytes(data, spec["filename"]):
        raise RuntimeError(f"legacy asset failed image validation: {asset_id}")
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)

    m = _manifest()
    m["assets"][asset_id] = {
        "id": asset_id,
        "filename": spec["filename"],
        "local_path": str(dest),
        "sha256": _sha(data),
        "bytes": len(data),
        "content_type": content_type,
        "status": "cached",
        "source_vendor": "legacy_creative_claw_cdn",
        "source_url_retained_for_audit_only": spec["source_url"],
        "migrated_at": _now(),
        "served_from": f"/api/v1/media/assets/{asset_id}",
    }
    m["updated_at"] = _now()
    _write_manifest(m)

def migrate_legacy_assets():
    LOCAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    for asset_id, spec in LEGACY_ASSETS.items():
        try:
            _download_one(asset_id, spec)
            print(f"[media-gateway] cached legacy asset {asset_id}", flush=True)
        except Exception as exc:
            print(f"[media-gateway] legacy asset migration blocked for {asset_id}: {exc}", flush=True)

def start_media_gateway():
    LOCAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    threading.Thread(
        target=migrate_legacy_assets,
        daemon=True,
        name="jakeai-media-legacy-migrator",
    ).start()

def adapter_status():
    m = _manifest()
    assets = m.get("assets") or {}
    return {
        "policy": MEDIA_POLICY,
        "adapters": ADAPTERS,
        "legacy_asset_migration": {
            "total": len(LEGACY_ASSETS),
            "cached": sum(1 for k in LEGACY_ASSETS if (assets.get(k) or {}).get("status") == "cached"),
            "pending": [k for k in LEGACY_ASSETS if (assets.get(k) or {}).get("status") != "cached"],
            "manifest_updated_at": m.get("updated_at"),
        },
        "creative_claw": {
            "status": "optional_adapter_only",
            "core_dependency": False,
            "automatic_fallback": False,
            "new_media_default": False,
            "legacy_cdn_frontend_dependency_target": 0,
        },
    }

@router.get("/api/v1/media/private/status")
@router.get("/v1/media/private/status")
def media_status(request: Request, authorization: Optional[str] = Header(None)):
    _require_control(authorization, request)
    return adapter_status()

@router.get("/api/v1/media/assets/{asset_id}")
@router.get("/v1/media/assets/{asset_id}")
def media_asset(asset_id: str):
    if asset_id not in LEGACY_ASSETS:
        raise HTTPException(404, "Unknown JakeAI media asset")
    spec = LEGACY_ASSETS[asset_id]
    dest = LEGACY_DIR / spec["filename"]
    if not dest.exists() or dest.stat().st_size < 64:
        raise HTTPException(503, "JakeAI media asset is still migrating")
    media_type = mimetypes.guess_type(spec["filename"])[0] or "application/octet-stream"
    return FileResponse(
        str(dest),
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-JakeAI-Media-Source": "self-hosted-cache",
        },
    )

def register_media_gateway(app):
    start_media_gateway()
    app.include_router(router)
