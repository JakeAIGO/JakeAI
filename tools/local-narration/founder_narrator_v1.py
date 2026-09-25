#!/usr/bin/env python3
"""JakeAI Editions Founder Narrator v1.

Resumable whole-book local narration from a verified JakeAI EPUB.

Hard rules:
- canonical source SHA-256 must pass;
- EPUB section XHTML must round-trip to exact canonical bytes;
- each spoken chunk is an exact contiguous source slice;
- no word substitution/addition/deletion through Chatterbox normalization;
- private QA may explicitly run unwatermarked;
- release-candidate completion requires working Perth watermarking.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import zipfile
from pathlib import Path

import torch
import torchaudio as ta

from jakeai_local_voice import load_runtime, normalize_audio, save_wav, synthesize

MAX_CHARS = 850
CHUNK_SILENCE_MS = 150


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_epub(epub: Path):
    with zipfile.ZipFile(epub, "r") as z:
        fidelity = json.loads(z.read("META-INF/jakeai-fidelity.json").decode("utf-8"))
        source = z.read("OEBPS/source/canonical.txt")
        names = set(z.namelist())
        section_names = []
        if "OEBPS/front.xhtml" in names:
            section_names.append("OEBPS/front.xhtml")
        section_names += sorted(
            n for n in names
            if re.fullmatch(r"OEBPS/section-\d+\.xhtml", n)
        )
        if not section_names:
            raise RuntimeError("JakeAI EPUB contains no exact-text sections")

        sections = []
        rebuilt = bytearray()
        for name in section_names:
            doc = z.read(name).decode("utf-8")
            marker = '<pre class="book">'
            a = doc.index(marker) + len(marker)
            b = doc.index("</pre>", a)
            raw = html.unescape(doc[a:b]).encode("utf-8")
            sections.append((name, raw))
            rebuilt.extend(raw)

    expected = fidelity["canonical_sha256"]
    if sha256(source) != expected:
        raise RuntimeError("Canonical text hash failed")
    if bytes(rebuilt) != source or sha256(bytes(rebuilt)) != expected:
        raise RuntimeError("EPUB sections do not reconstruct exact canonical text")
    source.decode("utf-8", errors="strict")
    return fidelity, source, sections


def exact_chunks(raw: bytes, max_chars: int):
    text = raw.decode("utf-8", errors="strict")
    out = []
    c0 = 0
    b0 = 0
    while c0 < len(text):
        hard = min(len(text), c0 + max_chars)
        end = hard
        if hard < len(text):
            window = text[c0:hard]
            choices = []
            for token in ("\r\n\r\n", "\n\n", ". ", "? ", "! ", "; ", ": ", "\r\n", "\n", " "):
                pos = window.rfind(token)
                if pos >= max_chars // 2:
                    choices.append(pos + len(token))
            if choices:
                end = c0 + max(choices)
        piece = text[c0:end]
        data = piece.encode("utf-8")
        out.append({
            "index": len(out),
            "char_start": c0,
            "char_end": end,
            "byte_start": b0,
            "byte_end": b0 + len(data),
            "bytes": len(data),
            "chars": len(piece),
            "sha256": sha256(data),
            "text": piece,
            "spoken": bool(piece.strip()),
        })
        c0 = end
        b0 += len(data)

    if b"".join(x["text"].encode("utf-8") for x in out) != raw:
        raise RuntimeError("Narration chunking changed source bytes")
    return out


def concat_wavs(paths: list[Path], out: Path, silence_ms: int):
    tracks = []
    sr = None
    for p in paths:
        wav, this_sr = ta.load(str(p))
        sr = this_sr if sr is None else sr
        if this_sr != sr:
            raise RuntimeError("Chunk sample-rate mismatch")
        tracks.append(wav)
        if silence_ms:
            tracks.append(torch.zeros(
                (wav.shape[0], int(sr * silence_ms / 1000)),
                dtype=wav.dtype,
            ))
    if not tracks:
        return None
    full = torch.cat(tracks[:-1] if silence_ms else tracks, dim=1)
    full, qa = normalize_audio(full)
    meta = save_wav(out, full, sr)
    meta.update(qa)
    meta["seconds"] = full.shape[-1] / sr
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="auto", choices=["auto","cpu","cuda"])
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS)
    ap.add_argument(
        "--private-unwatermarked",
        action="store_true",
        help="Allow unwatermarked output for PRIVATE QA only. Never qualifies for release.",
    )
    args = ap.parse_args()

    epub = Path(args.epub).expanduser().resolve()
    voice = Path(args.voice).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    chunks_dir = out / "chunks"
    chapters_dir = out / "chapters"
    chunks_dir.mkdir(exist_ok=True)
    chapters_dir.mkdir(exist_ok=True)

    fidelity, source, sections = extract_epub(epub)
    runtime = load_runtime(
        args.device,
        allow_private_unwatermarked=args.private_unwatermarked,
    )

    state_path = out / "founder-narration-manifest.json"
    state = {
        "format": "JAKEAI_FOUNDER_NARRATION_V1",
        "engine": runtime.engine,
        "device": runtime.device,
        "watermarked": runtime.watermarked,
        "private_unwatermarked": runtime.private_unwatermarked,
        "canonical_sha256": fidelity["canonical_sha256"],
        "canonical_bytes": len(source),
        "text_policy": "immutable_exact_source_slices",
        "text_rewrite_allowed": False,
        "reference_voice_public": False,
        "epub": str(epub),
        "voice": str(voice),
        "started_at": time.time(),
        "sections": [],
        "release_status": "PRIVATE_AUDIO_QA_REQUIRED",
        "human_release_approved": False,
    }

    total_chunks = sum(len(exact_chunks(raw, args.max_chars)) for _, raw in sections)
    done = 0

    for sidx, (section_name, raw) in enumerate(sections):
        chunks = exact_chunks(raw, args.max_chars)
        chapter_paths = []
        sec = {
            "index": sidx,
            "source_name": section_name,
            "source_sha256": sha256(raw),
            "source_bytes": len(raw),
            "chunks": [],
        }

        for c in chunks:
            done += 1
            cpath = chunks_dir / f"s{sidx:03d}-c{c['index']:04d}.wav"

            if not c["spoken"]:
                sec["chunks"].append({
                    **{k:v for k,v in c.items() if k != "text"},
                    "audio": None,
                    "status": "whitespace",
                })
                continue

            existing_ok = False
            if cpath.exists() and cpath.stat().st_size > 1024:
                existing_ok = True

            if not existing_ok:
                print(f"[{done}/{total_chunks}] section {sidx} chunk {c['index']} — {c['chars']} chars")
                wav, sr, seed = synthesize(
                    runtime,
                    c["text"],
                    voice,
                    namespace=f"{fidelity['canonical_sha256']}:{sidx}:{c['index']}",
                    verify_words=True,
                )
                wav, qa = normalize_audio(wav)
                audio = save_wav(cpath, wav, sr)
            else:
                wav, sr = ta.load(str(cpath))
                wav, qa = normalize_audio(wav)
                audio = {
                    "path": str(cpath),
                    "bytes": cpath.stat().st_size,
                    "sha256": sha256(cpath.read_bytes()),
                }
                seed = None

            chapter_paths.append(cpath)
            sec["chunks"].append({
                **{k:v for k,v in c.items() if k != "text"},
                "audio": audio,
                "seed": seed,
                "qa": qa,
                "status": "generated",
            })
            state_path.write_text(json.dumps(state | {"current_section": sec}, indent=2), encoding="utf-8")

        chapter_path = chapters_dir / f"section-{sidx:03d}.wav"
        sec["chapter_audio"] = concat_wavs(chapter_paths, chapter_path, CHUNK_SILENCE_MS)
        state["sections"].append(sec)
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    state["completed_at"] = time.time()
    state["generated_sections"] = len(state["sections"])
    state["release_status"] = (
        "PRIVATE_AUDIO_QA_REQUIRED"
        if runtime.watermarked
        else "PRIVATE_UNWATERMARKED_QA_ONLY"
    )
    state["release_eligible_after_audio_qa"] = bool(runtime.watermarked)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print("\nFOUNDER NARRATION PASS COMPLETE")
    print(f"Sections: {len(state['sections'])}")
    print(f"Manifest: {state_path}")
    print(f"Status: {state['release_status']}")
    print("No public release has occurred.")


if __name__ == "__main__":
    main()
