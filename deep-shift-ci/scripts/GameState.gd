extends Node

signal run_state_changed

var career := {
    "tech": 0,
    "battery": 0,
    "armor": 0,
    "ordnance": 0,
    "wins": 0,
    "runs": 0,
    "best_score": 0,
    "achievements": {}
}

var run := {}

func reset_run() -> void:
    run = {
        "sector": 0,
        "score": 0,
        "credits": 0,
        "max_energy": 100 + int(career.battery) * 10,
        "energy": 100 + int(career.battery) * 10,
        "starting_armor": int(career.armor),
        "armor": int(career.armor),
        "bomb_base": 2 + int(career.ordnance),
        "bombs": 2 + int(career.ordnance),
        "pulse_range": 2,
        "dash_range": 3,
        "ore_multiplier": 1.0,
        "dig_cost": 4,
        "skill_discount": 0,
        "combo": 1,
        "combo_cap": 9
    }
    career.runs += 1
    run_state_changed.emit()

func add_score(base: int) -> void:
    run.score += int(base * run.combo)
    run.combo = min(run.combo + 1, run.combo_cap)
    if run.combo >= 5:
        unlock_achievement("combo5")
    if run.score >= 10000:
        unlock_achievement("score10k")
    run_state_changed.emit()

func unlock_achievement(id: String) -> void:
    career.achievements[id] = true

func apply_upgrade(id: String) -> void:
    match id:
        "battery": run.max_energy += 25
        "armor": run.starting_armor += 1
        "bomb": run.bomb_base += 2
        "pulse": run.pulse_range += 1
        "dash": run.dash_range += 1
        "salvage": run.ore_multiplier += 0.5
        "efficiency": run.dig_cost = max(1, run.dig_cost - 1)
        "combo": run.combo_cap += 2
        "reactor": run.skill_discount += 2
    run_state_changed.emit()
