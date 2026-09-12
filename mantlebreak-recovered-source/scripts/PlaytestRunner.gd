extends Node

const MIN_WIN_RATE := 0.20
const MAX_WIN_RATE := 0.60
const MAX_ENERGY_DEATH_SHARE := 0.45

func _ready() -> void:
    var bot := preload("res://scripts/PlaytestBot.gd").new()
    add_child(bot)
    var report := bot.batch()
    print("DEEP_SHIFT_PLAYTEST_REPORT")
    print(JSON.stringify(report,"  "))
    var f := FileAccess.open("user://deep_shift_playtest_report.json",FileAccess.WRITE)
    if f:
        f.store_string(JSON.stringify(report,"  "))

    var failures: Array[String] = []
    var win_rate: float = float(report.win_rate)
    var total_deaths: int = int(report.runs) - int(report.wins)
    var energy_deaths: int = int(report.deaths.get("energy_depletion", 0))
    var energy_share: float = 0.0 if total_deaths <= 0 else float(energy_deaths) / float(total_deaths)

    if win_rate < MIN_WIN_RATE or win_rate > MAX_WIN_RATE:
        failures.append("Win rate %.3f outside prototype gate %.2f-%.2f" % [win_rate, MIN_WIN_RATE, MAX_WIN_RATE])
    if energy_share > MAX_ENERGY_DEATH_SHARE:
        failures.append("Energy-depletion share %.3f exceeds %.2f" % [energy_share, MAX_ENERGY_DEATH_SHARE])
    for id in ["pulse","dash","charge","shield"]:
        if int(report.ability_usage.get(id,0)) <= 0:
            failures.append("Ability has zero usage: %s" % id)

    if failures.is_empty():
        print("DEEP_SHIFT_BALANCE_GATE: PASS")
        get_tree().quit(0)
        return

    for failure in failures:
        push_error(failure)
    print("DEEP_SHIFT_BALANCE_GATE: FAIL")
    get_tree().quit(1)
