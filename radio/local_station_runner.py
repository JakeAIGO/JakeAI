#!/usr/bin/env python3
"""KJAI 404 local station showrunner.

Builds a PRIVATE radio-show proof from cleared/original tracks and fresh DJ copy.
DJ speech uses the shared JakeAI founder voice adapter locally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
import torchaudio as ta

from jakeai_local_voice import load_runtime, normalize_audio, save_wav, synthesize
from radio_engine import RadioContext, RadioMemory, Song, generate_break
from radio.programmer import build_rotation


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_audio(path: Path):
    wav, sr = ta.load(str(path))
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    elif wav.shape[0] > 2:
        wav = wav[:2]
    return wav.to(torch.float32), sr


def resample(wav, sr, target):
    if sr == target:
        return wav
    return ta.functional.resample(wav, sr, target)


def peak_normalize(wav, db=-3.0):
    peak = float(wav.abs().max().item())
    if peak <= 0:
        return wav
    target = 10 ** (db / 20)
    return wav * min(target / peak, 4.0)


def crossfade(a, b, sr, seconds=0.8):
    n = min(int(sr * seconds), a.shape[-1], b.shape[-1])
    if n <= 0:
        return torch.cat([a, b], dim=1)
    fade_out = torch.linspace(1, 0, n, dtype=a.dtype).view(1, -1)
    fade_in = torch.linspace(0, 1, n, dtype=b.dtype).view(1, -1)
    mix = a[:, -n:] * fade_out + b[:, :n] * fade_in
    return torch.cat([a[:, :-n], mix, b[:, n:]], dim=1)


def host_segment(runtime, text, voice, sr, out_file):
    wav, voice_sr, seed = synthesize(
        runtime, text, voice,
        namespace="KJAI-404",
        verify_words=False,
    )
    wav, qa = normalize_audio(wav)
    wav = resample(wav, voice_sr, sr)
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    meta = save_wav(out_file, wav, sr)
    return wav, {"seed": seed, "qa": qa, "audio": meta}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--context", default=None)
    ap.add_argument("--max-tracks", type=int, default=6)
    ap.add_argument("--device", default="auto", choices=["auto","cpu","cuda"])
    ap.add_argument("--private-unwatermarked", action="store_true")
    ap.add_argument("--allow-unreviewed-music", action="store_true")
    args = ap.parse_args()

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    if not catalog:
        raise RuntimeError("Song catalog is empty")
    tracks = build_rotation(catalog, args.max_tracks)

    if not args.allow_unreviewed_music:
        blocked = [x["id"] for x in tracks if not x.get("commercial_ok")]
        if blocked:
            raise RuntimeError(
                "Music is not commercial-cleared: " + ", ".join(blocked) +
                ". For PRIVATE QA only, pass --allow-unreviewed-music."
            )

    context = {}
    if args.context:
        context = json.loads(Path(args.context).read_text(encoding="utf-8"))

    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    breaks_dir = out / "breaks"
    breaks_dir.mkdir(exist_ok=True)

    runtime = load_runtime(
        args.device,
        allow_private_unwatermarked=args.private_unwatermarked,
    )
    memory = RadioMemory(str(out / "kjai404-memory.db"))
    voice = Path(args.voice).expanduser().resolve()

    show = None
    manifest = {
        "station": "KJAI 404",
        "tagline": "Signal Found",
        "host_voice": "JakeAI Original AI Narration",
        "engine": runtime.engine,
        "watermarked": runtime.watermarked,
        "private_unwatermarked": runtime.private_unwatermarked,
        "public_release": False,
        "commercial_release": False,
        "music_review_required": any(not x.get("commercial_ok") for x in tracks),
        "started_at": time.time(),
        "segments": [],
    }

    target_sr = None
    previous_song = None

    for i, row in enumerate(tracks):
        song = Song(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            genre=row.get("genre","original"),
            energy=float(row.get("energy",0.5)),
            mood=row.get("mood","neutral"),
            instrumental=bool(row.get("instrumental",False)),
            source=row.get("source","original"),
            commercial_ok=bool(row.get("commercial_ok",False)),
        )

        ctx = RadioContext(
            station_id="KJAI-404",
            previous_song=previous_song,
            next_song=song,
            game_time=context.get("game_time"),
            location=context.get("location"),
            weather=context.get("weather"),
            recent_event=context.get("recent_event"),
            player_state=context.get("player_state"),
            listen_minutes=context.get("listen_minutes"),
            session_id=context.get("session_id","private-demo"),
        )
        br = generate_break(ctx, memory=memory)

        track_path = Path(row["file"]).expanduser().resolve()
        track, sr = load_audio(track_path)
        target_sr = sr if target_sr is None else target_sr
        track = resample(track, sr, target_sr)
        track = peak_normalize(track)

        break_path = breaks_dir / f"break-{i:03d}.wav"
        voice_wav, voice_meta = host_segment(
            runtime, br.text, voice, target_sr, break_path
        )

        # Natural radio behavior: crossfade the end of the DJ break into the song.
        segment = crossfade(voice_wav, track, target_sr, seconds=0.65)
        show = segment if show is None else crossfade(show, segment, target_sr, seconds=0.9)

        manifest["segments"].append({
            "index": i,
            "dj_break": {
                "id": br.id,
                "text": br.text,
                "memory_key": br.memory_key,
                **voice_meta,
            },
            "song": {
                "id": song.id,
                "title": song.title,
                "artist": song.artist,
                "file": str(track_path),
                "audio_sha256": sha256(track_path.read_bytes()),
                "commercial_ok": song.commercial_ok,
                "review_status": row.get("review_status"),
            },
        })
        previous_song = song
        (out / "show-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if show is None:
        raise RuntimeError("No station audio was assembled")

    show = peak_normalize(show)
    show_path = out / "KJAI_404_SIGNAL_FOUND_PRIVATE_DEMO.wav"
    ta.save(str(show_path), show.cpu(), target_sr)
    manifest["completed_at"] = time.time()
    manifest["show_audio"] = {
        "path": str(show_path),
        "bytes": show_path.stat().st_size,
        "sha256": sha256(show_path.read_bytes()),
        "seconds": show.shape[-1] / target_sr,
    }
    manifest["release_status"] = (
        "PRIVATE_QA_ONLY"
        if runtime.private_unwatermarked or manifest["music_review_required"]
        else "PRIVATE_RELEASE_CANDIDATE"
    )
    (out / "show-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nKJAI 404 private show assembled.")
    print(show_path)
    print("Release status:", manifest["release_status"])
    print("No public release has occurred.")


if __name__ == "__main__":
    main()
