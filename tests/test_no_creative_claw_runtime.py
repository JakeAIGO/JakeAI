from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = "cdn.creativeclaw.co"
ALLOWED = {
    "jakeai_media_gateway.py",  # audit-only migration source URLs
}

def test_no_creative_claw_cdn_runtime_dependencies():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED or rel.startswith(".git/"):
            continue
        if path.suffix.lower() not in {".py",".html",".js",".json",".md",".txt",".css"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if FORBIDDEN in text:
            offenders.append(rel)
    assert not offenders, "Creative Claw CDN runtime references remain: " + ", ".join(offenders)
