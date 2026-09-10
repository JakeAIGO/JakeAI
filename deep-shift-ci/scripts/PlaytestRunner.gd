extends Node

func _ready() -> void:
    var bot := preload("res://scripts/PlaytestBot.gd").new()
    add_child(bot)
    var report := bot.batch()
    print("DEEP_SHIFT_PLAYTEST_REPORT")
    print(JSON.stringify(report,"  "))
    var f := FileAccess.open("user://deep_shift_playtest_report.json",FileAccess.WRITE)
    if f:
        f.store_string(JSON.stringify(report,"  "))
    get_tree().quit(0)
