from radio_engine import RadioContext, RadioMemory, Song, generate_break, station_manifest

def songs():
    return (
        Song("a","Midnight Exit","JakeAI House Band","synth-rock"),
        Song("b","Parking Lot Astronomy","JakeAI House Band","indie-electronic"),
    )

def test_station_voice_bans():
    m=station_manifest()
    assert set(m["voice_restrictions"]) == {"advertising","impersonation","political","sexual"}
    assert m["commercials_in_founder_voice"] is False

def test_break_is_contextual_and_not_public(tmp_path):
    a,b=songs()
    mem=RadioMemory(str(tmp_path/"radio.db"))
    ctx=RadioContext("KJAI-404",a,b,location="downtown",recent_event="heavy traffic",session_id="x")
    out=generate_break(ctx,mem,seed=1)
    assert b.title in out.text
    assert out.publishable is False
    assert out.public_release_approved is False
    assert len(out.text.split()) <= 72

def test_memory_changes_break(tmp_path):
    a,b=songs()
    mem=RadioMemory(str(tmp_path/"radio.db"))
    ctx=RadioContext("KJAI-404",a,b,location="downtown",session_id="x")
    one=generate_break(ctx,mem,seed=7)
    two=generate_break(ctx,mem,seed=8)
    assert one.text != two.text

def test_banned_context_is_suppressed(tmp_path):
    a,b=songs()
    mem=RadioMemory(str(tmp_path/"radio.db"))
    ctx=RadioContext("KJAI-404",a,b,recent_event="election campaign",player_state="politics rally",session_id="x")
    out=generate_break(ctx,mem,seed=3)
    assert "election" not in out.text.lower()
    assert "politics" not in out.text.lower()
