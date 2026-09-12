extends CanvasLayer

func _ready() -> void:
    GameState.run_state_changed.connect(refresh)

func refresh() -> void:
    if GameState.run.is_empty():
        return
    $Panel/HBox/Sector.text = "Sector %d/5" % [int(GameState.run.sector) + 1]
    $Panel/HBox/Score.text = "Score %d" % int(GameState.run.score)
    $Panel/HBox/Ore.text = "Credits %d" % int(GameState.run.credits)
    $Panel/HBox/Energy.text = "Energy %d/%d" % [int(GameState.run.energy), int(GameState.run.max_energy)]
    $Panel/HBox/Armor.text = "Armor %d" % int(GameState.run.armor)

func set_status(text: String) -> void:
    $Status.text = text
