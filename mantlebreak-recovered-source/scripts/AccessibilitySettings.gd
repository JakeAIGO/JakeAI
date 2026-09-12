extends Node

const PATH := "user://deep_shift_settings.json"

var screen_shake := true
var flash_intensity := 1.0
var master_volume := 0.8
var reduce_motion := false

func _ready() -> void:
    load_settings()

func save_settings() -> void:
    var f := FileAccess.open(PATH, FileAccess.WRITE)
    if f:
        f.store_string(JSON.stringify(serialize()))

func load_settings() -> void:
    if not FileAccess.file_exists(PATH):
        return
    var f := FileAccess.open(PATH, FileAccess.READ)
    var d = JSON.parse_string(f.get_as_text())
    if typeof(d) == TYPE_DICTIONARY:
        screen_shake = bool(d.get("screen_shake",screen_shake))
        flash_intensity = float(d.get("flash_intensity",flash_intensity))
        master_volume = float(d.get("master_volume",master_volume))
        reduce_motion = bool(d.get("reduce_motion",reduce_motion))

func serialize() -> Dictionary:
    return {"screen_shake":screen_shake,"flash_intensity":flash_intensity,
        "master_volume":master_volume,"reduce_motion":reduce_motion}
