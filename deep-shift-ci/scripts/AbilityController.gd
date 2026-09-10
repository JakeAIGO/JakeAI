extends Node

signal ability_fired(id: String, affected: int)

@export var pulse_damage := 1
@export var seismic_damage := 2

var owner_player: CharacterBody2D
var terrain: Node2D

func configure(player: CharacterBody2D, terrain_manager: Node2D) -> void:
    owner_player = player
    terrain = terrain_manager

func seismic_charge() -> int:
    if owner_player == null or terrain == null:
        return 0
    var affected := terrain.dig_radius(owner_player.global_position, 2)
    for enemy in get_tree().get_nodes_in_group("enemy"):
        if owner_player.global_position.distance_to(enemy.global_position) <= 150.0:
            if enemy.has_method("take_damage"):
                enemy.take_damage(seismic_damage)
                affected += 1
    ability_fired.emit("seismic_charge", affected)
    return affected

func shock_pulse(range_pixels: float) -> int:
    if owner_player == null:
        return 0
    var affected := 0
    for enemy in get_tree().get_nodes_in_group("enemy"):
        if owner_player.global_position.distance_to(enemy.global_position) <= range_pixels:
            if enemy.has_method("take_damage"):
                enemy.take_damage(pulse_damage)
                affected += 1
    ability_fired.emit("shock_pulse", affected)
    return affected

func drill_dash(direction: Vector2, range_cells: int, cell_size: float) -> int:
    if owner_player == null or terrain == null:
        return 0
    var affected := 0
    var dir := direction.normalized()
    for i in range(1, range_cells + 1):
        var pos := owner_player.global_position + dir * cell_size * i
        if terrain.dig_world(pos):
            affected += 1
        for enemy in get_tree().get_nodes_in_group("enemy"):
            if pos.distance_to(enemy.global_position) <= cell_size * 0.65:
                if enemy.has_method("take_damage"):
                    enemy.take_damage(1)
                    affected += 1
    owner_player.global_position += dir * cell_size * range_cells
    ability_fired.emit("drill_dash", affected)
    return affected
