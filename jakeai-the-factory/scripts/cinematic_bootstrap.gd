extends Node

# First cinematic bootstrap for JakeAI: The Factory.
# Environment/timeline work is allowed even while protagonist rendering is blocked.

@export var character_anchor_path: NodePath
@export var status_label_path: NodePath

@onready var character_anchor: Node = get_node_or_null(character_anchor_path)
@onready var status_label: Label = get_node_or_null(status_label_path)

func _ready() -> void:
	_start_cinematic_bootstrap()

func _start_cinematic_bootstrap() -> void:
	var allowed := BrandAssetGate.character_render_allowed()
	if allowed:
		_show_status("CANONICAL AVATAR LOCKED // CHARACTER CINEMATIC ENABLED")
		_enable_character_anchor()
	else:
		_show_status("BRAND CONTINUITY GATE ACTIVE // CHARACTER RENDER BLOCKED")
		_disable_character_anchor()
		_run_environment_only_opening()

func _enable_character_anchor() -> void:
	if character_anchor == null:
		return
	if character_anchor is CanvasItem:
		(character_anchor as CanvasItem).visible = true
	elif character_anchor is Node3D:
		(character_anchor as Node3D).visible = true

func _disable_character_anchor() -> void:
	if character_anchor == null:
		return
	if character_anchor is CanvasItem:
		(character_anchor as CanvasItem).visible = false
	elif character_anchor is Node3D:
		(character_anchor as Node3D).visible = false

func _run_environment_only_opening() -> void:
	var cues: Array[Dictionary] = [
		{"name":"factory_wake","type":"dialogue","text":"JAKEAI PRODUCT FACTORY // LIGHTS ONLINE"},
		{"name":"beat","type":"wait","seconds":0.65},
		{"name":"continuity","type":"dialogue","text":"Protagonist bay locked. Continuity has standards."},
		{"name":"beat2","type":"wait","seconds":0.8},
		{"name":"mission","type":"dialogue","text":"Build the world first. Nobody gets replaced by Random Guy #7."}
	]
	SceneDirector.play_sequence("environment_boot", cues, get_parent())

func _show_status(text: String) -> void:
	if status_label != null:
		status_label.text = text
