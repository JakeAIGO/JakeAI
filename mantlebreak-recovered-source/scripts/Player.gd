extends CharacterBody2D

signal energy_changed(value: int)
signal armor_changed(value: int)
signal player_destroyed
signal special_used(id: String)

@export var move_speed := 220.0
@export var dig_energy_cost := 4

var energy := 100
var armor := 0
var pulse_cooldown := 0.0
var dash_cooldown := 0.0
var shield_cooldown := 0.0
var pressure_decay_accum := 0.0
var facing := Vector2.RIGHT
var terrain: Node2D
var abilities: Node

func _ready() -> void:
    add_to_group("player")
    energy = int(GameState.run.energy)
    armor = int(GameState.run.armor)

func configure(terrain_manager: Node2D, ability_controller: Node) -> void:
    terrain = terrain_manager
    abilities = ability_controller
    abilities.configure(self, terrain)

func _physics_process(delta: float) -> void:
    var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
    if input != Vector2.ZERO:
        facing = input.normalized()
        _attempt_excavate(facing)
        velocity = facing * move_speed
    else:
        velocity = Vector2.ZERO
    move_and_slide()

    pulse_cooldown = max(0.0, pulse_cooldown - delta)
    dash_cooldown = max(0.0, dash_cooldown - delta)
    shield_cooldown = max(0.0, shield_cooldown - delta)

    pressure_decay_accum += delta
    if pressure_decay_accum >= 0.25:
        GameState.cool_pressure(pressure_decay_accum)
        pressure_decay_accum = 0.0

    if Input.is_action_just_pressed("cabinet_drill"):
        use_drill()
    if Input.is_action_just_pressed("cabinet_shock"):
        use_shock()
    if Input.is_action_just_pressed("cabinet_shield"):
        use_shield()
    if Input.is_action_just_pressed("cabinet_boost"):
        use_boost()

func _attempt_excavate(direction: Vector2) -> void:
    if terrain == null:
        return
    var probe := global_position + direction.normalized() * 34.0
    if terrain.is_solid_world(probe):
        if energy < max(1, int(GameState.run.dig_cost)):
            velocity = Vector2.ZERO
            return
        if terrain.dig_world(probe):
            drain_energy(max(1, int(GameState.run.dig_cost)))
            GameState.run.score += 3
            Audio.play("dig", randf_range(0.92,1.08))

func spend_energy(amount: int) -> bool:
    if energy < amount:
        return false
    energy -= amount
    energy_changed.emit(energy)
    return true

func drain_energy(amount: int) -> void:
    energy = max(0, energy - amount)
    energy_changed.emit(energy)

func take_damage(_amount := 1) -> void:
    GameState.break_pressure()
    Audio.play("hurt")
    if armor > 0:
        armor -= 1
        armor_changed.emit(armor)
        return
    player_destroyed.emit()

# Arcade vocabulary wrappers. These keep the cabinet contract stable while
# preserving the proven recovered gameplay implementation underneath.
func use_drill() -> void:
    use_seismic_charge()

func use_shock() -> void:
    use_shock_pulse()

func use_shield() -> void:
    use_reactive_shield()

func use_boost() -> void:
    use_drill_dash()

func use_seismic_charge() -> void:
    if GameState.run.bombs <= 0 or abilities == null:
        return
    GameState.run.bombs -= 1
    abilities.seismic_charge()
    Audio.play("charge")
    Telemetry.record("ability", {"id":"drill"})
    special_used.emit("DRILL")

func use_shock_pulse() -> void:
    if pulse_cooldown > 0 or abilities == null:
        return
    var cost: int = int(max(4, 12 - int(GameState.run.skill_discount)))
    if not spend_energy(cost):
        return
    pulse_cooldown = 5.0
    abilities.shock_pulse(float(GameState.run.pulse_range) * 64.0)
    Audio.play("pulse")
    Telemetry.record("ability", {"id":"shock"})
    special_used.emit("SHOCK")

func use_drill_dash() -> void:
    if dash_cooldown > 0 or abilities == null:
        return
    var cost: int = int(max(3, 10 - int(GameState.run.skill_discount)))
    if not spend_energy(cost):
        return
    dash_cooldown = 4.0
    abilities.drill_dash(facing, int(GameState.run.dash_range), 48.0)
    GameState.bump_pressure(0.15)
    Audio.play("boost")
    Telemetry.record("ability", {"id":"boost"})
    special_used.emit("BOOST")

func use_reactive_shield() -> void:
    if shield_cooldown > 0:
        return
    var cost: int = int(max(6, 18 - int(GameState.run.skill_discount)))
    if not spend_energy(cost):
        return
    armor += 1
    armor_changed.emit(armor)
    shield_cooldown = 8.0
    Audio.play("shield")
    Telemetry.record("ability", {"id":"shield"})
    special_used.emit("SHIELD")
