extends Node

@export var game_scene: PackedScene
var current_game: Node

func _ready() -> void:
    SaveSystem.load_career()
    _refresh_career_line()

func _on_start_pressed() -> void:
    $CanvasLayer/Menu.hide()
    $CanvasLayer/Report.hide()
    current_game = game_scene.instantiate()
    add_child(current_game)
    current_game.expedition_finished.connect(_on_expedition_finished)

func _on_career_pressed() -> void:
    var c := GameState.career
    $CanvasLayer/Menu/Center/VBox/Tagline.text = "TECH %d  •  BATTERY L%d  •  HULL L%d  •  ORDNANCE L%d  •  WINS %d" % [
        int(c.tech), int(c.battery), int(c.armor), int(c.ordnance), int(c.wins)
    ]

func _on_settings_pressed() -> void:
    $CanvasLayer/SettingsPanel.visible = not $CanvasLayer/SettingsPanel.visible

func _on_quit_pressed() -> void:
    get_tree().quit()

func _on_expedition_finished(success: bool, score: int) -> void:
    if is_instance_valid(current_game):
        current_game.queue_free()
    current_game = null
    $CanvasLayer/Report/Center/VBox/Result.text = "EXTRACTION COMPLETE" if success else "RIG LOST"
    $CanvasLayer/Report/Center/VBox/Score.text = "FINAL SCORE  %d" % score
    $CanvasLayer/Report/Center/VBox/Career.text = "TECH %d  •  BEST %d  •  RUNS %d  •  WINS %d" % [
        int(GameState.career.tech), int(GameState.career.best_score),
        int(GameState.career.runs), int(GameState.career.wins)
    ]
    $CanvasLayer/Report.show()

func _on_report_continue_pressed() -> void:
    $CanvasLayer/Report.hide()
    $CanvasLayer/Menu.show()
    $CanvasLayer/Menu/Center/VBox/Tagline.text = "DESCEND • SALVAGE • SURVIVE"
    _refresh_career_line()

func _refresh_career_line() -> void:
    var c := GameState.career
    $CanvasLayer/Menu/Center/VBox/CareerLine.text = "TECH %d   •   BEST %d   •   RUNS %d" % [
        int(c.tech), int(c.best_score), int(c.runs)
    ]
