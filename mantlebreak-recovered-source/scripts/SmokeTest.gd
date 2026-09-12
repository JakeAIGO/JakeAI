extends Node

var failures: Array[String] = []

func _ready() -> void:
    _test_game_state()
    _test_sector_generation()
    _test_upgrade_application()
    _test_terrain_excavation()
    _test_pathfinding()
    _test_rock_support()
    if failures.is_empty():
        print("DEEP_SHIFT_SMOKE_TEST: PASS")
        get_tree().quit(0)
    else:
        for failure in failures:
            push_error(failure)
        print("DEEP_SHIFT_SMOKE_TEST: FAIL (%d)" % failures.size())
        get_tree().quit(1)

func expect(condition: bool, message: String) -> void:
    if not condition:
        failures.append(message)

func _test_game_state() -> void:
    GameState.reset_run()
    expect(GameState.run.max_energy >= 100, "Run must begin with at least 100 max energy.")
    expect(GameState.run.bombs >= 2, "Run must begin with at least two seismic charges.")
    expect(GameState.run.sector == 0, "Run must begin in sector zero.")

func _test_sector_generation() -> void:
    var generator := preload("res://scripts/SectorGenerator.gd").new()
    add_child(generator)
    generator.set_seed(123456)
    var a := generator.generate_sector(0)
    generator.set_seed(123456)
    var b := generator.generate_sector(0)
    expect(a.seed == b.seed, "Deterministic sector seeds must match.")
    expect(a.ore_positions == b.ore_positions, "Ore placement must reproduce from the same seed.")
    expect(a.enemy_specs == b.enemy_specs, "Enemy placement must reproduce from the same seed.")
    expect(a.ore_count >= 5, "Sector must contain enough ore to satisfy extraction.")
    generator.queue_free()

func _test_upgrade_application() -> void:
    GameState.reset_run()
    var before := int(GameState.run.max_energy)
    GameState.apply_upgrade("battery")
    expect(GameState.run.max_energy == before + 25, "Battery upgrade must add 25 max energy.")

func _test_terrain_excavation() -> void:
    var terrain := preload("res://scripts/TerrainManager.gd").new()
    add_child(terrain)
    terrain.build_from_seed(999, Vector2(96,144), Vector2(1056,576))
    var cell := Vector2i(10,6)
    terrain._set_solid(cell, true)
    expect(terrain.is_solid_cell(cell), "QA cell should start solid.")
    var dug := terrain.dig_cell(cell)
    expect(dug, "Digging a solid cell must return true.")
    expect(not terrain.is_solid_cell(cell), "Dug cell must no longer be solid.")
    terrain.queue_free()


func _test_pathfinding() -> void:
    var terrain := preload("res://scripts/TerrainManager.gd").new()
    add_child(terrain)
    terrain.build_from_seed(2026, Vector2(96,144), Vector2(1056,576))
    var path := terrain.find_path_world(Vector2(96,144), Vector2(1056,576))
    expect(not path.is_empty(), "Generated sector should contain a path from spawn toward extraction.")
    terrain.queue_free()

func _test_rock_support() -> void:
    var terrain := preload("res://scripts/TerrainManager.gd").new()
    add_child(terrain)
    terrain.build_from_seed(77, Vector2(96,144), Vector2(1056,576))
    var rock_pos := terrain.cell_to_world(Vector2i(8,5))
    terrain._set_solid(Vector2i(8,6), true)
    expect(terrain.has_support_below(rock_pos), "Rock test cell should initially be supported.")
    terrain.dig_cell(Vector2i(8,6))
    expect(not terrain.has_support_below(rock_pos), "Rock support should disappear after excavation.")
    terrain.queue_free()
