extends Node

@export var game_scene: PackedScene
var current_game: Node
var initials := ["A", "A", "A"]
var initials_index := 0
var game_over_timer := 0.0

@onready var attract := $CanvasLayer/Attract
@onready var state_label := $CanvasLayer/Attract/Center/VBox/State
@onready var score_label := $CanvasLayer/Attract/Center/VBox/Scores
@onready var operator_label := $CanvasLayer/Attract/Center/VBox/Operator
@onready var game_over := $CanvasLayer/GameOver
@onready var game_over_result := $CanvasLayer/GameOver/Center/VBox/Result
@onready var game_over_score := $CanvasLayer/GameOver/Center/VBox/Score
@onready var initials_label := $CanvasLayer/GameOver/Center/VBox/Initials

func _ready() -> void:
    SaveSystem.load_career()
    ArcadeRuntime.run_requested.connect(_on_run_requested)
    ArcadeRuntime.arcade_state_changed.connect(_on_arcade_state_changed)
    ArcadeRuntime.credit_changed.connect(_on_credit_changed)
    ArcadeRuntime.operator_mode_changed.connect(_on_operator_mode_changed)
    _show_attract()

func _process(delta: float) -> void:
    if ArcadeRuntime.state == "GAME_OVER":
        game_over_timer += delta
        if game_over_timer >= 1.25:
            ArcadeRuntime.begin_initials()
            _refresh_initials()
    elif ArcadeRuntime.state == "INITIALS":
        _process_initials_input()

func _on_run_requested() -> void:
    if is_instance_valid(current_game):
        return
    attract.hide()
    game_over.hide()
    current_game = game_scene.instantiate()
    add_child(current_game)
    current_game.expedition_finished.connect(_on_expedition_finished)
    ArcadeRuntime.begin_play()

func _on_expedition_finished(success: bool, score: int) -> void:
    if is_instance_valid(current_game):
        current_game.queue_free()
    current_game = null
    game_over_timer = 0.0
    initials = ["A", "A", "A"]
    initials_index = 0
    ArcadeRuntime.end_run(score, {"success": success})
    game_over_result.text = "CORE BREACHED" if success else "RIG LOST"
    game_over_score.text = "FINAL SCORE  %d" % score
    initials_label.text = ""
    game_over.show()

func _on_arcade_state_changed(_state: String) -> void:
    if ArcadeRuntime.state in ["ATTRACT", "CREDIT"]:
        _show_attract()
    elif ArcadeRuntime.state == "INITIALS":
        _refresh_initials()

func _on_credit_changed(_credits: int) -> void:
    _refresh_attract_status()

func _on_operator_mode_changed(_enabled: bool) -> void:
    _refresh_attract_status()

func _show_attract() -> void:
    game_over.hide()
    attract.show()
    _refresh_attract_status()
    _refresh_scores()

func _refresh_attract_status() -> void:
    if ArcadeRuntime.operator_mode:
        state_label.text = "OPERATOR MODE"
        operator_label.text = "FREE PLAY: %s   CREDITS/GAME: %d   DIFFICULTY: %d   F2 TO EXIT" % [
            "ON" if ArcadeRuntime.free_play else "OFF",
            ArcadeRuntime.credits_per_game,
            ArcadeRuntime.difficulty
        ]
        return
    operator_label.text = "F1 CREDIT   ENTER START   F2 OPERATOR"
    if ArcadeRuntime.free_play:
        state_label.text = "FREE PLAY  •  PRESS START"
    elif ArcadeRuntime.can_start_run():
        state_label.text = "CREDIT %d  •  PRESS START" % ArcadeRuntime.credits
    else:
        state_label.text = "INSERT CREDIT"

func _refresh_scores() -> void:
    if ArcadeRuntime.high_scores.is_empty():
        score_label.text = "TOP SCORES\n---"
        return
    var lines := PackedStringArray(["TOP SCORES"])
    var count := min(5, ArcadeRuntime.high_scores.size())
    for i in range(count):
        var entry: Dictionary = ArcadeRuntime.high_scores[i]
        lines.append("%d.  %s   %07d" % [i + 1, String(entry.get("initials", "---")), int(entry.get("score", 0))])
    score_label.text = "\n".join(lines)

func _process_initials_input() -> void:
    if Input.is_action_just_pressed("move_left"):
        initials_index = max(0, initials_index - 1)
        _refresh_initials()
    if Input.is_action_just_pressed("move_right"):
        initials_index = min(2, initials_index + 1)
        _refresh_initials()
    if Input.is_action_just_pressed("move_up"):
        _shift_letter(1)
    if Input.is_action_just_pressed("move_down"):
        _shift_letter(-1)
    if Input.is_action_just_pressed("cabinet_start"):
        ArcadeRuntime.submit_initials("".join(initials))

func _shift_letter(delta: int) -> void:
    var code := initials[initials_index].unicode_at(0) - 65
    code = posmod(code + delta, 26)
    initials[initials_index] = String.chr(65 + code)
    _refresh_initials()

func _refresh_initials() -> void:
    if ArcadeRuntime.state != "INITIALS":
        return
    var rendered := PackedStringArray()
    for i in range(3):
        var value: String = initials[i]
        rendered.append("[%s]" % value if i == initials_index else " %s " % value)
    initials_label.text = "ENTER INITIALS\n%s\nJOYSTICK CHANGES LETTERS  •  START SUBMITS" % " ".join(rendered)
