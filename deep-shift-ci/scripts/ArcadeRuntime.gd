extends Node

signal arcade_state_changed(state: String)
signal credit_changed(credits: int)
signal run_requested
signal operator_mode_changed(enabled: bool)

const SAVE_PATH := "user://arcade_runtime.cfg"
const STATES := ["BOOT", "ATTRACT", "CREDIT", "READY", "PLAY", "BOSS", "GAME_OVER", "INITIALS"]

var state := "BOOT"
var credits := 0
var free_play := true
var credits_per_game := 1
var operator_mode := false
var attract_audio := true
var master_volume := 0.85
var difficulty := 1
var high_scores: Array = []

func _ready() -> void:
    load_settings()
    transition_to("ATTRACT")

func transition_to(next_state: String) -> void:
    if not STATES.has(next_state):
        push_error("Invalid arcade state: %s" % next_state)
        return
    state = next_state
    arcade_state_changed.emit(state)

func add_credit(amount: int = 1) -> void:
    credits = max(0, credits + amount)
    credit_changed.emit(credits)
    if state == "ATTRACT" and credits > 0:
        transition_to("CREDIT")

func can_start_run() -> bool:
    return free_play or credits >= credits_per_game

func request_start() -> bool:
    if operator_mode or not can_start_run():
        return false
    if not free_play:
        credits -= credits_per_game
        credit_changed.emit(credits)
    transition_to("READY")
    run_requested.emit()
    return true

func begin_play() -> void:
    transition_to("PLAY")

func begin_boss() -> void:
    transition_to("BOSS")

func end_run(score: int, metadata: Dictionary = {}) -> void:
    high_scores.append({
        "score": score,
        "initials": "---",
        "metadata": metadata.duplicate(true),
        "timestamp": Time.get_unix_time_from_system()
    })
    high_scores.sort_custom(func(a, b): return int(a.score) > int(b.score))
    if high_scores.size() > 10:
        high_scores.resize(10)
    save_settings()
    transition_to("GAME_OVER")

func submit_initials(initials: String) -> void:
    var cleaned := initials.strip_edges().to_upper().substr(0, 3)
    if cleaned.is_empty():
        cleaned = "---"
    for entry in high_scores:
        if String(entry.initials) == "---":
            entry.initials = cleaned
            break
    save_settings()
    transition_to("ATTRACT")

func set_operator_mode(enabled: bool) -> void:
    operator_mode = enabled
    operator_mode_changed.emit(operator_mode)

func reset_high_scores() -> void:
    high_scores.clear()
    save_settings()

func save_settings() -> void:
    var cfg := ConfigFile.new()
    cfg.set_value("operator", "free_play", free_play)
    cfg.set_value("operator", "credits_per_game", credits_per_game)
    cfg.set_value("operator", "attract_audio", attract_audio)
    cfg.set_value("operator", "master_volume", master_volume)
    cfg.set_value("operator", "difficulty", difficulty)
    cfg.set_value("scores", "top10", high_scores)
    var err := cfg.save(SAVE_PATH)
    if err != OK:
        push_error("Unable to save arcade runtime config: %s" % err)

func load_settings() -> void:
    var cfg := ConfigFile.new()
    if cfg.load(SAVE_PATH) != OK:
        return
    free_play = bool(cfg.get_value("operator", "free_play", free_play))
    credits_per_game = max(1, int(cfg.get_value("operator", "credits_per_game", credits_per_game)))
    attract_audio = bool(cfg.get_value("operator", "attract_audio", attract_audio))
    master_volume = clamp(float(cfg.get_value("operator", "master_volume", master_volume)), 0.0, 1.0)
    difficulty = clamp(int(cfg.get_value("operator", "difficulty", difficulty)), 0, 2)
    high_scores = cfg.get_value("scores", "top10", [])
