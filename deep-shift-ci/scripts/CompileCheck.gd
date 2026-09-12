extends Node

const PLAYER = preload("res://scripts/Player.gd")
const ENEMY = preload("res://scripts/Enemy.gd")
const ROCK = preload("res://scripts/Rock.gd")
const ABILITIES = preload("res://scripts/AbilityController.gd")
const BOSS = preload("res://scripts/BossController.gd")
const TERRAIN = preload("res://scripts/TerrainManager.gd")
const SECTORS = preload("res://scripts/SectorGenerator.gd")
const ARCADE_RUNTIME = preload("res://scripts/ArcadeRuntime.gd")
const CABINET_INPUT = preload("res://scripts/CabinetInput.gd")

func _ready() -> void:
    var scripts := [PLAYER, ENEMY, ROCK, ABILITIES, BOSS, TERRAIN, SECTORS, ARCADE_RUNTIME, CABINET_INPUT]
    for script in scripts:
        if script == null:
            push_error("MANTLEBREAK script preload returned null")
            get_tree().quit(1)
            return
    print("MANTLEBREAK_ARCADE_COMPILE_GATE: PASS")
    get_tree().quit(0)
