extends Node

@export var game_scene: PackedScene
var current_game: Node
var initials := ["A", "A", "A"]
var initials_index := 0
var game_over_timer := 0.0
var operator_index := 0

const OPERATOR_ITEMS := [
    "FREE PLAY",
    "CREDITS / GAME",
    "DIFFICULTY",
    "ATTRACT AUDIO",
    "MASTER VOLUME",
    "INPUT TEST",
    "RESET HIGH SCORES"
]

@onready var attract := $CanvasLayer/Attract
@onready var state_label := $CanvasLayer/Attract/Center/VBox/State
@onready var score_label := $CanvasLayer/Attract/Center/VBox/Scores
@onready var operator_label := $CanvasLayer/Attract/Center/VBox/Operator
@onready var operator_panel := $CanvasLayer/OperatorPanel
@onready var operator_menu := $CanvasLayer/OperatorPanel/Center/VBox/Menu
@onready var operator_diagnostics := $CanvasLayer/OperatorPanel/Center/VBox/Diagnostics
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
    if ArcadeRuntime.operator_mode:
        _process_operator_input()
        _refresh_diagnostics()
        return
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
    operator_panel.hide()
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

func _on_operator_mode_changed(enabled: bool) -> void:
    operator_panel.visible = enabled
    attract.visible = not enabled
    if enabled:
        operator_index = 0
        _refresh_operator_menu()
        _refresh_diagnostics()
    else:
        ArcadeRuntime.save_settings()
        _show_attract()

func _show_attract() -> void:
    operator_panel.hide()
    game_over.hide()
    attract.show()
    _refresh_attract_status()
    _refresh_scores()

func _refresh_attract_status() -> void:
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

func _process_operator_input() -> void:
    if Input.is_action_just_pressed("move_up"):
        operator_index = posmod(operator_index - 1, OPERATOR_ITEMS.size())
        _refresh_operator_menu()
    if Input.is_action_just_pressed("move_down"):
        operator_index = posmod(operator_index + 1, OPERATOR_ITEMS.size())
        _refresh_operator_menu()
    if Input.is_action_just_pressed("move_left"):
        _change_operator_value(-1)
    if Input.is_action_just_pressed("move_right"):
        _change_operator_value(1)
    if Input.is_action_just_pressed("cabinet_start"):
        _activate_operator_item()

func _change_operator_value(delta: int) -> void:
    match operator_index:
        0:
            ArcadeRuntime.free_play = not ArcadeRuntime.free_play
        1:
            ArcadeRuntime.credits_per_game = clamp(ArcadeRuntime.credits_per_game + delta, 1, 9)
        2:
            ArcadeRuntime.difficulty = clamp(ArcadeRuntime.difficulty + delta, 0, 2)
        3:
            ArcadeRuntime.attract_audio = not ArcadeRuntime.attract_audio
        4:
            ArcadeRuntime.master_volume = clamp(ArcadeRuntime.master_volume + float(delta) * 0.05, 0.0, 1.0)
    ArcadeRuntime.save_settings()
    _refresh_operator_menu()

func _activate_operator_item() -> void:
    if operator_index == 0:
        ArcadeRuntime.free_play = not ArcadeRuntime.free_play
    elif operator_index == 3:
        ArcadeRuntime.attract_audio = not ArcadeRuntime.attract_audio
    elif operator_index == 6:
        ArcadeRuntime.reset_high_scores()
    ArcadeRuntime.save_settings()
    _refresh_operator_menu()

func _refresh_operator_menu() -> void:
    var difficulty_names := ["EASY", "STANDARD", "HARD"]
    var values := [
        "ON" if ArcadeRuntime.free_play else "OFF",
        str(ArcadeRuntime.credits_per_game),
        difficulty_names[ArcadeRuntime.difficulty],
        "ON" if ArcadeRuntime.attract_audio else "OFF",
        "%d%%" % int(round(ArcadeRuntime.master_volume * 100.0)),
        "LIVE",
        "PRESS START"
    ]
    var lines := PackedStringArray()
    for i in range(OPERATOR_ITEMS.size()):
        var marker := ">" if i == operator_index else " "
        lines.append("%s %-20s  %s" % [marker, OPERATOR_ITEMS[i], values[i]])
    operator_menu.text = "\n".join(lines)

func _refresh_diagnostics() -> void:
    var active := PackedStringArray()
    var actions := [
        "move_up", "move_down", "move_left", "move_right",
        "cabinet_drill", "cabinet_shock", "cabinet_shield", "cabinet_boost",
        "cabinet_start", "cabinet_credit", "cabinet_operator"
    ]
    for action in actions:
        if InputMap.has_action(action) and Input.is_action_pressed(action):
            active.append(action.replace("cabinet_", "").to_upper())
    operator_diagnostics.text = "INPUT DIAGNOSTICS\nACTIVE: %s\nUSB arcade encoders may map to these actions without changing game code." % (", ".join(active) if not active.is_empty() else "NONE")

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
