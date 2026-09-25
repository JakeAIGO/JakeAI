"""KJAI Broadcast Engine v1.

Reusable private-production mixer promoted from Broadcast 001 Producer Mix v2.

Goals:
- preserve original songs and DJ wording;
- keep founder voice DJ/narrator-only;
- normalize music and DJ independently;
- trim sustained dead tails, not musical endings;
- overlap DJ/music for radio-style segues;
- generate cue/provenance manifests;
- never imply public/commercial release.

This module is for local production. It is intentionally not imported by the
Railway web runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import math
from typing import Iterable

import numpy as np
import torch
import torchaudio as ta


@dataclass(frozen=True)
class BroadcastMixProfile:
    sample_rate: int = 48000
    music_rms_db: float = -18.0
    dj_rms_db: float = -17.0
    final_rms_db: float = -17.4
    peak_db: float = -0.8
    dj_music_overlap_seconds: float = 1.00
    song_dj_overlap_seconds: float = 0.95
    closing_overlap_seconds: float = 0.55
    sting_overlap_seconds: float = 0.45
    silence_threshold_db: float = -38.0
    preserve_song_tail_seconds: float = 0.35
    dj_silence_threshold_db: float = -44.0
    dj_keep_lead_seconds: float = 0.04
    dj_keep_tail_seconds: float = 0.08


PRODUCER_V2 = BroadcastMixProfile()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_stereo(path: Path, target_sr: int) -> torch.Tensor:
    wav, sr = ta.load(str(path))
    wav = wav.float()
    if wav.dim() == 1:
        wav = wav.unsqueeze(0)
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    elif wav.shape[0] > 2:
        wav = wav[:2]
    if sr != target_sr:
        wav = ta.functional.resample(wav, sr, target_sr)
    return wav


def normalize_rms(wav: torch.Tensor, target_db: float, peak_db: float) -> torch.Tensor:
    wav = wav.float()
    rms = torch.sqrt(torch.mean(wav * wav) + 1e-12)
    gain = (10 ** (target_db / 20.0)) / float(rms)
    wav = wav * gain
    peak = float(torch.max(torch.abs(wav)))
    limit = 10 ** (peak_db / 20.0)
    if peak > limit:
        wav = wav * (limit / peak)
    return wav


def _frame_db(wav: torch.Tensor, frame: int = 2400) -> np.ndarray:
    mono = wav.mean(0)
    n = mono.numel() // frame
    if n <= 0:
        return np.array([])
    x = mono[: n * frame].reshape(n, frame)
    rms = torch.sqrt(torch.mean(x * x, dim=1) + 1e-12)
    return (20 * torch.log10(rms + 1e-12)).cpu().numpy()


def trim_dj_edges(wav: torch.Tensor, profile: BroadcastMixProfile) -> torch.Tensor:
    db = _frame_db(wav)
    if not len(db):
        return wav
    active = np.where(db > profile.dj_silence_threshold_db)[0]
    if not len(active):
        return wav
    frame = 2400
    a = max(0, active[0] * frame - int(profile.dj_keep_lead_seconds * profile.sample_rate))
    b = min(
        wav.shape[1],
        (active[-1] + 1) * frame + int(profile.dj_keep_tail_seconds * profile.sample_rate),
    )
    return wav[:, a:b]


def trim_song_dead_tail(wav: torch.Tensor, profile: BroadcastMixProfile) -> tuple[torch.Tensor, float]:
    """Trim only sustained dead tail after the last active musical frame."""
    db = _frame_db(wav)
    if not len(db):
        return wav, 0.0
    active = np.where(db > profile.silence_threshold_db)[0]
    if not len(active):
        return wav, 0.0
    frame = 2400
    last = (active[-1] + 1) * frame
    cut = min(wav.shape[1], last + int(profile.preserve_song_tail_seconds * profile.sample_rate))
    removed = max(0.0, (wav.shape[1] - cut) / profile.sample_rate)
    return wav[:, :cut], removed


def crossfade(a: torch.Tensor | None, b: torch.Tensor, sr: int, seconds: float) -> torch.Tensor:
    if a is None:
        return b
    n = min(int(sr * seconds), a.shape[1], b.shape[1])
    if n <= 0:
        return torch.cat([a, b], dim=1)
    t = torch.linspace(0, 1, n, dtype=a.dtype, device=a.device).view(1, -1)
    mix = a[:, -n:] * (1 - t) + b[:, :n] * t
    return torch.cat([a[:, :-n], mix, b[:, n:]], dim=1)


def station_sting(sr: int = 48000) -> torch.Tensor:
    """Original synthesized KJAI sting. No sampled audio."""
    dur = 1.35
    n = int(sr * dur)
    t = torch.arange(n) / sr
    f = 190 + 820 * (t / dur) ** 1.7
    phase = 2 * math.pi * torch.cumsum(f / sr, 0)
    sweep = torch.sin(phase) * torch.exp(-2.0 * t)
    chord = (
        torch.sin(2 * math.pi * 220 * t)
        + 0.6 * torch.sin(2 * math.pi * 330 * t)
        + 0.35 * torch.sin(2 * math.pi * 440 * t)
    )
    env = torch.clamp((t - 0.42) / 0.22, 0, 1) * torch.exp(
        -1.4 * torch.clamp(t - 0.75, min=0)
    )
    sig = 0.26 * sweep + 0.10 * chord * env
    sig = sig / (torch.max(torch.abs(sig)) + 1e-12) * 0.52
    return sig.unsqueeze(0).repeat(2, 1)


def assemble_broadcast(
    *,
    songs: list[dict],
    dj_breaks: list[dict],
    out_path: Path,
    manifest_path: Path,
    cue_path: Path,
    profile: BroadcastMixProfile = PRODUCER_V2,
    insert_sting_before_track_ids: set[str] | None = None,
    station_name: str = "KJAI 404",
    title: str = "JakeAI Radio Private Broadcast",
) -> dict:
    """Assemble one private broadcast from pre-rendered song/DJ stems.

    songs rows require: id, title, artist, path.
    dj_breaks rows require: id, path and one of before_track_id / after_track_id,
    or id OPEN / CLOSE.
    """
    insert_sting_before_track_ids = insert_sting_before_track_ids or set()
    break_by_after = {
        row.get("after_track_id"): row
        for row in dj_breaks
        if row.get("after_track_id")
    }
    open_break = next((x for x in dj_breaks if x["id"] == "OPEN"), None)

    final = None
    cursor = 0.0
    cues = []
    transitions = []

    def add(label: str, wav: torch.Tensor, overlap: float):
        nonlocal final, cursor
        before = 0.0 if final is None else min(
            overlap, final.shape[1] / profile.sample_rate, wav.shape[1] / profile.sample_rate
        )
        start = max(0.0, cursor - before)
        cues.append({"start_seconds": round(start, 3), "label": label})
        final = crossfade(final, wav, profile.sample_rate, overlap)
        cursor = final.shape[1] / profile.sample_rate

    add(f"{station_name} sting", station_sting(profile.sample_rate), 0.0)

    if open_break:
        w = load_stereo(Path(open_break["path"]), profile.sample_rate)
        w = trim_dj_edges(w, profile)
        w = normalize_rms(w, profile.dj_rms_db, -1.0)
        add("DJ OPEN", w, 0.35)

    for song in songs:
        path = Path(song["path"]).expanduser().resolve()
        w = load_stereo(path, profile.sample_rate)
        source_seconds = w.shape[1] / profile.sample_rate
        w, removed = trim_song_dead_tail(w, profile)
        w = normalize_rms(w, profile.music_rms_db, -1.0)

        add(
            f"{song['artist']} — {song['title']}",
            w,
            profile.dj_music_overlap_seconds,
        )
        transitions.append({
            "track_id": song["id"],
            "source_duration_seconds": round(source_seconds, 3),
            "producer_duration_seconds": round(w.shape[1] / profile.sample_rate, 3),
            "dead_tail_removed_seconds": round(removed, 3),
        })

        br = break_by_after.get(song["id"])
        if not br:
            continue

        next_track_id = br.get("before_track_id")
        if next_track_id in insert_sting_before_track_ids:
            add(
                f"{station_name} sting",
                station_sting(profile.sample_rate),
                profile.sting_overlap_seconds,
            )

        bw = load_stereo(Path(br["path"]), profile.sample_rate)
        bw = trim_dj_edges(bw, profile)
        bw = normalize_rms(bw, profile.dj_rms_db, -1.0)
        overlap = (
            profile.closing_overlap_seconds
            if br["id"] == "CLOSE"
            else profile.song_dj_overlap_seconds
        )
        add(f"DJ {br['id']}", bw, overlap)

    if final is None:
        raise RuntimeError("No broadcast audio was assembled")

    final = normalize_rms(final, profile.final_rms_db, profile.peak_db)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(
        str(out_path),
        final.cpu(),
        profile.sample_rate,
        encoding="PCM_S",
        bits_per_sample=16,
    )

    manifest = {
        "engine": "KJAI Broadcast Engine v1",
        "profile": asdict(profile),
        "station": station_name,
        "title": title,
        "release_state": "PRIVATE_QA_ONLY",
        "public_release": False,
        "founder_voice_used_in_songs": False,
        "founder_voice_role": "DJ/narrator only",
        "producer_changes": [
            "trim sustained dead song tails only",
            "trim DJ leading/trailing dead air",
            "standardize independent DJ/music level targets",
            "overlap DJ/music transitions",
            "preserve song content, DJ wording and performer identities",
        ],
        "transition_report": transitions,
        "cue_sheet": cues,
        "duration_seconds": round(final.shape[1] / profile.sample_rate, 3),
        "output": str(out_path),
        "output_sha256": sha256_file(out_path),
        "songs": [
            {
                **{k: v for k, v in row.items() if k != "path"},
                "path": str(Path(row["path"]).resolve()),
                "sha256": sha256_file(Path(row["path"]).resolve()),
            }
            for row in songs
        ],
        "dj_breaks": [
            {
                **{k: v for k, v in row.items() if k != "path"},
                "path": str(Path(row["path"]).resolve()),
                "sha256": sha256_file(Path(row["path"]).resolve()),
            }
            for row in dj_breaks
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    cue_path.write_text(json.dumps(cues, indent=2), encoding="utf-8")
    return manifest
