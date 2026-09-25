import json
from pathlib import Path

def test_artist_roster_keeps_founder_voice_out_of_songs():
    roster=json.loads(Path("radio/artist_roster.json").read_text(encoding="utf-8"))
    ids=set()
    names=set()
    for artist in roster["artists"]:
        assert artist["id"] not in ids
        assert artist["name"] not in names
        ids.add(artist["id"])
        names.add(artist["name"])
        blob=json.dumps(artist).lower()
        if artist["type"] != "fictional_instrumental_project":
            assert "founder voice" in blob or "use founder voice" in blob
        assert "imitate any named" in blob or artist["type"] in {"fictional_robotic_act","fictional_instrumental_project"}

def test_vocal_sampler_uses_fictional_roster_only():
    roster=json.loads(Path("radio/artist_roster.json").read_text(encoding="utf-8"))
    artist_ids={a["id"] for a in roster["artists"]}
    rows=json.loads(Path("radio/vocal_prompts_kjai404.json").read_text(encoding="utf-8"))
    assert len(rows) >= 5
    assert len({r["artist_id"] for r in rows}) >= 5
    for row in rows:
        assert row["artist_id"] in artist_ids
        assert row["lyrics"].strip()
        prompt=row["prompt"].lower()
        assert "no imitation" in prompt
        assert "founder" not in prompt

def test_station_rotation_and_voice_separation():
    station=json.loads(Path("radio/stations/kjai404.json").read_text(encoding="utf-8"))
    policy=station["music_policy"]
    assert policy["founder_voice_in_songs"] is False
    assert policy["recurring_fictional_performers"] is True
    assert policy["rotation_rules"]["same_artist_back_to_back"] is False
