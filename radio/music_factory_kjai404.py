#!/usr/bin/env python3
"""KJAI 404 local original-music factory.

Talks only to a locally running ACE-Step 1.5 REST API.
Generated tracks remain PRIVATE_ORIGINALITY_REVIEW_REQUIRED until a human
reviews them for unwanted similarity and the rights manifest is complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

try:
    from radio.artist_roster import load_artist_roster, artist_generation_prompt, artist_seed, artist_catalog_metadata
except ModuleNotFoundError:
    # Direct-script execution on Windows places the radio folder, not the repo root, on sys.path.
    from artist_roster import load_artist_roster, artist_generation_prompt, artist_seed, artist_catalog_metadata


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def call_json(url: str, payload: dict | None = None, timeout: int = 120):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=600) as r:
        return r.read()


def deterministic_seed(track_id: str) -> int:
    return int(hashlib.sha256(track_id.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="radio/artist_song_specs_v1.json")
    ap.add_argument("--artists", default="radio/artist_roster.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--model", default="acestep-v15-turbo")
    ap.add_argument("--poll-seconds", type=float, default=2.0)
    ap.add_argument("--max-duration", type=float, default=None, help="Private preview cap for each generated track")
    args = ap.parse_args()

    prompt_data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    prompts = prompt_data.get("tracks", []) if isinstance(prompt_data, dict) else prompt_data
    artists = load_artist_roster(args.artists)
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    health = call_json(args.api.rstrip("/") + "/health")
    if health.get("code") != 200:
        raise RuntimeError(f"ACE-Step API is not healthy: {health}")

    health_data = health.get("data") or {}
    if not health_data.get("models_initialized", False):
        print("ACE-Step server is alive; initializing the music model...")
        initialized = call_json(
            args.api.rstrip("/") + "/v1/init",
            {"model": args.model, "slot": 1, "init_llm": False},
            timeout=3600,
        )
        if initialized.get("code") != 200:
            raise RuntimeError(f"ACE-Step model initialization failed: {initialized}")
        health = call_json(args.api.rstrip("/") + "/health", timeout=120)
        health_data = health.get("data") or {}
        if not health_data.get("models_initialized", False):
            raise RuntimeError(f"ACE-Step model did not report initialized after /v1/init: {health}")
    print(f"ACE-Step model ready: {health_data.get('loaded_model') or args.model}")

    catalog = []
    for i, spec in enumerate(prompts, 1):
        tid = spec["id"]
        artist = artists.get(spec.get("artist_id")) if spec.get("artist_id") else None
        seed = artist_seed(artist, tid) if artist else deterministic_seed(tid)
        artist_name = artist["name"] if artist else spec.get("artist", "JakeAI House Instrumental")
        print(f"[{i}/{len(prompts)}] generating {tid} — {spec['title']} — {artist_name}")

        payload = {
            "prompt": artist_generation_prompt(artist, spec["prompt"]) if artist else spec["prompt"],
            "lyrics": spec.get("lyrics", ""),
            "thinking": False,
            "vocal_language": spec.get("vocal_language", "en"),
            "audio_format": "wav",
            "model": args.model,
            "audio_duration": min(float(spec["duration"]), float(args.max_duration)) if args.max_duration else spec["duration"],
            "bpm": spec["bpm"],
            "key_scale": spec["key_scale"],
            "time_signature": spec["time_signature"],
            "inference_steps": 8,
            "use_random_seed": False,
            "seed": seed,
            "batch_size": 1,
            "use_cot_caption": False,
            "use_cot_language": False,
        }
        created = call_json(args.api.rstrip("/") + "/release_task", payload)
        if created.get("code") != 200:
            raise RuntimeError(f"ACE-Step task failed to submit: {created}")
        task_id = created["data"]["task_id"]

        while True:
            time.sleep(args.poll_seconds)
            q = call_json(
                args.api.rstrip("/") + "/query_result",
                {"task_id_list": [task_id]},
            )
            rows = q.get("data") or []
            if not rows:
                continue
            row = rows[0]
            if row.get("status") == 2:
                raise RuntimeError(f"ACE-Step generation failed for {tid}: {row}")
            if row.get("status") != 1:
                continue

            results = json.loads(row["result"])
            item = results[0]
            file_url = item["file"]
            if file_url.startswith("/"):
                file_url = args.api.rstrip("/") + file_url
            audio = download(file_url)
            dest = out / f"{tid}.wav"
            dest.write_bytes(audio)
            if dest.stat().st_size < 4096:
                raise RuntimeError(f"Generated audio looks invalid: {dest}")

            entry = {
                "id": tid,
                "title": spec["title"],
                "artist": artist_name,
                "genre": ", ".join(artist.get("genres", [])) if artist else "original KJAI instrumental",
                "energy": 0.5,
                "mood": "station",
                "instrumental": not bool(spec.get("lyrics")),
                "file": str(dest),
                "audio_sha256": sha256(audio),
                "bytes": len(audio),
                "source": "ACE-Step 1.5 local generation",
                "model": args.model,
                "seed": seed,
                "prompt": payload["prompt"],
                "lyrics": spec.get("lyrics", ""),
                "rights_evidence": {
                    "engine_repo": "ace-step/ACE-Step-1.5",
                    "engine_repo_license": "MIT",
                    "model_repo": "ACE-Step/Ace-Step1.5",
                    "model_license": "MIT",
                },
                "commercial_ok": False,
                "review_status": "PRIVATE_ORIGINALITY_REVIEW_REQUIRED",
                "named_artist_prompt": False,
                "founder_voice_used": False,
                **(artist_catalog_metadata(artist) if artist else {
                    "artist_id": "KJAI-ART-HOUSE-INSTRUMENTAL",
                    "artist_type": "fictional_instrumental_project",
                    "identity_mode": "instrumental",
                }),
            }
            catalog.append(entry)
            (out / "kjai404-generated-catalog.json").write_text(
                json.dumps(catalog, indent=2), encoding="utf-8"
            )
            print(f"saved {dest.name}")
            break

    print("\nGeneration complete.")
    print("All tracks remain PRIVATE_ORIGINALITY_REVIEW_REQUIRED.")
    print("No track is marked commercial-ready automatically.")


if __name__ == "__main__":
    main()
