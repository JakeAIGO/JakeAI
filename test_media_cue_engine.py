import json
from pathlib import Path
from media_cue_engine import MediaProgram, active_cues, public_release_blockers

def load(path):
    return MediaProgram.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

def test_gridworks_program_is_private_and_timed():
    p=load("media-programs/gridworks_sizzle_v1_6.json")
    assert p.consumer=="documentary"
    assert p.private is True
    assert p.duration_seconds > 90
    assert active_cues(p,28.1)
    assert "human_release_not_approved" in public_release_blockers(p)

def test_game_program_keeps_founder_voice_in_narrator_dj_role():
    p=load("media-programs/game_dynamic_media_example.json")
    assert p.consumer=="game"
    assert p.founder_voice_allowed is True
    assert p.founder_voice_role=="dj_or_narrator_only"
    voice=[c for c in p.cues if c.kind=="voice"]
    assert voice
    assert all("founder_voice" in c.tags for c in voice)
