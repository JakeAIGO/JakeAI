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
        "pressure": 1.0,
        "pressure_cap": 5.0,
        "pressure_decay": 0.12,
        "combo": 1,
        "combo_cap": 9
    }
    career.runs += 1
    run_state_changed.emit()

func add_score(base: int) -> void:
    var multiplier: float = float(run.get("pressure", 1.0))
    run.score += int(round(float(base) * multiplier))
    bump_pressure(0.22, false)
    if multiplier >= 3.0:
        unlock_achievement("pressure3")
    if run.score >= 10000:
        unlock_achievement("score10k")
    run_state_changed.emit()

func bump_pressure(amount: float, emit_change: bool = true) -> void:
    run.pressure = min(float(run.pressure_cap), float(run.pressure) + amount)
    if emit_change:
        run_state_changed.emit()

func cool_pressure(delta: float) -> void:
    if run.is_empty():
        return
    var current: float = float(run.get("pressure", 1.0))
    if current <= 1.0:
        return
    var next_value: float = max(1.0, current - float(run.get("pressure_decay", 0.12)) * delta)
    if abs(next_value - current) >= 0.001:
        run.pressure = next_value
        run_state_changed.emit()

func break_pressure() -> void:
    if run.is_empty():
        return
    run.pressure = 1.0
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
        "combo":
            run.combo_cap += 2
            run.pressure_cap += 0.5
        "reactor": run.skill_discount += 2
    run_state_changed.emit()
