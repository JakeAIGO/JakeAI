extends CharacterBody2D

signal crushed_enemy(enemy_type: String)
signal crushed_player
signal started_falling

@export var fall_speed := 320.0
@export var settle_delay := 0.18

var falling := false
var terrain: Node2D
var settle_timer := 0.0

func configure(terrain_manager: Node2D) -> void:
    terrain = terrain_manager
    if terrain != null and terrain.has_signal("cell_dug"):
        terrain.cell_dug.connect(_on_cell_dug)
    _reevaluate_support()

func _on_cell_dug(_cell: Vector2i) -> void:
    _reevaluate_support()

func _reevaluate_support() -> void:
    if terrain == null or falling:
        return
    if not terrain.has_support_below(global_position):
        settle_timer = settle_delay

func _physics_process(delta: float) -> void:
    if not falling and settle_timer > 0.0:
        settle_timer -= delta
        if settle_timer <= 0.0 and terrain != null and not terrain.has_support_below(global_position):
            falling = true
            started_falling.emit()

    if not falling:
        velocity = Vector2.ZERO
        return

    velocity = Vector2.DOWN * fall_speed
    move_and_slide()

    var hit_something := false
    for i in get_slide_collision_count():
        var collision: KinematicCollision2D = get_slide_collision(i)
        var collider: Object = collision.get_collider()
        if collider == null:
            continue

        if collider.is_in_group("enemy") and collider.has_method("take_damage"):
            var t: String = str(collider.enemy_type) if "enemy_type" in collider else "enemy"
            collider.take_damage(2)
            crushed_enemy.emit(t)
            hit_something = true
        elif collider.is_in_group("player"):
            if collider.has_method("take_damage"):
                collider.take_damage(1)
            crushed_player.emit()
            hit_something = true
        else:
            hit_something = true

    if hit_something:
        falling = false
        settle_timer = 0.0
