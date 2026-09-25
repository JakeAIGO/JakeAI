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
from radio.broadcast_engine import assemble_broadcast, PRODUCER_V2


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

    rendered_songs = []
    rendered_breaks = []
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
        break_path = breaks_dir / f"break-{i:03d}.wav"

        # The founder voice remains a separate DJ layer.
        voice_wav, voice_meta = host_segment(
            runtime, br.text, voice, 48000, break_path
        )

        rendered_breaks.append({
            "id": "OPEN" if i == 0 else f"B{i:02d}",
            "path": str(break_path),
            "after_track_id": None if i == 0 else tracks[i-1]["id"],
            "before_track_id": row["id"],
            "text": br.text,
            "memory_key": br.memory_key,
            "voice_meta": voice_meta,
        })
        rendered_songs.append({
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "path": str(track_path),
            "commercial_ok": song.commercial_ok,
            "review_status": row.get("review_status"),
        })
        previous_song = song

    # Add one final sign-off after the last track using the same host engine.
    close_ctx = RadioContext(
        station_id="KJAI-404",
        previous_song=previous_song,
        next_song=None,
        game_time=context.get("game_time"),
        location=context.get("location"),
        weather=context.get("weather"),
        recent_event="station sign-off",
        player_state=context.get("player_state"),
        listen_minutes=context.get("listen_minutes"),
        session_id=context.get("session_id","private-demo"),
    )
    close_break = generate_break(close_ctx, memory=memory)
    close_path = breaks_dir / "break-close.wav"
    close_wav, close_meta = host_segment(
        runtime, close_break.text, voice, 48000, close_path
    )
    rendered_breaks.append({
        "id": "CLOSE",
        "path": str(close_path),
        "after_track_id": rendered_songs[-1]["id"],
        "before_track_id": None,
        "text": close_break.text,
        "memory_key": close_break.memory_key,
        "voice_meta": close_meta,
    })

    show_path = out / "KJAI_404_PRIVATE_BROADCAST.wav"
    manifest_path = out / "show-manifest.json"
    cue_path = out / "show-cue-sheet.json"
    broadcast = assemble_broadcast(
        songs=rendered_songs,
        dj_breaks=rendered_breaks,
        out_path=show_path,
        manifest_path=manifest_path,
        cue_path=cue_path,
        profile=PRODUCER_V2,
        insert_sting_before_track_ids={
            row["id"] for row in tracks
            if row.get("identity_mode") == "deliberately_synthetic"
        },
        station_name="KJAI 404",
        title="Signal Found",
    )

    # Carry station-generation evidence into the broadcast provenance.
    broadcast["voice_engine"] = runtime.engine
    broadcast["watermarked"] = runtime.watermarked
    broadcast["private_unwatermarked"] = runtime.private_unwatermarked
    broadcast["music_review_required"] = any(
        not row.get("commercial_ok") for row in tracks
    )
    broadcast["release_status"] = (
        "PRIVATE_QA_ONLY"
        if runtime.private_unwatermarked or broadcast["music_review_required"]
        else "PRIVATE_RELEASE_CANDIDATE"
    )
    manifest_path.write_text(json.dumps(broadcast, indent=2), encoding="utf-8")

    print("\nKJAI 404 private show assembled.")
    print(show_path)
    print("Release status:", broadcast["release_status"])
    print("Broadcast engine: KJAI Broadcast Engine v1 / Producer Mix v2")
    print("No public release has occurred.")


if __name__ == "__main__":
    main()
