extends Node

var failures: Array[String] = []

func _ready() -> void:
    _require_file("res://project.godot")
    _require_file("res://export_presets.cfg")
    _require_file("res://scenes/Main.tscn")
    _require_file("res://scenes/Game.tscn")
    _require_file("res://scenes/SmokeTest.tscn")
    _require_file("res://scenes/PlaytestRunner.tscn")
    _require_file("res://data/autonomous_playtester_spec.json")
    _require_file("res://data/balance_fairness_gate.json")
    _require_audio()
    if failures.is_empty():
        print("DEEP_SHIFT_RELEASE_GATE: PASS")
        get_tree().quit(0)
    for f in failures:
        push_error(f)
    print("DEEP_SHIFT_RELEASE_GATE: FAIL")
    get_tree().quit(1)

func _require_file(path: String) -> void:
    if not FileAccess.file_exists(path):
        failures.append("Missing: " + path)

func _require_audio() -> void:
    for id in ["dig","ore","pulse","charge","hurt","boss_warning","extract"]:
        _require_file("res://assets/audio/%s.wav" % id)
