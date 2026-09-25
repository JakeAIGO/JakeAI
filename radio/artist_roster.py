from __future__ import annotations

import hashlib
import json
from pathlib import Path

DEFAULT_ROSTER = Path(__file__).with_name("artist_roster.json")


def load_artist_roster(path: str | Path = DEFAULT_ROSTER) -> dict[str, dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["id"]: row for row in raw["artists"]}


def artist_generation_prompt(artist: dict, track_prompt: str) -> str:
    parts = [
        track_prompt.strip(),
        "FICTIONAL PERFORMER IDENTITY:",
        f"Name: {artist['name']}.",
        f"Voice: {artist['voice_profile']}",
        f"Core instrumentation: {artist['instrumentation']}",
        "Keep this as an original fictional performance.",
        "Do not imitate, approximate, or reference any named real performer.",
        "Do not use the JakeAI founder/DJ voice.",
    ]
    return " ".join(x for x in parts if x)


def artist_seed(artist: dict, track_id: str) -> int:
    namespace = artist.get("seed_namespace") or artist["id"]
    raw = f"{namespace}:{track_id}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16) & 0x7FFFFFFF


def artist_catalog_metadata(artist: dict) -> dict:
    return {
        "artist_id": artist["id"],
        "artist": artist["name"],
        "artist_type": artist["type"],
        "station_home": artist["station_home"],
        "genres": artist["genres"],
        "voice_identity": artist["voice_profile"],
        "identity_mode": artist["identity_mode"],
        "founder_voice_used": False,
    }
