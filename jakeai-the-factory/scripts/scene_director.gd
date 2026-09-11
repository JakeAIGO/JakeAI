extends Node

signal cue_started(cue_name: String)
signal cue_finished(cue_name: String)
signal sequence_finished(sequence_name: String)

var _running := false
var _current_sequence := ""

func is_running() -> bool:
	return _running

func play_sequence(sequence_name: String, cues: Array[Dictionary], context: Node = null) -> void:
	if _running:
		return
	_running = true
	_current_sequence = sequence_name
	for cue in cues:
		var cue_name := str(cue.get("name", "unnamed"))
		cue_started.emit(cue_name)
		await _run_cue(cue, context)
		cue_finished.emit(cue_name)
	_running = false
	sequence_finished.emit(sequence_name)
	_current_sequence = ""

func _run_cue(cue: Dictionary, context: Node) -> void:
	var cue_type := str(cue.get("type", "wait"))
	match cue_type:
		"wait":
			await get_tree().create_timer(float(cue.get("seconds", 0.5))).timeout
		"call":
			if context and context.has_method(str(cue.get("method", ""))):
				context.call(str(cue.get("method", "")), cue)
		"parallel_call":
			if context and context.has_method(str(cue.get("method", ""))):
				context.call_deferred(str(cue.get("method", "")), cue)
		"camera":
			if context and context.has_method("director_camera_cue"):
				context.call("director_camera_cue", cue)
		"dialogue":
			if context and context.has_method("director_dialogue_cue"):
				context.call("director_dialogue_cue", cue)
		"vfx":
			if context and context.has_method("director_vfx_cue"):
				context.call("director_vfx_cue", cue)
		"sfx":
			if context and context.has_method("director_sfx_cue"):
				context.call("director_sfx_cue", cue)
		_:
			push_warning("SceneDirector ignored unknown cue type: %s" % cue_type)

func stop() -> void:
	_running = false
	_current_sequence = ""
