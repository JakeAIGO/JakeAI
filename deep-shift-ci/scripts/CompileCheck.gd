extends Node

const PLAYER = preload("res://scripts/Player.gd")
const ENEMY = preload("res://scripts/Enemy.gd")
const ROCK = preload("res://scripts/Rock.gd")
const ABILITIES = preload("res://scripts/AbilityController.gd")
const BOSS = preload("res://scripts/BossController.gd")
const TERRAIN = preload("res://scripts/TerrainManager.gd")
const SECTORS = preload("res://scripts/SectorGenerator.gd")

func _ready() -> void:
    var scripts := [PLAYER, ENEMY, ROCK, ABILITIES, BOSS, TERRAIN, SECTORS]
    for script in scripts:
        if script == null:
            push_error("Gameplay script preload returned null")
            get_tree().quit(1)
            return
    print("DEEP_SHIFT_GAMEPLAY_COMPILE_GATE: PASS")
    get_tree().quit(0)
