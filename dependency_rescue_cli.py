"""Safe local CLI for JakeAI Dependency Rescue v1.

No archives, symlinks, binaries, network access, or production execution.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dependency_rescue import scan_files
from dependency_rescue_report import render_markdown

MAX_FILE_BYTES = 1_000_000
MAX_FILES = 100
ALLOWED_SUFFIXES = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".java", ".cs", ".rb", ".php", ".go", ".rs", ".sh",
    ".ps1", ".tf", ".tfvars", ".xml", ".properties", ".env.example"
}

class IntakeError(ValueError):
    pass

def read_safe_text(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        raise IntakeError(f"symlink rejected: {path}")
    if not path.is_file():
        raise IntakeError(f"not a regular file: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise IntakeError(f"file exceeds {MAX_FILE_BYTES} byte limit: {path}")
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES and path.name != ".env.example":
        raise IntakeError(f"unsupported file type: {path}")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise IntakeError(f"binary content rejected: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntakeError(f"non-UTF-8 content rejected: {path}") from exc
    return str(path), text

def collect(paths: list[str]) -> list[tuple[str, str]]:
    if len(paths) > MAX_FILES:
        raise IntakeError(f"too many files; maximum is {MAX_FILES}")
    return [read_safe_text(Path(p)) for p in paths]

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JakeAI Dependency Rescue v1 — pre-release local scanner")
    parser.add_argument("files", nargs="+", help="Redacted UTF-8 text/config/code files only")
    parser.add_argument("--report-id", default="LOCAL-PREVIEW")
    args = parser.parse_args(argv)
    try:
        artifacts = collect(args.files)
    except IntakeError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    result = scan_files(artifacts)
    print(render_markdown(result, args.report_id))
    return 3 if result.get("status") == "BLOCKED_SECRET_DETECTED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
