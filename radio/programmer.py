from __future__ import annotations

from collections import deque


def build_rotation(rows: list[dict], max_tracks: int | None = None) -> list[dict]:
    """Deterministically favor variety in artist, genre and vocal texture."""
    remaining = list(rows)
    out: list[dict] = []
    recent_artists = deque(maxlen=5)
    last_genre = None
    last_instrumental = None
    robotic_last_index = -999

    def score(row: dict) -> tuple[int, str]:
        nonlocal robotic_last_index, last_genre, last_instrumental
        artist = row.get("artist_id") or row.get("artist") or ""
        genre = row.get("genre") or ""
        instrumental = bool(row.get("instrumental", False))
        robotic = row.get("identity_mode") == "deliberately_synthetic"
        s = 0
        if out and artist == (out[-1].get("artist_id") or out[-1].get("artist")):
            s -= 1000
        if artist in recent_artists:
            s -= 30
        if genre != last_genre:
            s += 18
        if last_instrumental is not None and instrumental != last_instrumental:
            s += 12
        if robotic:
            s += 8 if len(out) - robotic_last_index >= 3 else -120
        return (s, str(row.get("id", "")))

    while remaining and (max_tracks is None or len(out) < max_tracks):
        chosen = max(remaining, key=score)
        remaining.remove(chosen)
        out.append(chosen)
        recent_artists.append(chosen.get("artist_id") or chosen.get("artist") or "")
        last_genre = chosen.get("genre") or ""
        last_instrumental = bool(chosen.get("instrumental", False))
        if chosen.get("identity_mode") == "deliberately_synthetic":
            robotic_last_index = len(out) - 1
    return out
