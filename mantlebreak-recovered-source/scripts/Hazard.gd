extends Area2D

signal triggered(hazard_type: String)

@export_enum("gas", "lava", "spikes") var hazard_type := "gas"
@export var damage := 1
@export var energy_damage := 10
var armed := true

func _ready() -> void:
    body_entered.connect(_on_body_entered)
    _apply_visual()

func _apply_visual() -> void:
    match hazard_type:
        "gas":
            $Body.color = Color(0.42, 0.72, 0.43, 0.72)
        "lava":
            $Body.color = Color(0.88, 0.31, 0.16, 1.0)
        "spikes":
            $Body.color = Color(0.72, 0.48, 0.88, 1.0)

func _on_body_entered(body: Node) -> void:
    if not armed or not body.is_in_group("player"):
        return
    triggered.emit(hazard_type)
    if hazard_type == "gas":
        armed = false
        visible = false
        monitoring = false
        if body.has_method("drain_energy"):
            body.drain_energy(energy_damage)
    elif hazard_type == "lava":
        if body.has_method("drain_energy"):
            body.drain_energy(energy_damage)
    else:
        armed = false
        visible = false
        monitoring = false
        if body.has_method("take_damage"):
            body.take_damage(damage)
