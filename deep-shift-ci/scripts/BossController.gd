extends CharacterBody2D

signal boss_phase_changed(phase: int)
signal boss_defeated
signal attack_telegraphed(label: String, duration: float)

@export var max_hp := 12
@export var hp := 12
@export var move_speed := 110.0
@export var attack_interval := 4.0

var phase := 1
var target: Node2D
var terrain: Node2D
var hazard_scene: PackedScene
var hazard_parent: Node
var attack_timer := 2.5
var telegraphing := false
var telegraph_timer := 0.0
var pending_attack := ""

func configure(player: Node2D, terrain_manager: Node2D, hazard: PackedScene, parent: Node) -> void:
    target = player
    terrain = terrain_manager
    hazard_scene = hazard
    hazard_parent = parent

func _physics_process(delta: float) -> void:
    if not is_instance_valid(target):
        return
    if telegraphing:
        velocity = Vector2.ZERO
        telegraph_timer -= delta
        $Body.modulate = Color(1.0, 0.45 + 0.35 * abs(sin(Time.get_ticks_msec()/90.0)), 0.45, 1.0)
        if telegraph_timer <= 0.0:
            telegraphing = false
            $Body.modulate = Color.WHITE
            _execute_pending_attack()
        return
    var speed_mult := 1.0 if phase == 1 else (1.25 if phase == 2 else 1.55)
    velocity = global_position.direction_to(target.global_position) * move_speed * speed_mult
    move_and_slide()
    attack_timer -= delta
    if attack_timer <= 0.0:
        _begin_telegraph()
        attack_timer = max(1.8, attack_interval - float(phase - 1) * 0.75)

func _begin_telegraph() -> void:
    telegraphing = true
    telegraph_timer = 1.1 if phase == 1 else (0.9 if phase == 2 else 0.7)
    pending_attack = "lava_ring" if phase < 3 else "seismic_burst"
    attack_telegraphed.emit("LAVA RING" if pending_attack == "lava_ring" else "SEISMIC BURST", telegraph_timer)

func _execute_pending_attack() -> void:
    if pending_attack == "lava_ring":
        _spawn_hazard_ring()
    elif pending_attack == "seismic_burst":
        _spawn_hazard_ring()
        _seismic_burst()
    pending_attack = ""

func _seismic_burst() -> void:
    if terrain != null:
        terrain.dig_radius(global_position, 2)
    if is_instance_valid(target) and global_position.distance_to(target.global_position) <= 150.0:
        if target.has_method("take_damage"):
            target.take_damage(1)

func take_damage(amount := 1) -> void:
    hp -= amount
    if hp <= 0:
        boss_defeated.emit()
        queue_free()
        return
    if hp <= 8 and phase == 1:
        _set_phase(2)
    elif hp <= 4 and phase == 2:
        _set_phase(3)

func _set_phase(value: int) -> void:
    phase = value
    boss_phase_changed.emit(phase)
    attack_timer = 1.5

func _spawn_hazard_ring() -> void:
    if hazard_scene == null or hazard_parent == null:
        return
    var radius := 105.0 if phase == 1 else (125.0 if phase == 2 else 145.0)
    for angle_deg in [0,60,120,180,240,300]:
        var h = hazard_scene.instantiate()
        h.hazard_type = "lava"
        var offset := Vector2.RIGHT.rotated(deg_to_rad(angle_deg)) * radius
        h.global_position = global_position + offset
        hazard_parent.add_child(h)
