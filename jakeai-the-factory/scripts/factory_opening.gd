extends Node3D

@onready var camera_rig: Node3D = $CameraRig
@onready var camera: Camera3D = $CameraRig/Camera3D
@onready var protagonist_anchor: Marker3D = $ProtagonistAnchor
@onready var discovery_tower: Marker3D = $DiscoveryTower
@onready var build_line: Marker3D = $BuildLine
@onready var repair_bay: Marker3D = $SelfRepairBay
@onready var council_door: Marker3D = $CouncilDoor
@onready var status: Label = $HUD/Status
@onready var caption: Label = $HUD/Caption

var shot_index := 0
var shot_names := ["ORIGIN", "DISCOVERY", "BUILD", "SELF-REPAIR", "COUNCIL"]

func _ready() -> void:
	status.text = "JAKEAI FACTORY // CAMERA SYSTEM ONLINE"
	caption.text = "Capital available: $12.99. Ambition available: unreasonable."
	_call_brand_gate()
	await get_tree().create_timer(1.2).timeout
	_play_opening_tour()

func _call_brand_gate() -> void:
	if Engine.has_singleton("BrandAssetGate"):
		Engine.get_singleton("BrandAssetGate").require_character_render()

func _play_opening_tour() -> void:
	var targets := [protagonist_anchor, discovery_tower, build_line, repair_bay, council_door]
	for i in targets.size():
		shot_index = i
		status.text = "CAMERA // %s" % shot_names[i]
		_move_camera_to(targets[i].global_position)
		await get_tree().create_timer(1.35).timeout
	caption.text = "Factory tour complete. Character slot remains continuity-gated."

func _move_camera_to(target: Vector3) -> void:
	var tween := create_tween()
	var desired := target + Vector3(0, 4.8, 10.5)
	tween.tween_property(camera_rig, "global_position", desired, 0.9).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	tween.parallel().tween_method(func(weight: float):
		camera.look_at(camera.global_position.lerp(target, weight), Vector3.UP), 0.0, 1.0, 0.9)
