"""JakeAI Media Gateway — local-first provider-independent media routing.

Core rule:
JakeAI owns the workflow, prompts, provenance, QA, storage, and release gates.
Media engines/providers are replaceable adapters.

Paid adapters are disabled by default and may not be selected unless:
1) the adapter is explicitly enabled in environment, AND
2) a spend ceiling is present, AND
3) the caller explicitly requests paid fallback.

This module is intentionally a routing/policy layer. Local workers (Chatterbox,
ACE-Step, FFmpeg, deterministic SVG/HTML) can run on a user's/worker's machine
without creating a per-character/per-song/per-play vendor bill.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from mission_dispatcher import _require_control

router = APIRouter()

MEDIA_POLICY = {
    "architecture": "local_first_provider_independent",
    "shared_consumers": ["JakeAI Editions", "JakeAI Radio", "JakeAI Games", "GridWorks private production"],
    "principle": "JakeAI is the system; models and media providers are replaceable adapters.",
    "default_spend_policy": "zero_marginal_vendor_cost",
    "paid_fallback_default": False,
    "public_release_gate": True,
    "rights_gate": True,
    "provenance_gate": True,
    "human_release_gate": True,
}

ADAPTERS = {
    "speech": [
        {
            "id": "local_chatterbox",
            "label": "Local Chatterbox",
            "mode": "local",
            "priority": 10,
            "marginal_vendor_cost": 0,
            "capabilities": ["narration", "voice_reference", "dj_host"],
            "status": "primary",
            "notes": "Private reference stays local. Public release requires provenance/watermark QA.",
        },
        {
            "id": "creative_claw_speech",
            "label": "Creative Claw Speech",
            "mode": "paid_external",
            "priority": 90,
            "marginal_vendor_cost": "metered",
            "capabilities": ["speech", "provider_comparison"],
            "status": "optional_fallback",
            "enabled_env": "MEDIA_ENABLE_CREATIVE_CLAW",
        },
    ],
    "music": [
        {
            "id": "local_ace_step",
            "label": "Local ACE-Step 1.5",
            "mode": "local",
            "priority": 10,
            "marginal_vendor_cost": 0,
            "capabilities": ["text_to_music", "lyrics", "synthetic_vocals", "instrumental"],
            "status": "primary",
            "notes": "Founder voice is never passed into song generation.",
        },
        {
            "id": "creative_claw_music",
            "label": "Creative Claw Music",
            "mode": "paid_external",
            "priority": 90,
            "marginal_vendor_cost": "metered",
            "capabilities": ["music"],
            "status": "optional_fallback",
            "enabled_env": "MEDIA_ENABLE_CREATIVE_CLAW",
        },
    ],
    "audio_mix": [
        {
            "id": "local_ffmpeg",
            "label": "Local FFmpeg",
            "mode": "local",
            "priority": 10,
            "marginal_vendor_cost": 0,
            "capabilities": ["mix", "concat", "normalize", "crossfade", "encode", "radio_assembly"],
            "status": "primary",
        }
    ],
    "graphics": [
        {
            "id": "deterministic_svg_html",
            "label": "JakeAI SVG / HTML Renderer",
            "mode": "local",
            "priority": 10,
            "marginal_vendor_cost": 0,
            "capabilities": ["book_covers", "cards", "ui_art", "diagrams", "branded_assets"],
            "status": "primary_when_suitable",
        },
        {
            "id": "native_image_generation",
            "label": "Native Image Generation",
            "mode": "platform",
            "priority": 30,
            "marginal_vendor_cost": "plan_dependent",
            "capabilities": ["generative_art", "concept_art", "visual_assets"],
            "status": "optional",
            "notes": "Use when generative visuals materially improve the asset; not a runtime product dependency.",
        },
        {
            "id": "creative_claw_image",
            "label": "Creative Claw Image",
            "mode": "paid_external",
            "priority": 90,
            "marginal_vendor_cost": "metered",
            "capabilities": ["image"],
            "status": "optional_fallback",
            "enabled_env": "MEDIA_ENABLE_CREATIVE_CLAW",
        },
    ],
    "video": [
        {
            "id": "local_ffmpeg_video",
            "label": "Local FFmpeg / Existing Assets",
            "mode": "local",
            "priority": 10,
            "marginal_vendor_cost": 0,
            "capabilities": ["edit", "assemble", "transcode", "audio_mix", "captions"],
            "status": "primary_for_post",
        },
        {
            "id": "external_video_renderer",
            "label": "External Generative Video Renderer",
            "mode": "paid_external",
            "priority": 80,
            "marginal_vendor_cost": "metered",
            "capabilities": ["generative_video"],
            "status": "optional_when_quality_justifies_cost",
            "enabled_env": "MEDIA_ENABLE_PAID_VIDEO",
        },
    ],
}

VOICE_POLICY = {
    "founder_voice_id": "jakeai_original_ai_narration",
    "allowed": ["book_narration", "ordinary_radio_dj_hosting", "JakeAI station identification"],
    "forbidden": ["song_vocals", "sexual_material", "political_content", "advertising", "impersonation"],
    "private_reference_must_remain_private": True,
}

class RouteRequest(BaseModel):
    media_type: Literal["speech","music","audio_mix","graphics","video"]
    capability: str = ""
    allow_paid_fallback: bool = False
    approved_spend_cents: int = Field(default=0, ge=0)
    require_local: bool = False

def _truthy(name:str)->bool:
    return os.environ.get(name,"").strip().lower() in {"1","true","yes","on"}

def _adapter_enabled(adapter:dict, req:RouteRequest)->bool:
    if adapter["mode"] != "paid_external":
        return True
    env = adapter.get("enabled_env")
    if env and not _truthy(env):
        return False
    if not req.allow_paid_fallback:
        return False
    if req.approved_spend_cents <= 0:
        return False
    return True

def choose_adapter(req:RouteRequest):
    candidates = ADAPTERS.get(req.media_type) or []
    for adapter in sorted(candidates,key=lambda x:int(x.get("priority",999))):
        if req.require_local and adapter.get("mode") != "local":
            continue
        if req.capability and req.capability not in adapter.get("capabilities",[]):
            continue
        if not _adapter_enabled(adapter,req):
            continue
        return adapter
    raise HTTPException(409,"No media adapter satisfies the current local/cost/approval policy")

def legacy_asset_inventory():
    path=Path(__file__).resolve().parent/"media_legacy_assets.json"
    if not path.exists():
        return {"assets":[],"status":"not_scanned"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"assets":[],"status":"invalid"}

@router.get("/api/v1/media-gateway/private/status")
@router.get("/v1/media-gateway/private/status")
def media_status(request:Request,authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    inv=legacy_asset_inventory()
    return {
      "status":"local_first_live",
      "policy":MEDIA_POLICY,
      "voice_policy":VOICE_POLICY,
      "adapters":ADAPTERS,
      "creative_claw_role":"optional_paid_fallback_only",
      "creative_claw_enabled":_truthy("MEDIA_ENABLE_CREATIVE_CLAW"),
      "paid_video_enabled":_truthy("MEDIA_ENABLE_PAID_VIDEO"),
      "legacy_external_assets":len(inv.get("assets",[])),
      "legacy_asset_migration_status":inv.get("status"),
      "shared_cue_engine":{
        "module":"media_cue_engine.py",
        "consumers":MEDIA_POLICY["shared_consumers"],
        "gridworks_program":"media-programs/gridworks_sizzle_v1_6.json",
        "game_example":"media-programs/game_dynamic_media_example.json",
      },
    }

@router.post("/api/v1/media-gateway/private/route")
@router.post("/v1/media-gateway/private/route")
def media_route(body:RouteRequest,request:Request,authorization:Optional[str]=Header(None)):
    _require_control(authorization,request)
    adapter=choose_adapter(body)
    return {
      "selected":adapter,
      "paid_fallback_requested":body.allow_paid_fallback,
      "approved_spend_cents":body.approved_spend_cents,
      "policy":MEDIA_POLICY["architecture"],
    }

def register_media_gateway_routes(app):
    app.include_router(router)
