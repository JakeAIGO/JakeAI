extends CharacterBody2D

signal enemy_destroyed(enemy_type: String, points: int)

@export var enemy_type := "crawler"
@export var max_hp := 1
@export var hp := 1
@export var move_speed := 110.0
@export var repath_interval := 0.35

var target: Node2D
var terrain: Node2D
var path: Array[Vector2] = []
var repath_timer := 0.0

func _ready() -> void:
    add_to_group("enemy")
    match enemy_type:
        "stalker":
            move_speed = 150.0
            $Body.color = Color(0.71, 0.44, 0.87)
        "brute":
            move_speed = 80.0
            $Body.scale = Vector2(1.25, 1.25)
            $Body.color = Color(0.78, 0.57, 0.28)

func configure(player: Node2D, terrain_manager: Node2D) -> void:
    target = player
    terrain = terrain_manager
    repath_timer = 0.0

func _physics_process(delta: float) -> void:
    if not is_instance_valid(target) or terrain == null:
        velocity = Vector2.ZERO
        return

    repath_timer -= delta
    if repath_timer <= 0.0:
        path = terrain.find_path_world(global_position, target.global_position)
        repath_timer = repath_interval

    if path.is_empty():
        velocity = Vector2.ZERO
        return

    var waypoint := path[0]
    if global_position.distance_to(waypoint) < 10.0:
        path.pop_front()
        if path.is_empty():
            velocity = Vector2.ZERO
            return
        waypoint = path[0]

    velocity = global_position.direction_to(waypoint) * move_speed
    move_and_slide()

func take_damage(amount := 1) -> void:
    hp -= amount
    if hp <= 0:
        var points := 240 if enemy_type == "brute" else 140
        enemy_destroyed.emit(enemy_type, points)
        queue_free()
