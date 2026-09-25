import json
from pathlib import Path

def test_six_artist_batch_is_private_and_never_uses_founder_voice_for_songs():
    data=json.loads(Path("radio/artist_song_specs_v1.json").read_text(encoding="utf-8"))
    assert data["release_state"]=="PRIVATE_GENERATION_READY"
    assert data["founder_voice_used_in_songs"] is False
    rows=data["tracks"]
    assert len(rows)==6
    assert len({r["artist_id"] for r in rows})==6
    assert any(r["genre"]=="country-rock" for r in rows)
    assert any(r["genre"]=="hard rock" for r in rows)
    assert any(r["identity_mode"]=="deliberately_synthetic" for r in json.loads(Path("radio/artist_tracks_v1.json").read_text(encoding="utf-8"))["tracks"])
    for row in rows:
        assert "founder voice" not in row["prompt"].lower()
        assert "named artist imitation" in row["prompt"].lower() or "named band" in row["prompt"].lower() or "known robot" in row["prompt"].lower()
