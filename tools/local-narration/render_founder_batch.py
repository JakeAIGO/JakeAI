#!/usr/bin/env python3
"""JakeAI Editions founder-voice batch renderer.

Runs Founder Narrator v1 over every JakeAI release-ready EPUB in a folder.
It never publishes, uploads, or creates commerce. Finished books are skipped;
partial books resume through founder_narrator_v1.py.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--epub-dir", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--device", default="auto", choices=["auto","cpu","cuda"])
    ap.add_argument("--private-unwatermarked", action="store_true")
    args=ap.parse_args()

    root=Path(__file__).resolve().parent
    narrator=root/"founder_narrator_v1.py"
    epub_dir=Path(args.epub_dir).expanduser().resolve()
    voice=Path(args.voice).expanduser().resolve()
    out_dir=Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True,exist_ok=True)

    if not narrator.exists():
        raise SystemExit("Founder Narrator v1 is missing")
    if not voice.exists():
        raise SystemExit(f"Founder voice reference not found: {voice}")
    epubs=sorted(epub_dir.glob("JAE-*.epub"))
    if not epubs:
        raise SystemExit(f"No JAE-*.epub release candidates found in {epub_dir}")

    results=[]
    print(f"JAKEAI FOUNDER NARRATION BATCH · {len(epubs)} BOOK(S)")
    print("Private local production only. Nothing is uploaded or published.\n")

    for i,epub in enumerate(epubs,1):
        book_out=out_dir/epub.stem
        manifest=book_out/"founder-narration-manifest.json"
        if manifest.exists():
            try:
                state=json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                state={}
            if state.get("completed_at") and (book_out/"FounderNarration_Master.wav").exists():
                print(f"[{i}/{len(epubs)}] SKIP complete · {epub.stem}")
                results.append({"book":epub.stem,"status":"already_complete"})
                continue

        print(f"\n[{i}/{len(epubs)}] RENDER · {epub.stem}")
        cmd=[
            sys.executable,str(narrator),
            "--epub",str(epub),
            "--voice",str(voice),
            "--out",str(book_out),
            "--device",args.device,
        ]
        if args.private_unwatermarked:
            cmd.append("--private-unwatermarked")
        started=time.time()
        try:
            subprocess.run(cmd,check=True)
            results.append({"book":epub.stem,"status":"complete","seconds":round(time.time()-started,1)})
        except subprocess.CalledProcessError as exc:
            results.append({"book":epub.stem,"status":"failed","returncode":exc.returncode})
            print(f"FAILED · {epub.stem} · continuing with next book")

    summary={
        "format":"JAKEAI_FOUNDER_BATCH_V1",
        "voice_reference":str(voice),
        "epub_dir":str(epub_dir),
        "out_dir":str(out_dir),
        "books":results,
        "public_release":False,
        "commerce_changed":False,
    }
    summary_path=out_dir/"founder-batch-summary.json"
    summary_path.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    complete=sum(x["status"] in {"complete","already_complete"} for x in results)
    failed=sum(x["status"]=="failed" for x in results)
    print("\nBATCH PASS COMPLETE")
    print(f"Ready/complete: {complete} · Failed: {failed}")
    print(f"Summary: {summary_path}")
    print("No public release has occurred.")


if __name__=="__main__":
    main()
