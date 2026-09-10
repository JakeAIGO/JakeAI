extends Node

const BIOMES := [
    {"name":"Rust Veins","modifier":"Low Visibility","ore":7,"hazard":"gas"},
    {"name":"Crystal Fault","modifier":"Rich Ore","ore":8,"hazard":"spikes"},
    {"name":"Magma Shelf","modifier":"Hot Zone","ore":9,"hazard":"lava"},
    {"name":"Ancient Works","modifier":"Enemy Surge","ore":10,"hazard":"gas"},
    {"name":"Core Nest","modifier":"Boss Sector","ore":5,"hazard":"lava"}
]

const UPGRADES := [
    {"id":"battery","name":"Deep Cell","description":"+25 maximum energy"},
    {"id":"armor","name":"Reinforced Hull","description":"+1 starting armor"},
    {"id":"bomb","name":"Ordnance Rack","description":"+2 seismic charges"},
    {"id":"pulse","name":"Arc Amplifier","description":"+1 Shock Pulse range"},
    {"id":"dash","name":"Turbo Drill","description":"+1 Drill Dash range"},
    {"id":"salvage","name":"Salvage Magnet","description":"+50% ore score"},
    {"id":"efficiency","name":"Efficient Drill","description":"Digging costs 1 less energy"},
    {"id":"combo","name":"Score Capacitor","description":"+2 maximum combo"},
    {"id":"reactor","name":"Hot Reactor","description":"Abilities cost 2 less energy"}
]

var rng := RandomNumberGenerator.new()
var run_seed := 0

func _ready() -> void:
    if run_seed == 0:
        randomize_seed()

func randomize_seed() -> void:
    rng.randomize()
    run_seed = rng.randi()

func set_seed(value: int) -> void:
    run_seed = value
    rng.seed = value

func sector_seed(index: int) -> int:
    return int((run_seed + (index + 1) * 104729) & 0x7fffffff)

func generate_sector(index: int) -> Dictionary:
    var biome: Dictionary = BIOMES[index]
    var local_rng := RandomNumberGenerator.new()
    var seed_value := sector_seed(index)
    local_rng.seed = seed_value

    var ore_positions: Array[Vector2] = []
    for i in biome.ore:
        ore_positions.append(Vector2(
            local_rng.randi_range(220, 1080),
            local_rng.randi_range(180, 610)
        ))

    var enemy_specs: Array[Dictionary] = []
    var enemy_count := 3 + index + (2 if biome.modifier == "Enemy Surge" else 0)
    for i in enemy_count:
        var t := "crawler"
        if index >= 1 and i % 3 == 1:
            t = "stalker"
        if index >= 2 and i % 4 == 2:
            t = "brute"
        enemy_specs.append({
            "type": t,
            "hp": 2 if t == "brute" else 1,
            "position": Vector2(
                local_rng.randi_range(300, 1080),
                local_rng.randi_range(190, 600)
            )
        })

    if index == 4:
        enemy_specs.append({"type":"boss","hp":10,"position":Vector2(850,380)})

    var hazard_positions: Array[Vector2] = []
    for i in 3 + index:
        hazard_positions.append(Vector2(
            local_rng.randi_range(280, 1080),
            local_rng.randi_range(220, 600)
        ))

    var rock_positions: Array[Vector2] = []
    for i in 4 + index:
        rock_positions.append(Vector2(
            local_rng.randi_range(260, 1060),
            local_rng.randi_range(150, 520)
        ))

    return {
        "seed": seed_value,
        "name": biome.name,
        "modifier": biome.modifier,
        "hazard_type": biome.hazard,
        "ore_count": biome.ore,
        "ore_positions": ore_positions,
        "hazard_positions": hazard_positions,
        "rock_positions": rock_positions,
        "player_spawn": Vector2(140,180),
        "exit_position": Vector2(1120,600),
        "enemy_specs": enemy_specs,
        "briefing": "Sector %d — %s • %s • Seed %d" % [index + 1, biome.name, biome.modifier, seed_value]
    }

func draft_upgrades(count := 3) -> Array[Dictionary]:
    var choices: Array[Dictionary] = []
    var indexes := range(UPGRADES.size())
    indexes.shuffle()
    for i in min(count, indexes.size()):
        choices.append(UPGRADES[indexes[i]].duplicate(true))
    return choices
