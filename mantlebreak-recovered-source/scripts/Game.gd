extends Node2D

signal expedition_finished(success: bool, score: int)

@export var player_scene: PackedScene
@export var enemy_scene: PackedScene
@export var ore_scene: PackedScene
@export var hazard_scene: PackedScene
@export var extraction_scene: PackedScene
@export var rock_scene: PackedScene
@export var boss_scene: PackedScene

@onready var sector_generator := $SectorGenerator
@onready var terrain_manager := $World/TerrainManager
@onready var entities := $World/Entities
@onready var hud := $HUD
@onready var upgrade_panel := $UpgradePanel
@onready var abilities := $AbilityController

var player: Node2D
var sector_data := {}
var sector_index := 0
var ore_collected := 0
var boss_alive := false
var waiting_for_upgrade := false

func _ready() -> void:
    GameState.reset_run()
    sector_generator.randomize_seed()
    Telemetry.begin(sector_generator.run_seed)
    upgrade_panel.upgrade_selected.connect(_on_upgrade_selected)
    start_sector(0)

func start_sector(index: int) -> void:
    sector_index = index
    waiting_for_upgrade = false
    GameState.run.sector = index
    GameState.run.energy = GameState.run.max_energy
    GameState.run.armor = GameState.run.starting_armor
    GameState.run.bombs = GameState.run.bomb_base
    sector_data = sector_generator.generate_sector(index)
    _clear_entities()
    terrain_manager.build_from_seed(int(sector_data.seed), sector_data.player_spawn, sector_data.exit_position)
    _spawn_player()
    _spawn_ore()
    _spawn_hazards()
    _spawn_rocks()
    _spawn_extraction()
    _spawn_enemies_and_boss()
    ore_collected = 0
    boss_alive = index == 4
    if index == 4:
        ArcadeRuntime.begin_boss()
    elif ArcadeRuntime.state != "PLAY":
        ArcadeRuntime.begin_play()
    if index == 0:
        hud.set_status("JOYSTICK moves and digs  •  DRILL breaks through  •  SHOCK clears space  •  SHIELD protects  •  BOOST escapes")
    else:
        hud.set_status("%s  •  Secure ore, survive, reach extraction." % sector_data.get("briefing", "Begin the expedition."))
    hud.refresh()

func _clear_entities() -> void:
    for child in entities.get_children():
        child.queue_free()

func _spawn_player() -> void:
    player = player_scene.instantiate()
    player.position = sector_data.player_spawn
    entities.add_child(player)
    player.configure(terrain_manager, abilities)
    player.energy_changed.connect(_on_player_energy_changed)
    player.armor_changed.connect(_on_player_armor_changed)
    player.player_destroyed.connect(_on_player_destroyed)
    player.special_used.connect(_on_special_used)

func _spawn_ore() -> void:
    for pos in sector_data.ore_positions:
        terrain_manager.dig_world(pos)
        var ore = ore_scene.instantiate()
        ore.position = pos
        entities.add_child(ore)
        ore.collected.connect(collect_ore)

func _spawn_hazards() -> void:
    for pos in sector_data.hazard_positions:
        terrain_manager.dig_world(pos)
        var hazard = hazard_scene.instantiate()
        hazard.position = pos
        hazard.hazard_type = sector_data.hazard_type
        entities.add_child(hazard)
        hazard.triggered.connect(_on_hazard_triggered)

func _spawn_rocks() -> void:
    for pos in sector_data.rock_positions:
        terrain_manager.dig_world(pos)
        var rock = rock_scene.instantiate()
        rock.position = pos
        entities.add_child(rock)
        rock.configure(terrain_manager)

func _spawn_extraction() -> void:
    terrain_manager.dig_world(sector_data.exit_position)
    var beacon = extraction_scene.instantiate()
    beacon.position = sector_data.exit_position
    entities.add_child(beacon)
    beacon.extraction_requested.connect(request_extract)

func _spawn_enemies_and_boss() -> void:
    for spec in sector_data.enemy_specs:
        terrain_manager.dig_world(spec.position)
        if spec.type == "boss":
            var boss = boss_scene.instantiate()
            boss.position = spec.position
            entities.add_child(boss)
            boss.configure(player, terrain_manager, hazard_scene, entities)
            boss.attack_telegraphed.connect(_on_boss_attack_telegraphed)
            boss.boss_phase_changed.connect(_on_boss_phase_changed)
            boss.boss_defeated.connect(_on_boss_defeated)
        else:
            var enemy = enemy_scene.instantiate()
            enemy.enemy_type = spec.type
            enemy.max_hp = spec.hp
            enemy.hp = spec.hp
            enemy.position = spec.position
            entities.add_child(enemy)
            enemy.configure(player, terrain_manager)
            enemy.enemy_destroyed.connect(_on_enemy_destroyed)

func _on_player_energy_changed(value: int) -> void:
    GameState.run.energy = value
    hud.refresh()

func _on_player_armor_changed(value: int) -> void:
    GameState.run.armor = value
    hud.refresh()

func _on_special_used(id: String) -> void:
    hud.set_status("%s activated." % id.capitalize())

func _on_hazard_triggered(hazard_type: String) -> void:
    hud.set_status("%s hazard triggered." % hazard_type.capitalize())

func _on_enemy_destroyed(enemy_type: String, points: int) -> void:
    GameState.add_score(points)
    hud.refresh()

func _on_boss_phase_changed(phase: int) -> void:
    hud.set_status("CORE WARDEN PHASE %d" % phase)

func _on_boss_attack_telegraphed(label: String, duration: float) -> void:
    Audio.play("boss_warning")
    Telemetry.record("boss_telegraph", {"label":label,"duration":duration})
    hud.set_status("WARNING: %s — %.1fs" % [label, duration])

func _on_boss_defeated() -> void:
    boss_alive = false
    GameState.add_score(1500)
    GameState.unlock_achievement("boss")
    hud.set_status("CORE WARDEN DESTROYED — reach extraction.")
    hud.refresh()

func collect_ore() -> void:
    ore_collected += 1
    GameState.add_score(int(100 * GameState.run.ore_multiplier))
    GameState.run.credits += 10
    GameState.run.energy = min(GameState.run.max_energy, GameState.run.energy + 10)
    GameState.unlock_achievement("firstOre")
    Audio.play("ore", 1.0 + min(0.25, ore_collected * 0.02))
    Telemetry.record("ore_collected", {"sector":sector_index,"count":ore_collected})
    hud.set_status("Ore secured — %d collected." % ore_collected)
    hud.refresh()

func request_extract() -> void:
    if waiting_for_upgrade:
        return
    var requirement: int = 0 if sector_index == 4 else int(min(int(sector_data.ore_count), 5 + sector_index))
    if sector_index == 4 and boss_alive:
        hud.set_status("Core Warden still active.")
        return
    if ore_collected < requirement:
        hud.set_status("Extraction locked — need %d more ore." % (requirement - ore_collected))
        return
    _complete_sector()

func _complete_sector() -> void:
    GameState.run.score += 500
    if sector_index >= 4:
        _finish_run(true)
        return
    waiting_for_upgrade = true
    hud.set_status("Sector cleared. Choose an upgrade.")
    upgrade_panel.show_choices(sector_generator.draft_upgrades(3))

func _on_upgrade_selected(id: String) -> void:
    if not waiting_for_upgrade:
        return
    GameState.apply_upgrade(id)
    start_sector(sector_index + 1)

func _on_player_destroyed() -> void:
    _finish_run(false)

func _finish_run(success: bool) -> void:
    var depth: int = sector_index + 1
    var tech: int = int(max(1, int(depth / 2) + (3 if success else 0) + int(GameState.run.score / 3000)))
    GameState.career.tech += tech
    if success:
        GameState.career.wins += 1
        GameState.unlock_achievement("win")
    GameState.career.best_score = max(GameState.career.best_score, GameState.run.score)
    SaveSystem.save_career()
    Telemetry.finish(success, GameState.run.score)
    if success:
        Audio.play("extract")
    expedition_finished.emit(success, GameState.run.score)
