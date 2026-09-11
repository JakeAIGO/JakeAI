extends Node

const MANIFEST_PATH := "res://assets/asset_manifest.json"

var manifest: Dictionary = {}
var failures: Array[String] = []

func _ready() -> void:
	load_manifest()

func load_manifest() -> bool:
	failures.clear()
	if not FileAccess.file_exists(MANIFEST_PATH):
		failures.append("Asset manifest missing")
		return false
	var file := FileAccess.open(MANIFEST_PATH, FileAccess.READ)
	if file == null:
		failures.append("Asset manifest unreadable")
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		failures.append("Asset manifest invalid JSON")
		return false
	manifest = parsed
	return true

func character_render_allowed() -> bool:
	if manifest.is_empty() and not load_manifest():
		return false
	if str(manifest.get("production_character_rendering", "BLOCKED")) != "ALLOWED":
		failures.append("Canonical JakeAI avatar master is not locked")
		return false
	for asset in manifest.get("canonical_assets", []):
		if str(asset.get("id", "")) == "jakeai_avatar_master":
			if str(asset.get("status", "")) != "APPROVED_LOCKED":
				failures.append("JakeAI avatar master has not reached APPROVED_LOCKED")
				return false
			return true
	failures.append("JakeAI avatar master entry missing")
	return false

func require_character_render() -> void:
	if not character_render_allowed():
		push_error("BRAND ASSET CONTINUITY GATE: character render blocked. " + "; ".join(failures))
