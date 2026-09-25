import json
from pathlib import Path

def test_kjai_music_prompts_are_instrumental_and_avoid_named_artist_imitation():
    rows=json.loads(Path("radio/music_prompts_kjai404.json").read_text(encoding="utf-8"))
    assert len(rows) >= 8
    for row in rows:
        prompt=row["prompt"].lower()
        assert "instrumental" in prompt
        assert "no vocals" in prompt
        assert "named-artist" in prompt or "named artist" in prompt
        assert row["artist"] == "JakeAI House Band"

def test_demo_context_is_not_release_metadata():
    row=json.loads(Path("radio/demo_context.json").read_text(encoding="utf-8"))
    assert row["session_id"].startswith("KJAI-DEMO")
