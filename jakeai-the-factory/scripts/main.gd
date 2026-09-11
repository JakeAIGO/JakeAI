extends Control

@onready var status_label: Label = $Root/TopBar/Status
@onready var budget_label: Label = $Root/TopBar/Budget
@onready var headline: Label = $Root/Hero/Headline
@onready var subhead: Label = $Root/Hero/Subhead
@onready var action_button: Button = $Root/Hero/Action
@onready var pipeline: HBoxContainer = $Root/Pipeline

var budget := 12.99
var stage_index := 0
var stages := ["DISCOVER", "DESIGN", "BUILD", "TEST", "LEGAL", "SELF-REPAIR", "MARKET", "SELL", "EXPAND"]

func _ready() -> void:
	budget_label.text = "$%.2f ORIGIN BUDGET" % budget
	action_button.pressed.connect(_advance)
	status_label.text = "AUTONOMOUS OPERATIONS: STANDBY"
	_build_pipeline()
	_play_opening()

func _build_pipeline() -> void:
	for child in pipeline.get_children():
		child.queue_free()
	for i in stages.size():
		var chip := Label.new()
		chip.text = stages[i]
		chip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		chip.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		chip.add_theme_font_size_override("font_size", 15)
		chip.modulate = Color(0.35, 0.55, 0.68) if i > stage_index else Color(0.95, 0.72, 0.24)
		pipeline.add_child(chip)

func _play_opening() -> void:
	var cues: Array[Dictionary] = [
		{"name":"boot","type":"dialogue","text":"JAKEAI PRODUCT FACTORY // BOOTING"},
		{"name":"beat","type":"wait","seconds":0.7},
		{"name":"budget","type":"dialogue","text":"Capital available: $12.99. Ambition available: unreasonable."},
		{"name":"beat2","type":"wait","seconds":1.0},
		{"name":"ready","type":"dialogue","text":"Choose an opportunity. Try not to invent legal trouble."}
	]
	SceneDirector.play_sequence("opening", cues, self)

func director_dialogue_cue(cue: Dictionary) -> void:
	headline.text = str(cue.get("text", ""))

func _advance() -> void:
	if SceneDirector.is_running():
		return
	stage_index = min(stage_index + 1, stages.size() - 1)
	_build_pipeline()
	status_label.text = "PIPELINE: %s" % stages[stage_index]
	match stages[stage_index]:
		"TEST":
			headline.text = "TEST FAILED SUCCESSFULLY"
			subhead.text = "Engineering would like a moment."
		"LEGAL":
			headline.text = "LEGAL HAS ENTERED THE CHAT"
			subhead.text = "Everybody act natural."
		"SELF-REPAIR":
			headline.text = "ROOT CAUSE FOUND"
			subhead.text = "Blind retry rejected. Repair the responsible layer."
		"SELL":
			headline.text = "FIRST SIMULATED SALE"
			subhead.text = "Revenue is simulated. Satisfaction is suspiciously real."
		"EXPAND":
			headline.text = "FACTORY EXPANSION UNLOCKED"
			subhead.text = "The Council Chamber is now accepting bad ideas professionally."
		_:
			headline.text = stages[stage_index]
			subhead.text = "Move the product forward."
