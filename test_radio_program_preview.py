from radio_engine import _program_preview

def test_private_program_separates_founder_dj_from_song_vocals():
    data = _program_preview(12)
    assert data["founder_voice_used_in_songs"] is False
    assert data["dj_voice"] == "JakeAI Original AI Narration"
    assert data["public"] is False
    assert data["program"]
    assert len(data["program"]) <= 12
    for row in data["program"]:
        assert row["dj_voice"] == "JakeAI Original AI Narration"
        assert row["public"] is False
        assert row["artist"]
        assert row["genre"]

def test_private_program_avoids_same_artist_back_to_back():
    rows = _program_preview(12)["program"]
    for left, right in zip(rows, rows[1:]):
        assert left["artist_id"] != right["artist_id"]
