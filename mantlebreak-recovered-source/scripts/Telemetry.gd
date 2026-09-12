extends Node

const PATH := "user://deep_shift_last_run_telemetry.json"
var events: Array[Dictionary] = []
var run_seed := 0

func begin(seed_value: int) -> void:
    run_seed = seed_value
    events.clear()
    record("run_begin", {"seed":seed_value})

func record(event_type: String, payload := {}) -> void:
    events.append({"t_ms":Time.get_ticks_msec(),"type":event_type,"data":payload})

func finish(success: bool, score: int) -> void:
    record("run_end", {"success":success,"score":score})
    var f := FileAccess.open(PATH,FileAccess.WRITE)
    if f:
        f.store_string(JSON.stringify({"seed":run_seed,"events":events}, "  "))
