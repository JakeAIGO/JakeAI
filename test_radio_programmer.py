from radio.programmer import build_rotation

def test_rotation_avoids_same_artist_back_to_back_and_spaces_robotic_act():
    rows = [
        {"id":"a1","artist_id":"country","genre":"country","instrumental":False,"identity_mode":"prompt_locked_recurring_identity"},
        {"id":"a2","artist_id":"country","genre":"country","instrumental":False,"identity_mode":"prompt_locked_recurring_identity"},
        {"id":"b1","artist_id":"rock","genre":"rock","instrumental":False,"identity_mode":"prompt_locked_recurring_identity"},
        {"id":"c1","artist_id":"robot","genre":"robotic electro","instrumental":False,"identity_mode":"deliberately_synthetic"},
        {"id":"d1","artist_id":"alt","genre":"alt","instrumental":False,"identity_mode":"prompt_locked_recurring_identity"},
        {"id":"e1","artist_id":"inst","genre":"electronic","instrumental":True,"identity_mode":"instrumental"},
    ]
    out = build_rotation(rows)
    assert len(out) == len(rows)
    for x, y in zip(out, out[1:]):
        assert x["artist_id"] != y["artist_id"]
    robot_positions = [i for i,x in enumerate(out) if x["identity_mode"]=="deliberately_synthetic"]
    assert len(robot_positions) == 1
