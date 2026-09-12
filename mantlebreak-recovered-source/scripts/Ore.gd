extends Area2D

signal collected

@export var value := 100
@export var energy_restore := 10

func _ready() -> void:
    body_entered.connect(_on_body_entered)

func _on_body_entered(body: Node) -> void:
    if body.is_in_group("player"):
        collected.emit()
        queue_free()
