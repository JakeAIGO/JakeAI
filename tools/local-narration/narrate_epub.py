#!/usr/bin/env python3
"""JakeAI Editions local narration runner.

Generates a private audiobook from a JakeAI pre-release EPUB using Chatterbox Nano.
The literary text is never rewritten: every spoken TTS input is an exact UTF-8
slice of OEBPS/source/canonical.txt embedded in the verified EPUB.

The private reference voice file is never uploaded by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import torch
import torchaudio as ta
from jakeai_local_voice import load_runtime, normalize_audio, synthesize

MAX_CHARS = 900
SILENCE_MS = 220

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_verified_source(epub_path: Path):
    with zipfile.ZipFile(epub_path, "r") as z:
        fidelity = json.loads(z.read("META-INF/jakeai-fidelity.json").decode("utf-8"))
        source = z.read("OEBPS/source/canonical.txt")
    expected = fidelity["canonical_sha256"]
    actual = sha256(source)
    if actual != expected:
        raise RuntimeError(f"Canonical source hash mismatch: expected {expected}, got {actual}")
    source.decode("utf-8", errors="strict")
    return source, fidelity

def utf8_byte_len(text: str) -> int:
    return len(text.encode("utf-8"))

def chunk_exact(source: bytes, max_chars: int = MAX_CHARS):
    """Create contiguous exact source slices, preferring paragraph/sentence boundaries."""
    text = source.decode("utf-8", errors="strict")
    chunks = []
    char_start = 0
    byte_start = 0
    n = len(text)

    while char_start < n:
        hard_end = min(n, char_start + max_chars)
        end = hard_end

        if hard_end < n:
            window = text[char_start:hard_end]
            # Prefer paragraph, then sentence-ish punctuation, then whitespace.
            candidates = []
            for pat in ("\r\n\r\n", "\n\n", ". ", "? ", "! ", "; ", ": ", "\r\n", "\n", " "):
                pos = window.rfind(pat)
                if pos >= max_chars // 2:
                    candidates.append((pos + len(pat), pat))
            if candidates:
                end = char_start + max(candidates, key=lambda x: x[0])[0]

        piece = text[char_start:end]
        raw = piece.encode("utf-8")
        byte_end = byte_start + len(raw)
        chunks.append({
            "index": len(chunks),
            "char_start": char_start,
            "char_end": end,
            "byte_start": byte_start,
            "byte_end": byte_end,
            "bytes": len(raw),
            "chars": len(piece),
            "sha256": sha256(raw),
            "text": piece,
            "spoken": bool(piece.strip()),
        })
        char_start = end
        byte_start = byte_end

    rebuilt = b"".join(c["text"].encode("utf-8") for c in chunks)
    if rebuilt != source:
        raise RuntimeError("Chunker changed canonical source")
    return chunks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub", required=True, help="JakeAI verified pre-release EPUB")
    ap.add_argument("--voice", required=True, help="Private WAV reference clip")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--device", default="auto", choices=["auto","cpu","cuda"])
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS)
    args = ap.parse_args()

    epub = Path(args.epub).expanduser().resolve()
    voice = Path(args.voice).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    chunk_dir = out / "chunks"
    chunk_dir.mkdir(exist_ok=True)

    if not epub.exists():
        raise FileNotFoundError(epub)
    if not voice.exists():
        raise FileNotFoundError(voice)

    source, fidelity = load_verified_source(epub)
    chunks = chunk_exact(source, args.max_chars)
    print(f"Canonical SHA-256: {fidelity['canonical_sha256']}")
    print(f"Canonical bytes: {len(source):,}")
    print(f"Exact chunks: {len(chunks):,}")
    print("Loading JakeAI Media Gateway local voice adapter...")
    runtime = load_runtime(args.device, allow_private_unwatermarked=True)
    print(f"Engine: {runtime.engine}")
    print(f"Device: {runtime.device}")
    print(f"Watermarked: {runtime.watermarked}")

    rendered = []
    manifest_chunks = []
    for c in chunks:
        idx = c["index"]
        path = chunk_dir / f"{idx:05d}.wav"

        if not c["spoken"]:
            manifest_chunks.append({k:v for k,v in c.items() if k!="text"} | {"audio":None, "status":"whitespace"})
            continue

        print(f"[{idx+1}/{len(chunks)}] {c['chars']} chars")
        wav, sample_rate, seed = synthesize(
            runtime,
            c["text"],
            voice,
            namespace=f"JakeAI-Editions:{fidelity['canonical_sha256']}:{idx}",
            verify_words=True,
        )
        wav, level_qa = normalize_audio(wav)
        ta.save(str(path), wav.cpu(), sample_rate)
        audio_bytes = path.read_bytes()
        rendered.append((idx, path))
        manifest_chunks.append({
            **{k:v for k,v in c.items() if k!="text"},
            "audio": str(path.name),
            "audio_sha256": sha256(audio_bytes),
            "seed": seed,
            "level_qa": level_qa,
            "status":"generated",
        })

    if not rendered:
        raise RuntimeError("No spoken audio generated")

    # Concatenate generated WAV chunks with short silence between them.
    tracks = []
    for _, p in rendered:
        wav, sr = ta.load(str(p))
        if sr != sample_rate:
            raise RuntimeError(f"Unexpected sample rate in {p}: {sr}")
        tracks.append(wav)
        silence = torch.zeros((wav.shape[0], int(sample_rate * SILENCE_MS / 1000)), dtype=wav.dtype)
        tracks.append(silence)
    full = torch.cat(tracks[:-1], dim=1)
    full_path = out / "audiobook.wav"
    ta.save(str(full_path), full, sample_rate)

    manifest = {
        "engine":runtime.engine,
        "engine_family":"JakeAI Media Gateway / local Chatterbox",
        "generation_mode":"self_hosted_zero_shot_voice_reference",
        "commercial_model_license":"MIT",
        "watermark_expected":"PerTh",
        "watermarked":runtime.watermarked,
        "private_unwatermarked":runtime.private_unwatermarked,
        "canonical_sha256":fidelity["canonical_sha256"],
        "canonical_bytes":len(source),
        "text_policy":"Every spoken TTS input is an exact UTF-8 slice of the immutable canonical source.",
        "text_rewrite_allowed":False,
        "reference_voice_path":str(voice),
        "reference_voice_public":False,
        "device":runtime.device,
        "sample_rate":sample_rate,
        "silence_between_chunks_ms":SILENCE_MS,
        "chunk_count":len(chunks),
        "generated_chunk_count":len(rendered),
        "chunks":manifest_chunks,
        "full_audio":str(full_path),
        "full_audio_sha256":sha256(full_path.read_bytes()),
        "release_status":"PRIVATE_AUDIO_QA_REQUIRED",
        "human_release_approved":False,
    }
    (out / "narration-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nREADY FOR AUDIO QA: {full_path}")
    print("Public release remains disabled.")

if __name__ == "__main__":
    main()
